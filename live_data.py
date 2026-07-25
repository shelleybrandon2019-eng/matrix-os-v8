#!/usr/bin/env python3
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

try:
    import requests
except ImportError:
    requests = None

REFRESH_SECONDS = 30
ECOWITT_BASE = "https://api.ecowitt.net/api/v3"
ECOWITT_APPLICATION_KEY = os.getenv("ECOWITT_APPLICATION_KEY", "")
ECOWITT_API_KEY = os.getenv("ECOWITT_API_KEY", "")
ECOWITT_MAC = os.getenv("ECOWITT_MAC", "")
FRONT_ROOM_URL = os.getenv("FRONT_ROOM_URL", "")
BEDROOM_URL = os.getenv("BEDROOM_URL", "")


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
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("value", "val"):
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


def _device_list(payload: Any) -> list[dict[str, Any]]:
    """Normalize the different Ecowitt device/list response shapes."""
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


@dataclass
class LiveData:
    front_room_f: Optional[float] = None
    bedroom_f: Optional[float] = None
    inside_f: Optional[float] = None
    outside_f: Optional[float] = None
    last_refresh: float = 0.0
    ecowitt_mac: str = ECOWITT_MAC
    error: str = ""

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_refresh < REFRESH_SECONDS:
            return
        self.last_refresh = now

        front = read_temperature(FRONT_ROOM_URL)
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
            payload = response.json()
            devices = _device_list(payload)

            for device in devices:
                mac = (
                    device.get("mac")
                    or device.get("device_mac")
                    or device.get("mac_address")
                )
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
        params.update({"mac": mac, "call_back": "all", "temp_unitid": "1"})
        try:
            response = requests.get(
                f"{ECOWITT_BASE}/device/real_time",
                params=params,
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else payload

            inside = _find_value(
                data,
                (
                    "indoor_temperature",
                    "indoor",
                    "tempinf",
                    "temperature_indoor",
                ),
            )
            outside = _find_value(
                data,
                (
                    "outdoor_temperature",
                    "outdoor",
                    "tempf",
                    "temperature_outdoor",
                ),
            )

            if inside is None and isinstance(data, dict):
                inside = _find_value(data.get("indoor", {}), ("temperature", "temp", "value"))
            if outside is None and isinstance(data, dict):
                outside = _find_value(data.get("outdoor", {}), ("temperature", "temp", "value"))

            self.error = "" if inside is not None or outside is not None else "Ecowitt returned no temperatures"
            return inside, outside
        except Exception as exc:
            self.error = f"Ecowitt read failed: {exc}"
            return None, None
