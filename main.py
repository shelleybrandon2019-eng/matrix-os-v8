#!/usr/bin/env python3
"""Matrix OS V8 approved cinematic display.

This restores the visual system Brandon approved:
  * independent mixed-speed Matrix rain that never pauses or gets boxed off
  * one reading at a time
  * random cell-by-cell hard reveal with quick glyph flickers
  * full-brightness text only; no alpha fades
  * outward shatter with a hard cut
  * smaller clock pinned above the rain and reveal area
"""

import math
import os
import random
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import pygame

from live_data import LiveData

try:
    import requests
except ImportError:
    requests = None

WIDTH, HEIGHT, FPS = 480, 320, 60
FULLSCREEN = os.getenv("MATRIX_FULLSCREEN", "1") != "0"
TIME_HEIGHT = 58
TIME_FORMAT = "%I:%M %p"

IDLE_MIN_SECONDS, IDLE_MAX_SECONDS = 10, 19
HOLD_SECONDS = 7.0
OS_HOLD_SECONDS = 1.4
OS_GLIMPSE_CHANCE = 0.35

CELL_STAGGER = 0.028
FLICKER_FRAMES_MIN, FLICKER_FRAMES_MAX = 2, 4
GLITCH_RELOCK_CHANCE = 0.02
SHATTER_SPEED_MIN, SHATTER_SPEED_MAX = 70.0, 190.0
SHATTER_LIFETIME = 0.55
REVEAL_TIMEOUT_PAD = 1.0

XRP_REFRESH_SECONDS = 30
WIND_REFRESH_SECONDS = 30
ECOWITT_BASE = "https://api.ecowitt.net/api/v3"
ECOWITT_APPLICATION_KEY = os.getenv("ECOWITT_APPLICATION_KEY", "")
ECOWITT_API_KEY = os.getenv("ECOWITT_API_KEY", "")
ECOWITT_MAC = os.getenv("ECOWITT_MAC", "")

XRP_SOURCES = (
    ("COINBASE", "https://api.coinbase.com/v2/prices/XRP-USD/spot"),
    ("COINGECKO", "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd"),
    ("KRAKEN", "https://api.kraken.com/0/public/Ticker?pair=XRPUSD"),
)

MATRIX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*+=<>?/\\|ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"

OS_GLIMPSES = [
    "ACCESSING...",
    "CPU 12%",
    "WEATHER MODULE ONLINE",
    "CAMERA 3 CONNECTED",
    "GOVEE LINK ACTIVE",
]

GREEN = (0, 255, 70)
DIM_GREEN = (0, 95, 35)
WHITE_GREEN = (180, 255, 200)
BLACK = (0, 0, 0)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = clamp(t, 0.0, 1.0)
    return tuple(int(lerp(a[i], b[i], t)) for i in range(3))


def temp_color(temp_f: Optional[float]) -> Tuple[int, int, int]:
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


def format_temp(value: Optional[float]) -> str:
    return "--°" if value is None else f"{value:.0f}°"


def cardinal(degrees: float) -> str:
    points = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    return points[int((degrees + 11.25) / 22.5) % 16]


def _number(value) -> Optional[float]:
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


def _find_value(node, wanted: Tuple[str, ...]) -> Optional[float]:
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


def fetch_xrp() -> Optional[float]:
    if requests is None:
        return None
    for source, url in XRP_SOURCES:
        try:
            response = requests.get(
                url,
                timeout=6,
                headers={"User-Agent": "MatrixOS-V8-Approved/1.0"},
            )
            response.raise_for_status()
            payload = response.json()
            if source == "COINBASE":
                price = float(payload["data"]["amount"])
            elif source == "COINGECKO":
                price = float(payload["ripple"]["usd"])
            else:
                ticker = next(iter(payload.get("result", {}).values()))
                price = float(ticker["c"][0])
            if 0.01 < price < 1000:
                return price
        except Exception:
            continue
    return None


class XRPFeed:
    def __init__(self) -> None:
        self.price: Optional[float] = None
        self.last_refresh = -9999.0
        self.busy = False

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if self.busy or (not force and now - self.last_refresh < XRP_REFRESH_SECONDS):
            return
        self.busy = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            price = fetch_xrp()
            if price is not None:
                self.price = price
            self.last_refresh = time.monotonic()
        finally:
            self.busy = False


