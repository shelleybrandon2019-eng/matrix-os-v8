#!/usr/bin/env python3
"""Matrix OS V8 — live-data build.

No hard-coded temperatures. Outside weather comes from the configured WU
station when a key exists, otherwise Open-Meteo for Grove City. Front-room
and bedroom values come directly from the two Govee BLE sensors.
"""

import asyncio
import math
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional, Tuple

import pygame

try:
    import requests
except ImportError:
    requests = None

WIDTH, HEIGHT, FPS = 480, 320, 60
FULLSCREEN = os.getenv("MATRIX_FULLSCREEN", "1") != "0"
TIME_HEIGHT = 58
TIME_FORMAT = "%I:%M %p"

IDLE_MIN_SECONDS, IDLE_MAX_SECONDS = 8, 14
HOLD_SECONDS = 7.0
CELL_STAGGER = 0.024
SHATTER_LIFETIME = 0.62

WEATHER_REFRESH_SECONDS = 60
GOVEE_REFRESH_SECONDS = 15
XRP_REFRESH_SECONDS = 30
LATITUDE = float(os.getenv("MATRIX_LATITUDE", "39.8815"))
LONGITUDE = float(os.getenv("MATRIX_LONGITUDE", "-83.0930"))
WU_STATION_ID = os.getenv("WU_STATION_ID", "KOHGROVE130")
WU_API_KEY = os.getenv("WU_API_KEY", "")
FRONT_ROOM_MAC = os.getenv("FRONT_ROOM_MAC", "A4:C1:38:21:0C:F2").upper()
BEDROOM_MAC = os.getenv("BEDROOM_MAC", "A4:C1:38:17:EC:09").upper()

XRP_SOURCES = (
    ("COINBASE", "https://api.coinbase.com/v2/prices/XRP-USD/spot"),
    ("COINGECKO", "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd"),
    ("KRAKEN", "https://api.kraken.com/0/public/Ticker?pair=XRPUSD"),
)

MATRIX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*+=<>?/\\|ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
GREEN = (0, 255, 70)
DIM_GREEN = (0, 92, 34)
WHITE_GREEN = (185, 255, 205)
BLACK = (0, 0, 0)


def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * clamp(t, 0.0, 1.0)


def mix(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(3))


def temp_color(temp_f: Optional[float]):
    if temp_f is None:
        return GREEN
    if temp_f < 55:
        return (40, 145, 255)
    if temp_f < 66:
        return (35, 220, 220)
    if temp_f < 76:
        return (0, 255, 90)
    if temp_f < 85:
        return (245, 225, 40)
    if temp_f < 90:
        return (255, 145, 20)
    return (255, 45, 25)


def get_json(url: str) -> Optional[dict]:
    if not url or requests is None:
        return None
    try:
        response = requests.get(url, timeout=6, headers={"User-Agent": "MatrixOS-V8/2.0"})
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def cardinal(degrees: float) -> str:
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((degrees + 11.25) / 22.5) % 16]


def fetch_xrp() -> Tuple[Optional[float], str]:
    for source, url in XRP_SOURCES:
        payload = get_json(url)
        try:
            if source == "COINBASE":
                price = float(payload["data"]["amount"])
            elif source == "COINGECKO":
                price = float(payload["ripple"]["usd"])
            else:
                ticker = next(iter(payload.get("result", {}).values()))
                price = float(ticker["c"][0])
            if 0.01 < price < 1000:
                return price, source
        except Exception:
            continue
    return None, "STALE"


