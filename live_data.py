#!/usr/bin/env python3
import os
import time
from dataclasses import dataclass
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

REFRESH_SECONDS = 30
WU_STATION_ID = os.getenv("WU_STATION_ID", "KOHGROVE130")
WU_API_KEY = os.getenv("WU_API_KEY", "")
FRONT_ROOM_URL = os.getenv("FRONT_ROOM_URL", "")
BEDROOM_URL = os.getenv("BEDROOM_URL", "")
INSIDE_URL = os.getenv("INSIDE_URL", "")


def read_temperature(url: str) -> Optional[float]:
    if not url or requests is None:
        return None
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        payload = response.json()
        for key in ("temperature_f", "temp_f", "temperature", "temp"):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    except Exception:
        return None
    return None


@dataclass
class LiveData:
    front_room_f: Optional[float] = None
    bedroom_f: Optional[float] = None
    inside_f: Optional[float] = None
    outside_f: Optional[float] = None
    last_refresh: float = 0.0

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_refresh < REFRESH_SECONDS:
            return
        self.last_refresh = now

        front = read_temperature(FRONT_ROOM_URL)
        bedroom = read_temperature(BEDROOM_URL)
        inside = read_temperature(INSIDE_URL)
        outside = self.read_outside()

        if front is not None:
            self.front_room_f = front
        if bedroom is not None:
            self.bedroom_f = bedroom
        if inside is not None:
            self.inside_f = inside
        if outside is not None:
            self.outside_f = outside

    def read_outside(self) -> Optional[float]:
        if requests is None or not WU_API_KEY:
            return None
        try:
            url = (
                "https://api.weather.com/v2/pws/observations/current"
                f"?stationId={WU_STATION_ID}&format=json&units=e&apiKey={WU_API_KEY}"
            )
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            payload = response.json()
            observations = payload.get("observations") or []
            if observations:
                value = observations[0].get("imperial", {}).get("temp")
                if isinstance(value, (int, float)):
                    return float(value)
        except Exception:
            return None
        return None
