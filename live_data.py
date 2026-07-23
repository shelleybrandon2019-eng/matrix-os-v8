#!/usr/bin/env python3
import time
from dataclasses import dataclass
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

XRP_URL = "https://min-api.cryptocompare.com/data/price?fsym=XRP&tsyms=USD"


@dataclass
class LiveData:
    xrp_usd: Optional[float] = None
    last_refresh: float = 0.0
    error: str = ""

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_refresh < 20:
            return
        self.last_refresh = now
        if requests is None:
            self.error = "REQUESTS MISSING"
            return
        try:
            response = requests.get(XRP_URL, timeout=5)
            response.raise_for_status()
            payload = response.json()
            value = payload.get("USD")
            if isinstance(value, (int, float)):
                self.xrp_usd = float(value)
                self.error = ""
            else:
                self.error = "XRP DATA ERROR"
        except Exception:
            self.error = "XRP OFFLINE"