def decode_govee_temperature(manufacturer_data: dict) -> Optional[float]:
    """Decode Govee H5074/H5075-style advertisements."""
    for raw in manufacturer_data.values():
        data = bytes(raw)
        candidates = []
        if len(data) >= 3:
            candidates.append(int.from_bytes(data[-3:], "big"))
        if len(data) >= 6:
            candidates.append(int.from_bytes(data[3:6], "big"))
        for packed in candidates:
            negative = bool(packed & 0x800000)
            packed &= 0x7FFFFF
            temp_c = (packed // 1000) / 10.0
            if negative:
                temp_c = -temp_c
            if -40.0 <= temp_c <= 85.0:
                return temp_c * 9.0 / 5.0 + 32.0
    return None


@dataclass
class LiveData:
    outside_f: Optional[float] = None
    front_f: Optional[float] = None
    bedroom_f: Optional[float] = None
    wind_mph: Optional[float] = None
    wind_dir: str = ""
    xrp_usd: Optional[float] = None
    weather_source: str = "WAITING"
    govee_source: str = "WAITING"
    xrp_source: str = "WAITING"
    last_weather: float = -9999.0
    last_govee: float = -9999.0
    last_xrp: float = -9999.0
    _http_busy: bool = field(default=False, init=False, repr=False)
    _ble_busy: bool = field(default=False, init=False, repr=False)

    def refresh(self):
        now = time.monotonic()
        weather_due = now - self.last_weather >= WEATHER_REFRESH_SECONDS
        xrp_due = now - self.last_xrp >= XRP_REFRESH_SECONDS
        govee_due = now - self.last_govee >= GOVEE_REFRESH_SECONDS

        if (weather_due or xrp_due) and not self._http_busy:
            self._http_busy = True
            threading.Thread(target=self._http_worker, args=(weather_due, xrp_due), daemon=True).start()
        if govee_due and not self._ble_busy:
            self._ble_busy = True
            threading.Thread(target=self._ble_worker, daemon=True).start()

    def _http_worker(self, weather_due, xrp_due):
        try:
            if weather_due:
                self.refresh_weather()
                self.last_weather = time.monotonic()
            if xrp_due:
                price, source = fetch_xrp()
                if price is not None:
                    self.xrp_usd = price
                    self.xrp_source = source
                else:
                    self.xrp_source = "STALE"
                self.last_xrp = time.monotonic()
        finally:
            self._http_busy = False

    def refresh_weather(self):
        if WU_API_KEY:
            url = (
                "https://api.weather.com/v2/pws/observations/current"
                f"?stationId={WU_STATION_ID}&format=json&units=e&apiKey={WU_API_KEY}"
            )
            payload = get_json(url)
            try:
                observation = payload["observations"][0]
                imperial = observation.get("imperial", {})
                temp = imperial.get("temp")
                wind = imperial.get("windSpeed")
                direction = observation.get("winddir")
                if isinstance(temp, (int, float)):
                    self.outside_f = float(temp)
                if isinstance(wind, (int, float)):
                    self.wind_mph = float(wind)
                if isinstance(direction, (int, float)):
                    self.wind_dir = cardinal(float(direction))
                if self.outside_f is not None:
                    self.weather_source = WU_STATION_ID
                    return
            except Exception:
                pass

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LATITUDE}&longitude={LONGITUDE}"
            "&current=temperature_2m,wind_speed_10m,wind_direction_10m"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph"
        )
        payload = get_json(url)
        try:
            current = payload["current"]
            temp = current.get("temperature_2m")
            wind = current.get("wind_speed_10m")
            direction = current.get("wind_direction_10m")
            if isinstance(temp, (int, float)):
                self.outside_f = float(temp)
            if isinstance(wind, (int, float)):
                self.wind_mph = float(wind)
            if isinstance(direction, (int, float)):
                self.wind_dir = cardinal(float(direction))
            self.weather_source = "OPEN-METEO" if self.outside_f is not None else "STALE"
        except Exception:
            self.weather_source = "STALE"

    def _ble_worker(self):
        try:
            try:
                from bleak import BleakScanner
            except ImportError:
                self.govee_source = "INSTALL BLEAK"
                return

            async def scan_once():
                found = {}
                devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
                for address, pair in devices.items():
                    device, adv = pair
                    mac = (getattr(device, "address", "") or address).upper()
                    if mac not in (FRONT_ROOM_MAC, BEDROOM_MAC):
                        continue
                    temp = decode_govee_temperature(getattr(adv, "manufacturer_data", {}) or {})
                    if temp is not None:
                        found[mac] = temp
                return found

            readings = asyncio.run(scan_once())
            if FRONT_ROOM_MAC in readings:
                self.front_f = readings[FRONT_ROOM_MAC]
            if BEDROOM_MAC in readings:
                self.bedroom_f = readings[BEDROOM_MAC]
            self.govee_source = "GOVEE BLE" if readings else "GOVEE NOT FOUND"
        except Exception as exc:
            self.govee_source = "BLE ERROR"
            print(f"Govee scan failed: {exc}", file=sys.stderr)
        finally:
            self.last_govee = time.monotonic()
            self._ble_busy = False


@dataclass
class Reveal:
    key: str
    title: str
    value: Callable[[LiveData], str]
    accent: Callable[[LiveData], Tuple[int, int, int]]
    subtitle: Callable[[LiveData], str]


def temp_text(value):
    return "WAITING" if value is None else f"{value:.0f}°"


