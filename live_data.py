#!/usr/bin/env python3
import asyncio
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from bleak import BleakScanner
except ImportError:
    BleakScanner = None

REFRESH_SECONDS = 30
BLE_SCAN_SECONDS = 8
ECOWITT_BASE = "https://api.ecowitt.net/api/v3"
ECOWITT_APPLICATION_KEY = os.getenv("ECOWITT_APPLICATION_KEY", "")
ECOWITT_API_KEY = os.getenv("ECOWITT_API_KEY", "")
ECOWITT_MAC = os.getenv("ECOWITT_MAC", "")
FRONT_ROOM_URL = os.getenv("FRONT_ROOM_URL", "")
BEDROOM_URL = os.getenv("BEDROOM_URL", "")
FRONT_ROOM_MAC = os.getenv("FRONT_ROOM_MAC", "A4:C1:38:21:0C:F2").upper()
BEDROOM_MAC = os.getenv("BEDROOM_MAC", "A4:C1:38:17:EC:09").upper()
GOVEE_COMPANY_ID = 60552


def read_temperature(url: str) -> Optional[float]:
    if not url or requests is None:
        return None
    try:
        response = requests.get(url, timeout=6)
        response.raise_for_status()
        payload = response.json()
        for key in ("temperature_f", "temp_f", "temperature", "temp"):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    except Exception:
        return None
    return None


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("value", "val", "current", "reading"):
            parsed = _number(value.get(key))
            if parsed is not None:
                return parsed
    return None


def _find_value(node: Any, wanted: tuple[str, ...]) -> Optional[float]:
    if isinstance(node, dict):
        lowered = {str(key).lower(): value for key, value in node.items()}
        for key in wanted:
            if key in lowered:
                parsed = _number(lowered[key])
                if parsed is not None:
                    return parsed
        for value in node.values():
            parsed = _find_value(value, wanted)
            if parsed is not None:
                return parsed
    elif isinstance(node, list):
        for value in node:
            parsed = _find_value(value, wanted)
            if parsed is not None:
                return parsed
    return None


def _temperature_candidates(node: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], float]]:
    """Collect temperature readings from any Ecowitt v3 response shape."""
    found: list[tuple[tuple[str, ...], float]] = []

    if isinstance(node, dict):
        for raw_key, value in node.items():
            key = str(raw_key).lower()
            new_path = path + (key,)

            # Ecowitt commonly stores readings as {temperature: {value: "72.1"}}
            # and sometimes as tempf/tempinf or channel-specific temperature keys.
            if (
                "temp" in key
                or "temperature" in key
                or key in ("indoor", "outdoor")
            ):
                parsed = _number(value)
                if parsed is not None and -100.0 <= parsed <= 180.0:
                    found.append((new_path, parsed))

            found.extend(_temperature_candidates(value, new_path))

    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_temperature_candidates(value, path + (str(index),)))

    return found


def _pick_temperature(
    candidates: list[tuple[tuple[str, ...], float]],
    kind: str,
) -> Optional[float]:
    """Choose the best indoor/outdoor reading using path-name scoring."""
    if not candidates:
        return None

    if kind == "inside":
        positive = (
            "indoor", "inside", "tempinf", "temp_in", "room",
            "console", "gateway", "indoor_temperature",
        )
        negative = ("outdoor", "outside", "tempf", "soil", "pool", "leaf", "ch")
    else:
        positive = (
            "outdoor", "outside", "tempf", "temp_out",
            "outdoor_temperature", "weather_station",
        )
        negative = ("indoor", "inside", "tempinf", "room", "console", "gateway", "soil", "pool")

    ranked: list[tuple[int, int, float]] = []
    for path, value in candidates:
        joined = ".".join(path)
        score = 0
        for token in positive:
            if token in joined:
                score += 20
        for token in negative:
            if token in joined:
                score -= 15

        # Prefer explicit temperature nodes over generic parent nodes.
        if "temperature" in joined:
            score += 5
        if any(part in ("value", "val", "current", "reading") for part in path):
            score += 2

        ranked.append((score, -len(path), value))

    ranked.sort(reverse=True)
    return ranked[0][2] if ranked and ranked[0][0] > 0 else None


def _extract_ecowitt_temperatures(data: Any) -> tuple[Optional[float], Optional[float]]:
    """Parse both old and current Ecowitt cloud response layouts."""
    # Exact/common field names first.
    inside = _find_value(
        data,
        (
            "indoor_temperature",
            "temperature_indoor",
            "tempinf",
            "temp_in",
        ),
    )
    outside = _find_value(
        data,
        (
            "outdoor_temperature",
            "temperature_outdoor",
            "tempf",
            "temp_out",
        ),
    )

    # Ecowitt v3 often nests the actual reading under indoor/outdoor groups.
    if isinstance(data, dict):
        for container_name in ("indoor", "inside", "temp_and_humidity", "temperature"):
            container = data.get(container_name)
            if inside is None and container_name in ("indoor", "inside"):
                inside = _find_value(container, ("temperature", "temp", "value"))

        for container_name in ("outdoor", "outside"):
            container = data.get(container_name)
            if outside is None:
                outside = _find_value(container, ("temperature", "temp", "value"))

    # Final robust pass: inspect every nested path and score likely readings.
    candidates = _temperature_candidates(data)
    if inside is None:
        inside = _pick_temperature(candidates, "inside")
    if outside is None:
        outside = _pick_temperature(candidates, "outside")

    return inside, outside


