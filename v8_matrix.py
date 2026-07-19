#!/usr/bin/env python3
"""Matrix OS V8 cinematic Raspberry Pi display.

Hard-cut glyph reveals, continuous Matrix rain, shatter collapse, live weather,
room temperatures and XRP/USD pricing with automatic source fallback.
"""

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

IDLE_MIN_SECONDS, IDLE_MAX_SECONDS = 8, 15
HOLD_SECONDS = 7.0
OS_HOLD_SECONDS = 1.35
OS_GLIMPSE_CHANCE = 0.28
CELL_STAGGER = 0.022
FLICKER_FRAMES_MIN, FLICKER_FRAMES_MAX = 2, 5
GLITCH_RELOCK_CHANCE = 0.012
SHATTER_SPEED_MIN, SHATTER_SPEED_MAX = 85.0, 220.0
SHATTER_LIFETIME = 0.62
REVEAL_TIMEOUT_PAD = 0.8

DATA_REFRESH_SECONDS = 180
XRP_REFRESH_SECONDS = 30
WU_STATION_ID = os.getenv("WU_STATION_ID", "KOHGROVE130")
WU_API_KEY = os.getenv("WU_API_KEY", "")
FRONT_ROOM_URL = os.getenv("FRONT_ROOM_URL", "")
BEDROOM_URL = os.getenv("BEDROOM_URL", "")

XRP_SOURCES = (
    ("Coinbase", "https://api.coinbase.com/v2/prices/XRP-USD/spot"),
    ("CoinGecko", "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd"),
    ("Kraken", "https://api.kraken.com/0/public/Ticker?pair=XRPUSD"),
)

MATRIX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*+=<>?/\\|ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
OS_GLIMPSES = [
    "ACCESSING...",
    "WEATHER MODULE ONLINE",
    "CAMERA LINK ACTIVE",
    "GOVEE LINK ACTIVE",
    "CRYPTO FEED ONLINE",
]

GREEN = (0, 255, 70)
DIM_GREEN = (0, 92, 34)
WHITE_GREEN = (185, 255, 205)
BLACK = (0, 0, 0)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(lerp(a[i], b[i], t)) for i in range(3))