REVEALS = [
    Reveal("outside", "OUTSIDE", lambda d: temp_text(d.outside_f), lambda d: temp_color(d.outside_f), lambda d: d.weather_source),
    Reveal("front", "FRONT ROOM", lambda d: temp_text(d.front_f), lambda d: temp_color(d.front_f), lambda d: d.govee_source),
    Reveal("bedroom", "BEDROOM", lambda d: temp_text(d.bedroom_f), lambda d: temp_color(d.bedroom_f), lambda d: d.govee_source),
    Reveal("wind", "WIND", lambda d: "WAITING" if d.wind_mph is None else f"{d.wind_mph:.0f} MPH", lambda d: (80, 205, 255), lambda d: d.wind_dir or d.weather_source),
    Reveal("xrp", "XRP", lambda d: "UPDATING" if d.xrp_usd is None else f"${d.xrp_usd:,.4f}", lambda d: (115, 205, 255), lambda d: d.xrp_source),
]


@dataclass
class Drop:
    x: int
    y: float
    speed: float
    length: int
    chars: List[str]
    sway: float = 0.0
    burst: float = 1.0

    def reset(self):
        self.y = random.uniform(-HEIGHT, -10)
        self.speed = random.uniform(4.2, 15.0)
        self.length = random.randint(8, 20)
        self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
        self.burst = 1.0


class MatrixRain:
    def __init__(self, font):
        self.font = font
        self.char_w = max(11, font.size("W")[0])
        self.char_h = max(15, font.get_linesize())
        self.columns = []
        for x in range(0, WIDTH + self.char_w, self.char_w):
            drop = Drop(x, random.uniform(-HEIGHT, HEIGHT), 5.0, 12, [])
            drop.reset()
            drop.y = random.uniform(-HEIGHT, HEIGHT)
            self.columns.append(drop)

    def update(self, energy=0.0):
        for drop in self.columns:
            if random.random() < 0.003 + energy * 0.01:
                drop.burst = random.uniform(1.5, 2.8)
            drop.burst += (1.0 - drop.burst) * 0.055
            drop.y += drop.speed * drop.burst * (1.0 + energy * 0.45)
            if random.random() < 0.085:
                drop.chars[random.randrange(len(drop.chars))] = random.choice(MATRIX_CHARS)
            if drop.y - drop.length * self.char_h > HEIGHT:
                drop.reset()

    def draw(self, surface, accent=None, strength=0.0):
        for drop in self.columns:
            for index, char in enumerate(drop.chars):
                y = int(drop.y - index * self.char_h)
                if y < TIME_HEIGHT or y > HEIGHT:
                    continue
                brightness = max(0.12, 1.0 - index / max(1, drop.length))
                color = WHITE_GREEN if index == 0 else mix(DIM_GREEN, GREEN, brightness)
                if accent and random.random() < strength * (0.2 + brightness * 0.25):
                    color = mix(color, accent, 0.7)
                surface.blit(self.font.render(char, True, color), (drop.x, y))


@dataclass
class Cell:
    char: str
    x: float
    y: float
    color: Tuple[int, int, int]
    font: pygame.font.Font
    reveal_at: float
    state: str = "hidden"
    flicker: int = 0
    shown: str = ""
    vx: float = 0.0
    vy: float = 0.0
    shatter_t: float = 0.0


class RevealEngine:
    def __init__(self, lines):
        self.cells = []
        order = []
        for text, font, color, center_y in lines:
            char_w = font.size("M")[0]
            start_x = WIDTH / 2 - char_w * len(text) / 2
            for i, ch in enumerate(text):
                if ch == " ":
                    continue
                cell = Cell(ch, start_x + i * char_w, center_y, color, font, 0.0)
                self.cells.append(cell)
                order.append(cell)
        random.shuffle(order)
        for i, cell in enumerate(order):
            cell.reveal_at = i * CELL_STAGGER
        self.elapsed = 0.0
        self.duration = len(order) * CELL_STAGGER + 0.9

    def update(self, dt):
        self.elapsed += dt
        for cell in self.cells:
            if cell.state == "hidden" and self.elapsed >= cell.reveal_at:
                cell.state = "flicker"
                cell.flicker = random.randint(2, 5)
            elif cell.state == "flicker":
                cell.shown = random.choice(MATRIX_CHARS)
                cell.flicker -= 1
                if cell.flicker <= 0:
                    cell.state = "locked"
                    cell.shown = cell.char
            elif cell.state == "locked":
                cell.shown = random.choice(MATRIX_CHARS) if random.random() < 0.012 else cell.char
            elif cell.state == "shatter":
                cell.x += cell.vx * dt
                cell.y += cell.vy * dt
                cell.shatter_t += dt
                if cell.shatter_t >= SHATTER_LIFETIME:
                    cell.state = "gone"

    def revealed(self):
        return all(c.state in ("locked", "shatter", "gone") for c in self.cells)

    def gone(self):
        return all(c.state == "gone" for c in self.cells)

    def shatter(self):
        cx, cy = WIDTH / 2, HEIGHT / 2
        for cell in self.cells:
            dx, dy = cell.x - cx, cell.y - cy
            distance = math.hypot(dx, dy) or 1.0
            speed = random.uniform(85, 220)
            cell.vx = dx / distance * speed + random.uniform(-35, 35)
            cell.vy = dy / distance * speed + random.uniform(-35, 35)
            cell.state = "shatter"

    def draw(self, surface):
        for cell in self.cells:
            if cell.state in ("hidden", "gone") or cell.y < TIME_HEIGHT:
                continue
            surface.blit(cell.font.render(cell.shown or random.choice(MATRIX_CHARS), True, cell.color), (cell.x, cell.y))