def _device_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("list", "devices", "device_list"):
            items = data.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]

    for key in ("list", "devices", "device_list"):
        items = payload.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _decode_govee_h5075(payload: bytes) -> Optional[float]:
    if len(payload) < 4:
        return None
    packed = int.from_bytes(payload[1:4], byteorder="big", signed=False)
    negative = bool(packed & 0x800000)
    packed &= 0x7FFFFF
    temperature_c = (packed // 1000) / 10.0
    if negative:
        temperature_c = -temperature_c
    return round((temperature_c * 9.0 / 5.0) + 32.0, 1)


@dataclass
class LiveData:
    front_room_f: Optional[float] = None
    bedroom_f: Optional[float] = None
    inside_f: Optional[float] = None
    outside_f: Optional[float] = None
    last_refresh: float = 0.0
    ecowitt_mac: str = ECOWITT_MAC
    error: str = ""
    _ble_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _ble_values: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if BleakScanner is not None:
            threading.Thread(target=self._ble_worker, daemon=True).start()

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_refresh < REFRESH_SECONDS:
            return
        self.last_refresh = now

        with self._ble_lock:
            front = self._ble_values.get(FRONT_ROOM_MAC)
            bedroom = self._ble_values.get(BEDROOM_MAC)

        if front is None:
            front = read_temperature(FRONT_ROOM_URL)
        if bedroom is None:
            bedroom = read_temperature(BEDROOM_URL)

        inside, outside = self.read_ecowitt()

        if front is not None:
            self.front_room_f = front
        if bedroom is not None:
            self.bedroom_f = bedroom
        if inside is not None:
            self.inside_f = inside
        if outside is not None:
            self.outside_f = outside

    def _ble_worker(self) -> None:
        while True:
            try:
                asyncio.run(self._scan_govee())
            except Exception as exc:
                if not self.error:
                    self.error = f"Bluetooth scan failed: {exc}"
            time.sleep(max(1, REFRESH_SECONDS - BLE_SCAN_SECONDS))

    async def _scan_govee(self) -> None:
        if BleakScanner is None:
            return
        targets = {FRONT_ROOM_MAC, BEDROOM_MAC}
        found: dict[str, float] = {}

        def callback(device: Any, advertisement: Any) -> None:
            address = str(getattr(device, "address", "")).upper()
            if address not in targets:
                return
            manufacturer_data = getattr(advertisement, "manufacturer_data", {})
            payload = manufacturer_data.get(GOVEE_COMPANY_ID)
            if not isinstance(payload, (bytes, bytearray)):
                return
            temperature_f = _decode_govee_h5075(bytes(payload))
            if temperature_f is not None:
                found[address] = temperature_f

        scanner = BleakScanner(callback)
        await scanner.start()
        try:
            await asyncio.sleep(BLE_SCAN_SECONDS)
        finally:
            await scanner.stop()

        if found:
            with self._ble_lock:
                self._ble_values.update(found)

    def _params(self) -> dict[str, str]:
        return {
            "application_key": ECOWITT_APPLICATION_KEY,
            "api_key": ECOWITT_API_KEY,
        }

    def discover_mac(self) -> Optional[str]:
        if requests is None or not ECOWITT_APPLICATION_KEY or not ECOWITT_API_KEY:
            return None
        try:
            response = requests.get(
                f"{ECOWITT_BASE}/device/list",
                params=self._params(),
                timeout=8,
            )
            response.raise_for_status()
            devices = _device_list(response.json())
            for device in devices:
                mac = device.get("mac") or device.get("device_mac") or device.get("mac_address")
                if mac:
                    self.ecowitt_mac = str(mac)
                    self.error = ""
                    return self.ecowitt_mac
            self.error = "Ecowitt account returned no devices"
        except Exception as exc:
            self.error = f"Ecowitt device lookup failed: {exc}"
        return None

    def read_ecowitt(self) -> tuple[Optional[float], Optional[float]]:
        if requests is None:
            self.error = "Python requests module is missing"
            return None, None
        if not ECOWITT_APPLICATION_KEY or not ECOWITT_API_KEY:
            self.error = "Ecowitt keys are missing from config.env"
            return None, None

        mac = self.ecowitt_mac or self.discover_mac()
        if not mac:
            return None, None

        params = self._params()
        params.update({"mac": mac, "call_back": "all", "temp_unitid": "2"})
        try:
            response = requests.get(
                f"{ECOWITT_BASE}/device/real_time",
                params=params,
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else payload

            inside, outside = _extract_ecowitt_temperatures(data)
            self.error = "" if inside is not None or outside is not None else "Ecowitt returned no temperatures"
            return inside, outside
        except Exception as exc:
            self.error = f"Ecowitt read failed: {exc}"
            return None, None