class WindFeed:
    def __init__(self) -> None:
        self.speed_mph: Optional[float] = None
        self.direction = ""
        self.last_refresh = -9999.0
        self.busy = False

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if self.busy or (not force and now - self.last_refresh < WIND_REFRESH_SECONDS):
            return
        if requests is None or not ECOWITT_APPLICATION_KEY or not ECOWITT_API_KEY or not ECOWITT_MAC:
            return
        self.busy = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            response = requests.get(
                f"{ECOWITT_BASE}/device/real_time",
                params={
                    "application_key": ECOWITT_APPLICATION_KEY,
                    "api_key": ECOWITT_API_KEY,
                    "mac": ECOWITT_MAC,
                    "call_back": "all",
                    "temp_unitid": "2",
                    "wind_speed_unitid": "9",
                },
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            speed = _find_value(data, ("wind_speed", "windspeed", "wind_speed_avg", "speed"))
            degrees = _find_value(data, ("wind_direction", "winddir", "wind_dir", "direction"))
            if speed is not None:
                self.speed_mph = speed
            if degrees is not None:
                self.direction = cardinal(degrees)
            self.last_refresh = time.monotonic()
        except Exception:
            self.last_refresh = time.monotonic()
        finally:
            self.busy = False


@dataclass(frozen=True)
class Reveal:
    key: str
    title: str


REVEALS = [
    Reveal("outside", "OUTSIDE"),
    Reveal("inside", "INSIDE"),
    Reveal("front", "FRONT ROOM"),
    Reveal("bedroom", "BEDROOM"),
    Reveal("wind", "WIND"),
    Reveal("xrp", "XRP"),
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
    """Approved V8 rain: independent, full-width, mixed speed, no fade surface."""

    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.char_w = max(11, font.size("W")[0])
        self.char_h = max(15, font.get_linesize())
        self.columns: List[Drop] = []
        for x in range(0, WIDTH + self.char_w, self.char_w):
            length = random.randint(8, 20)
            drop = Drop(
                x,
                random.uniform(-HEIGHT, HEIGHT),
                5.0,
                length,
                [random.choice(MATRIX_CHARS) for _ in range(length)],
            )
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

    def draw(
        self,
        surface: pygame.Surface,
        accent: Optional[Tuple[int, int, int]] = None,
        accent_strength: float = 0.0,
    ) -> None:
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
    """Hard-cut random-cell reveal, hold, then outward hard-cut shatter."""

    def __init__(self, lines: List[Tuple[str, pygame.font.Font, Tuple[int, int, int], int]]):
        self.cells: List[Cell] = []
        reveal_order: List[Cell] = []

        for text, font, color, center_y in lines:
            if not text:
                continue
            char_w = font.size("M")[0]
            total_w = char_w * len(text)
            start_x = WIDTH / 2 - total_w / 2
            for index, char in enumerate(text):
                if char == " ":
                    continue
                cell = Cell(
                    char=char,
                    x=start_x + index * char_w,
                    y=center_y,
                    color=color,
                    font=font,
                    reveal_at=0.0,
                )
                self.cells.append(cell)
                reveal_order.append(cell)

        random.shuffle(reveal_order)
        for index, cell in enumerate(reveal_order):
            cell.reveal_at = index * CELL_STAGGER

        self.duration = len(reveal_order) * CELL_STAGGER + REVEAL_TIMEOUT_PAD
        self.elapsed = 0.0
        self.shattering = False

    def is_revealed(self) -> bool:
        return all(cell.state in ("locked", "shatter", "gone") for cell in self.cells)

    def is_gone(self) -> bool:
        return all(cell.state == "gone" for cell in self.cells)

    def start_shatter(self) -> None:
        if self.shattering:
            return
        self.shattering = True
        center_x, center_y = WIDTH / 2, HEIGHT / 2
        for cell in self.cells:
            if cell.state == "gone":
                continue
            dx, dy = cell.x - center_x, cell.y - center_y
            distance = math.hypot(dx, dy) or 1.0
            speed = random.uniform(SHATTER_SPEED_MIN, SHATTER_SPEED_MAX)
            cell.vx = (dx / distance) * speed + random.uniform(-30, 30)
            cell.vy = (dy / distance) * speed + random.uniform(-30, 30)
            cell.state = "shatter"
            cell.shatter_t = 0.0

    def update(self, dt: float) -> None:
        self.elapsed += dt
        for cell in self.cells:
            if cell.state == "hidden":
                if self.elapsed >= cell.reveal_at:
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
                cell.display_char = (
                    random.choice(MATRIX_CHARS)
                    if random.random() < GLITCH_RELOCK_CHANCE
                    else cell.char
                )
            elif cell.state == "shatter":
                cell.x += cell.vx * dt
                cell.y += cell.vy * dt
                cell.shatter_t += dt
                if cell.shatter_t >= SHATTER_LIFETIME:
                    cell.state = "gone"

    def draw(self, surface: pygame.Surface) -> None:
        for cell in self.cells:
            if cell.state in ("hidden", "gone") or cell.y < TIME_HEIGHT:
                continue
            surface.blit(cell.font.render(cell.display_char, True, cell.color), (cell.x, cell.y))


class MatrixOS:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.mouse.set_visible(False)
        pygame.display.set_caption("Matrix OS V8 - Approved")
        self.clock = pygame.time.Clock()

        self.matrix_font = pygame.font.SysFont("DejaVu Sans Mono", 17, bold=True)
        self.time_font = pygame.font.SysFont("DejaVu Sans Mono", 38, bold=True)
        self.title_font = pygame.font.SysFont("DejaVu Sans Mono", 25, bold=True)
        self.value_font = pygame.font.SysFont("DejaVu Sans Mono", 72, bold=True)
        self.subtitle_font = pygame.font.SysFont("DejaVu Sans Mono", 28, bold=True)
        self.glimpse_font = pygame.font.SysFont("DejaVu Sans Mono", 22, bold=True)

        self.rain = MatrixRain(self.matrix_font)
        self.data = LiveData()
        self.data.refresh(force=True)
        self.xrp = XRPFeed()
        self.xrp.refresh(force=True)
        self.wind = WindFeed()
        self.wind.refresh(force=True)

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
        self.phase = phase
        self.phase_start = time.monotonic()

    def next_item(self) -> None:
        self.index = (self.index + 1) % len(REVEALS)
        self.item = REVEALS[self.index]

    def item_value(self, item: Reveal) -> str:
        if item.key == "outside":
            return format_temp(self.data.outside_f)
        if item.key == "inside":
            return format_temp(self.data.inside_f)
        if item.key == "front":
            return format_temp(self.data.front_room_f)
        if item.key == "bedroom":
            return format_temp(self.data.bedroom_f)
        if item.key == "wind":
            return "-- MPH" if self.wind.speed_mph is None else f"{self.wind.speed_mph:.0f} MPH"
        return "UPDATING" if self.xrp.price is None else f"${self.xrp.price:,.3f}"

    def item_accent(self, item: Reveal) -> Tuple[int, int, int]:
        if item.key == "outside":
            return temp_color(self.data.outside_f)
        if item.key == "inside":
            return temp_color(self.data.inside_f)
        if item.key == "front":
            return temp_color(self.data.front_room_f)
        if item.key == "bedroom":
            return temp_color(self.data.bedroom_f)
        if item.key == "wind":
            return (80, 205, 255)
        return (115, 205, 255)

    def item_subtitle(self, item: Reveal) -> str:
        return self.wind.direction if item.key == "wind" else ""

    def begin_reveal(self) -> None:
        if random.random() < OS_GLIMPSE_CHANCE:
            self.is_glimpse = True
            text = random.choice(OS_GLIMPSES)
            lines = [(text, self.glimpse_font, (120, 230, 160), HEIGHT // 2 - 10)]
            self.engine = RevealEngine(lines)
        else:
            self.is_glimpse = False
            self.next_item()
            assert self.item is not None
            accent = self.item_accent(self.item)
            center_y = TIME_HEIGHT + (HEIGHT - TIME_HEIGHT) // 2 + 8
            lines = [
                (self.item.title, self.title_font, accent, center_y - 58),
                (self.item_value(self.item), self.value_font, accent, center_y + 10),
            ]
            subtitle = self.item_subtitle(self.item)
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

        elif self.phase == "reveal" and self.engine is not None:
            self.engine.update(dt)
            if self.engine.is_revealed() or elapsed >= self.engine.duration:
                self.set_phase("hold")

        elif self.phase == "hold" and self.engine is not None:
            hold_target = OS_HOLD_SECONDS if self.is_glimpse else HOLD_SECONDS
            self.engine.update(dt)
            if elapsed >= hold_target:
                self.engine.start_shatter()
                self.set_phase("shatter")

        elif self.phase == "shatter" and self.engine is not None:
            self.engine.update(dt)
            if self.engine.is_gone() or elapsed >= SHATTER_LIFETIME + REVEAL_TIMEOUT_PAD:
                self.engine = None
                self.idle_duration = random.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
                self.set_phase("idle")

    def draw_time(self) -> None:
        text = datetime.now().strftime(TIME_FORMAT).lstrip("0")
        glitch = time.monotonic() < self.clock_glitch_until
        rendered = self.time_font.render(text, True, GREEN)
        rect = rendered.get_rect(
            center=(
                WIDTH // 2 + (random.randint(-5, 5) if glitch else 0),
                TIME_HEIGHT // 2 + 2,
            )
        )
        if glitch:
            ghost = self.time_font.render(text, True, (0, 110, 255))
            self.screen.blit(ghost, rect.move(random.randint(-4, 4), random.randint(-2, 2)))
        self.screen.blit(rendered, rect)

    def draw(self) -> None:
        self.screen.fill(BLACK)

        accent: Optional[Tuple[int, int, int]] = None
        strength = 0.0
        energy = 0.0
        push = 0.0

        if self.phase in ("reveal", "hold", "shatter") and not self.is_glimpse and self.item:
            accent = self.item_accent(self.item)
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
                    if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                        self.begin_reveal()

            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now

            self.data.refresh()
            self.xrp.refresh()
            self.wind.refresh()
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
        print(f"Matrix OS V8 Approved failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