def temp_color(temp_f: float) -> Tuple[int, int, int]:
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
        response = requests.get(
            url,
            timeout=5,
            headers={"User-Agent": "MatrixOS-V8/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def fetch_xrp_price() -> Tuple[Optional[float], str]:
    """Fetch XRP/USD using independent spot-price sources in priority order."""
    for source, url in XRP_SOURCES:
        payload = get_json(url)
        try:
            if source == "Coinbase":
                price = float(payload["data"]["amount"])
            elif source == "CoinGecko":
                price = float(payload["ripple"]["usd"])
            else:
                result = payload.get("result", {})
                ticker = next(iter(result.values()))
                price = float(ticker["c"][0])
            if 0.01 < price < 1000:
                return price, source
        except Exception:
            continue
    return None, "STALE"


def cardinal(degrees: float) -> str:
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((degrees + 11.25) / 22.5) % 16]


@dataclass
class LiveData:
    outside_f: float = 90.0
    front_f: float = 72.0
    bedroom_f: float = 68.0
    wind_mph: float = 8.0
    wind_dir: str = "SW"
    xrp_usd: float = 0.0
    xrp_source: str = "WAITING"
    last_refresh: float = -9999.0
    last_xrp_refresh: float = -9999.0
    _refreshing: bool = field(default=False, init=False, repr=False)

    def refresh(self) -> None:
        """Never block the animation loop while HTTP requests are running."""
        now = time.monotonic()
        weather_due = now - self.last_refresh >= DATA_REFRESH_SECONDS
        xrp_due = now - self.last_xrp_refresh >= XRP_REFRESH_SECONDS
        if self._refreshing or not (weather_due or xrp_due):
            return
        self._refreshing = True
        threading.Thread(
            target=self._refresh_worker,
            args=(weather_due, xrp_due),
            daemon=True,
        ).start()

    def _refresh_worker(self, weather_due: bool, xrp_due: bool) -> None:
        try:
            if weather_due:
                self.refresh_weather()
                self.refresh_room(FRONT_ROOM_URL, "front_f")
                self.refresh_room(BEDROOM_URL, "bedroom_f")
                self.last_refresh = time.monotonic()
            if xrp_due:
                price, source = fetch_xrp_price()
                if price is not None:
                    self.xrp_usd = price
                    self.xrp_source = source.upper()
                self.last_xrp_refresh = time.monotonic()
        finally:
            self._refreshing = False

    def refresh_weather(self) -> None:
        if not WU_API_KEY:
            return
        url = (
            "https://api.weather.com/v2/pws/observations/current"
            f"?stationId={WU_STATION_ID}&format=json&units=e&apiKey={WU_API_KEY}"
        )
        payload = get_json(url)
        try:
            observation = payload["observations"][0]
            imperial = observation.get("imperial", {})
            if isinstance(imperial.get("temp"), (int, float)):
                self.outside_f = float(imperial["temp"])
            if isinstance(imperial.get("windSpeed"), (int, float)):
                self.wind_mph = float(imperial["windSpeed"])
            if isinstance(observation.get("winddir"), (int, float)):
                self.wind_dir = cardinal(float(observation["winddir"]))
        except Exception:
            pass

    def refresh_room(self, url: str, field_name: str) -> None:
        payload = get_json(url)
        if not payload:
            return
        for key in ("temperature", "temp", "temperature_f", "temp_f"):
            if isinstance(payload.get(key), (int, float)):
                setattr(self, field_name, float(payload[key]))
                return


@dataclass
class Reveal:
    key: str
    title: str
    value: Callable[[LiveData], str]
    accent: Callable[[LiveData], Tuple[int, int, int]]
    subtitle: Callable[[LiveData], str] = lambda _: ""


REVEALS = [
    Reveal("outside", "OUTSIDE", lambda d: f"{d.outside_f:.0f}°", lambda d: temp_color(d.outside_f)),
    Reveal("front", "FRONT ROOM", lambda d: f"{d.front_f:.0f}°", lambda d: temp_color(d.front_f)),
    Reveal("bedroom", "BEDROOM", lambda d: f"{d.bedroom_f:.0f}°", lambda d: temp_color(d.bedroom_f)),
    Reveal("wind", "WIND", lambda d: f"{d.wind_mph:.0f} MPH", lambda _: (80, 205, 255), lambda d: d.wind_dir),
    Reveal("xrp", "XRP", lambda d: "UPDATING" if d.xrp_usd <= 0 else f"${d.xrp_usd:,.4f}", lambda _: (115, 205, 255), lambda d: d.xrp_source),
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

    def reset(self) -> None:
        self.y = random.uniform(-HEIGHT, -10)
        roll = random.random()
        if roll < 0.10:
            self.speed = random.uniform(12.0, 18.0)
        elif roll < 0.32:
            self.speed = random.uniform(7.5, 12.0)
        else:
            self.speed = random.uniform(4.2, 8.0)
        self.length = random.randint(8, 20)
        self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
        self.burst = 1.0


class MatrixRain:
    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.char_w = max(11, font.size("W")[0])
        self.char_h = max(15, font.get_linesize())
        self.columns: List[Drop] = []
        for x in range(0, WIDTH + self.char_w, self.char_w):
            length = random.randint(8, 20)
            drop = Drop(x, random.uniform(-HEIGHT, HEIGHT), 5.0, length, [random.choice(MATRIX_CHARS) for _ in range(length)])
            drop.reset()
            drop.y = random.uniform(-HEIGHT, HEIGHT)
            self.columns.append(drop)

    def update(self, push: float = 0.0, energy: float = 0.0) -> None:
        for drop in self.columns:
            if random.random() < 0.0025 + energy * 0.010:
                drop.burst = random.uniform(1.7, 3.0)
            drop.burst += (1.0 - drop.burst) * 0.055
            drop.y += drop.speed * drop.burst * (1.0 + energy * 0.55)
            drop.sway = drop.sway * 0.82 + push * 0.18
            if random.random() < 0.085:
                drop.chars[random.randrange(len(drop.chars))] = random.choice(MATRIX_CHARS)
            if drop.y - drop.length * self.char_h > HEIGHT:
                drop.reset()

    def draw(self, surface, accent=None, accent_strength: float = 0.0) -> None:
        for drop in self.columns:
            for index, char in enumerate(drop.chars):
                y = int(drop.y - index * self.char_h)
                if y < TIME_HEIGHT or y > HEIGHT:
                    continue
                x = int(drop.x + drop.sway)
                brightness = max(0.12, 1.0 - index / max(1, drop.length))
                color = WHITE_GREEN if index == 0 else mix(DIM_GREEN, GREEN, brightness)
                if accent and random.random() < accent_strength * (0.20 + brightness * 0.25):
                    color = mix(color, accent, 0.70)
                surface.blit(self.font.render(char, True, color), (x, y))


@dataclass
class Cell:
    char: str
    x: float
    y: float
    color: Tuple[int, int, int]
    font: pygame.font.Font
    reveal_at: float
    state: str = "hidden"
    flicker_left: int = 0
    display_char: str = ""
    vx: float = 0.0
    vy: float = 0.0
    shatter_t: float = 0.0


class RevealEngine:
    def __init__(self, lines: List[Tuple[str, pygame.font.Font, Tuple[int, int, int], int]]):
        self.cells: List[Cell] = []
        reveal_order: List[Cell] = []
        for text, font, color, center_y in lines:
            if not text:
                continue
            char_w = font.size("M")[0]
            total_w = char_w * len(text)
            start_x = WIDTH / 2 - total_w / 2
            for i, ch in enumerate(text):
                if ch == " ":
                    continue
                cell = Cell(ch, start_x + i * char_w, center_y, color, font, 0.0)
                self.cells.append(cell)
                reveal_order.append(cell)
        random.shuffle(reveal_order)
        for i, cell in enumerate(reveal_order):
            cell.reveal_at = i * CELL_STAGGER
        self.duration = len(reveal_order) * CELL_STAGGER + REVEAL_TIMEOUT_PAD
        self.elapsed = 0.0
        self.shattering = False

    def is_revealed(self) -> bool:
        return all(c.state in ("locked", "shatter", "gone") for c in self.cells)

    def is_gone(self) -> bool:
        return all(c.state == "gone" for c in self.cells)

    def start_shatter(self) -> None:
        if self.shattering:
            return
        self.shattering = True
        cx, cy = WIDTH / 2, HEIGHT / 2
        for cell in self.cells:
            if cell.state == "gone":
                continue
            dx, dy = cell.x - cx, cell.y - cy
            distance = math.hypot(dx, dy) or 1.0
            speed = random.uniform(SHATTER_SPEED_MIN, SHATTER_SPEED_MAX)
            cell.vx = dx / distance * speed + random.uniform(-35, 35)
            cell.vy = dy / distance * speed + random.uniform(-35, 35)
            cell.state = "shatter"
            cell.shatter_t = 0.0

    def update(self, dt: float) -> None:
        self.elapsed += dt
        for cell in self.cells:
            if cell.state == "hidden" and self.elapsed >= cell.reveal_at:
                cell.state = "flicker"
                cell.flicker_left = random.randint(FLICKER_FRAMES_MIN, FLICKER_FRAMES_MAX)
                cell.display_char = random.choice(MATRIX_CHARS)
            elif cell.state == "flicker":
                cell.display_char = random.choice(MATRIX_CHARS)
                cell.flicker_left -= 1
                if cell.flicker_left <= 0:
                    cell.state = "locked"
                    cell.display_char = cell.char
            elif cell.state == "locked":
                cell.display_char = random.choice(MATRIX_CHARS) if random.random() < GLITCH_RELOCK_CHANCE else cell.char
            elif cell.state == "shatter":
                cell.x += cell.vx * dt
                cell.y += cell.vy * dt
                cell.shatter_t += dt
                if cell.shatter_t >= SHATTER_LIFETIME:
                    cell.state = "gone"

    def draw(self, surface) -> None:
        for cell in self.cells:
            if cell.state in ("hidden", "gone") or cell.y < TIME_HEIGHT:
                continue
            surface.blit(cell.font.render(cell.display_char, True, cell.color), (cell.x, cell.y))


class MatrixOS:
    def __init__(self):
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.mouse.set_visible(False)
        pygame.display.set_caption("Matrix OS V8")
        self.clock = pygame.time.Clock()
        self.matrix_font = pygame.font.SysFont("DejaVu Sans Mono", 17, bold=True)
        self.time_font = pygame.font.SysFont("DejaVu Sans Mono", 38, bold=True)
        self.title_font = pygame.font.SysFont("DejaVu Sans Mono", 25, bold=True)
        self.value_font = pygame.font.SysFont("DejaVu Sans Mono", 66, bold=True)
        self.subtitle_font = pygame.font.SysFont("DejaVu Sans Mono", 22, bold=True)
        self.glimpse_font = pygame.font.SysFont("DejaVu Sans Mono", 22, bold=True)
        self.rain = MatrixRain(self.matrix_font)
        self.data = LiveData()
        self.phase = "idle"
        self.phase_start = time.monotonic()
        self.idle_duration = random.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
        self.index = -1
        self.item: Optional[Reveal] = None
        self.is_glimpse = False
        self.engine: Optional[RevealEngine] = None
        self.clock_glitch_until = 0.0

    def elapsed(self) -> float:
        return time.monotonic() - self.phase_start

    def set_phase(self, phase: str) -> None:
        self.phase, self.phase_start = phase, time.monotonic()

    def next_item(self) -> None:
        self.index = (self.index + 1) % len(REVEALS)
        self.item = REVEALS[self.index]

    def begin_reveal(self) -> None:
        if random.random() < OS_GLIMPSE_CHANCE:
            self.is_glimpse = True
            lines = [(random.choice(OS_GLIMPSES), self.glimpse_font, (120, 230, 160), HEIGHT // 2 - 10)]
            self.engine = RevealEngine(lines)
        else:
            self.is_glimpse = False
            self.next_item()
            accent = self.item.accent(self.data)
            center_y = TIME_HEIGHT + (HEIGHT - TIME_HEIGHT) // 2 + 8
            lines = [
                (self.item.title, self.title_font, accent, center_y - 58),
                (self.item.value(self.data), self.value_font, accent, center_y + 10),
            ]
            subtitle = self.item.subtitle(self.data)
            if subtitle:
                lines.append((subtitle, self.subtitle_font, accent, center_y + 76))
            self.engine = RevealEngine(lines)
        self.set_phase("reveal")

    def update_state(self, dt: float) -> None:
        elapsed = self.elapsed()
        if self.phase == "idle":
            if random.random() < 0.0007:
                self.clock_glitch_until = time.monotonic() + random.uniform(0.08, 0.22)
            if elapsed >= self.idle_duration:
                self.begin_reveal()
        elif self.phase == "reveal":
            self.engine.update(dt)
            if self.engine.is_revealed() or elapsed >= self.engine.duration:
                self.set_phase("hold")
        elif self.phase == "hold":
            self.engine.update(dt)
            hold_target = OS_HOLD_SECONDS if self.is_glimpse else HOLD_SECONDS
            if elapsed >= hold_target:
                self.engine.start_shatter()
                self.set_phase("shatter")
        elif self.phase == "shatter":
            self.engine.update(dt)
            if self.engine.is_gone() or elapsed >= SHATTER_LIFETIME + REVEAL_TIMEOUT_PAD:
                self.engine = None
                self.idle_duration = random.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
                self.set_phase("idle")

    def draw_time(self) -> None:
        text = datetime.now().strftime(TIME_FORMAT).lstrip("0")
        glitch = time.monotonic() < self.clock_glitch_until
        rendered = self.time_font.render(text, True, GREEN)
        rect = rendered.get_rect(center=(WIDTH // 2 + (random.randint(-5, 5) if glitch else 0), TIME_HEIGHT // 2 + 2))
        if glitch:
            ghost = self.time_font.render(text, True, (0, 110, 255))
            self.screen.blit(ghost, rect.move(random.randint(-4, 4), random.randint(-2, 2)))
        self.screen.blit(rendered, rect)

    def draw(self) -> None:
        self.screen.fill(BLACK)
        accent = None
        strength = 0.0
        energy = 0.0
        push = 0.0
        if self.phase in ("reveal", "hold", "shatter") and not self.is_glimpse and self.item:
            accent = self.item.accent(self.data)
            strength = 0.55 if self.phase == "reveal" else 0.15
            energy = 0.35 if self.phase == "reveal" else 0.10
            if self.item.key == "wind":
                push = 5.5
        elif self.phase in ("reveal", "hold", "shatter") and self.is_glimpse:
            strength, energy = 0.20, 0.15
        self.rain.update(push, energy)
        self.rain.draw(self.screen, accent, strength)
        if self.engine is not None:
            self.engine.draw(self.screen)
        self.draw_time()
        pygame.display.flip()

    def run(self) -> None:
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


def main() -> int:
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