class MatrixOS:
    def __init__(self):
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.matrix_font = pygame.font.SysFont("DejaVu Sans Mono", 17, bold=True)
        self.time_font = pygame.font.SysFont("DejaVu Sans Mono", 38, bold=True)
        self.title_font = pygame.font.SysFont("DejaVu Sans Mono", 25, bold=True)
        self.value_font = pygame.font.SysFont("DejaVu Sans Mono", 66, bold=True)
        self.subtitle_font = pygame.font.SysFont("DejaVu Sans Mono", 20, bold=True)
        self.rain = MatrixRain(self.matrix_font)
        self.data = LiveData()
        self.phase = "idle"
        self.phase_start = time.monotonic()
        self.idle_duration = random.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
        self.index = -1
        self.item = None
        self.engine = None

    def set_phase(self, phase):
        self.phase = phase
        self.phase_start = time.monotonic()

    def begin_reveal(self):
        self.index = (self.index + 1) % len(REVEALS)
        self.item = REVEALS[self.index]
        accent = self.item.accent(self.data)
        center_y = TIME_HEIGHT + (HEIGHT - TIME_HEIGHT) // 2 + 8
        lines = [
            (self.item.title, self.title_font, accent, center_y - 58),
            (self.item.value(self.data), self.value_font, accent, center_y + 10),
            (self.item.subtitle(self.data), self.subtitle_font, accent, center_y + 76),
        ]
        self.engine = RevealEngine(lines)
        self.set_phase("reveal")

    def update_state(self, dt):
        elapsed = time.monotonic() - self.phase_start
        if self.phase == "idle":
            if elapsed >= self.idle_duration:
                self.begin_reveal()
        elif self.phase == "reveal":
            self.engine.update(dt)
            if self.engine.revealed() or elapsed >= self.engine.duration:
                self.set_phase("hold")
        elif self.phase == "hold":
            self.engine.update(dt)
            if elapsed >= HOLD_SECONDS:
                self.engine.shatter()
                self.set_phase("shatter")
        elif self.phase == "shatter":
            self.engine.update(dt)
            if self.engine.gone() or elapsed >= SHATTER_LIFETIME + 0.9:
                self.engine = None
                self.idle_duration = random.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
                self.set_phase("idle")

    def draw_time(self):
        text = datetime.now().strftime(TIME_FORMAT).lstrip("0")
        image = self.time_font.render(text, True, GREEN)
        self.screen.blit(image, image.get_rect(center=(WIDTH // 2, TIME_HEIGHT // 2 + 2)))

    def draw(self):
        self.screen.fill(BLACK)
        accent = self.item.accent(self.data) if self.item and self.phase != "idle" else None
        energy = 0.32 if self.phase == "reveal" else 0.08
        self.rain.update(energy)
        self.rain.draw(self.screen, accent, 0.5 if self.phase == "reveal" else 0.12)
        if self.engine:
            self.engine.draw(self.screen)
        self.draw_time()
        pygame.display.flip()

    def run(self):
        last = time.monotonic()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_SPACE:
                        self.begin_reveal()
            now = time.monotonic()
            dt = now - last
            last = now
            self.data.refresh()
            self.update_state(dt)
            self.draw()
            self.clock.tick(FPS)


def main():
    try:
        MatrixOS().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix OS V8 failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
