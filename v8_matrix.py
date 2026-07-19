#!/usr/bin/env python3
"""Matrix OS V8 cinematic Raspberry Pi display."""

import math
import os
import random
import sys
import time
from dataclasses import dataclass
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
IDLE_MIN_SECONDS, IDLE_MAX_SECONDS = 10, 19
PREP_SECONDS, TEAR_SECONDS = 1.05, 1.40
HOLD_SECONDS, COLLAPSE_SECONDS = 7.0, 1.45
DATA_REFRESH_SECONDS = 180

WU_STATION_ID = os.getenv("WU_STATION_ID", "KOHGROVE130")
WU_API_KEY = os.getenv("WU_API_KEY", "")
FRONT_ROOM_URL = os.getenv("FRONT_ROOM_URL", "")
BEDROOM_URL = os.getenv("BEDROOM_URL", "")
XRP_URL = "https://min-api.cryptocompare.com/data/price?fsym=XRP&tsyms=USD"

MATRIX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*+=<>?/\\|ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
GREEN = (0, 255, 70)
DIM_GREEN = (0, 95, 35)
WHITE_GREEN = (180, 255, 200)
BLACK = (0, 0, 0)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ease(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_out(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


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
        response = requests.get(url, timeout=4)
        response.raise_for_status()
        value = response.json()
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def cardinal(degrees: float) -> str:
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((degrees + 11.25) / 22.5) % 16]


def decoded_text(final_text: str, progress: float) -> str:
    """Reveal final text from left to right while unresolved glyphs scramble."""
    progress = clamp(progress, 0.0, 1.0)
    locked = int(len(final_text) * progress)
    chars = []
    for index, final_char in enumerate(final_text):
        if final_char == " ":
            chars.append(" ")
        elif index < locked or progress > 0.96:
            chars.append(final_char)
        else:
            chars.append(random.choice(MATRIX_CHARS))
    return "".join(chars)


@dataclass
class LiveData:
    outside_f: float = 90.0
    front_f: float = 72.0
    bedroom_f: float = 68.0
    wind_mph: float = 8.0
    wind_dir: str = "SW"
    xrp_usd: float = 2.40
    last_refresh: float = -9999.0

    def refresh(self) -> None:
        now = time.monotonic()
        if now - self.last_refresh < DATA_REFRESH_SECONDS:
            return
        self.last_refresh = now
        self.refresh_weather()
        self.refresh_room(FRONT_ROOM_URL, "front_f")
        self.refresh_room(BEDROOM_URL, "bedroom_f")
        payload = get_json(XRP_URL)
        if payload and isinstance(payload.get("USD"), (int, float)):
            self.xrp_usd = float(payload["USD"])

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

    def refresh_room(self, url: str, field: str) -> None:
        payload = get_json(url)
        if not payload:
            return
        for key in ("temperature", "temp", "temperature_f", "temp_f"):
            if isinstance(payload.get(key), (int, float)):
                setattr(self, field, float(payload[key]))
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
    Reveal("xrp", "XRP", lambda d: f"${d.xrp_usd:,.3f}", lambda _: (115, 205, 255)),
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
        self.columns = []
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

    def draw(self, surface, accent=None, accent_strength=0.0, tear=0.0, scatter=0.0):
        cx, cy = WIDTH // 2, HEIGHT // 2 + 20
        half_w = max(1, int(lerp(20, WIDTH * 0.38, ease_out(tear))))
        half_h = max(1, int(lerp(12, HEIGHT * 0.24, ease_out(tear))))
        for drop in self.columns:
            for index, char in enumerate(drop.chars):
                y = int(drop.y - index * self.char_h)
                if y < TIME_HEIGHT or y > HEIGHT:
                    continue
                x = int(drop.x + drop.sway)
                local_dim = 1.0
                if tear > 0:
                    nx = abs(x - cx) / half_w
                    ny = abs(y - cy) / half_h
                    distance = nx * nx + ny * ny
                    if distance < 1.0:
                        direction = -1 if x < cx else 1
                        bend = (1.0 - min(1.0, nx)) ** 2
                        x += int(direction * bend * 54 * tear)
                        y += int((y - cy) * 0.10 * tear)
                        local_dim = 0.42 + 0.58 * distance
                brightness = max(0.12, 1.0 - index / max(1, drop.length)) * local_dim
                color = WHITE_GREEN if index == 0 else mix(DIM_GREEN, GREEN, brightness)
                if accent and random.random() < accent_strength * (0.20 + brightness * 0.25):
                    color = mix(color, accent, 0.70)
                if scatter:
                    x += int(random.uniform(-16, 16) * scatter)
                    y += int(random.uniform(-5, 5) * scatter)
                surface.blit(self.font.render(char, True, color), (x, y))


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
        self.value_font = pygame.font.SysFont("DejaVu Sans Mono", 72, bold=True)
        self.subtitle_font = pygame.font.SysFont("DejaVu Sans Mono", 28, bold=True)
        self.rain = MatrixRain(self.matrix_font)
        self.data = LiveData()
        self.phase = "idle"
        self.phase_start = time.monotonic()
        self.idle_duration = random.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
        self.index = -1
        self.item = REVEALS[0]
        self.clock_glitch_until = 0.0

    def elapsed(self) -> float:
        return time.monotonic() - self.phase_start

    def set_phase(self, phase: str) -> None:
        self.phase, self.phase_start = phase, time.monotonic()

    def next_item(self) -> None:
        self.index = (self.index + 1) % len(REVEALS)
        self.item = REVEALS[self.index]

    def update_state(self) -> None:
        elapsed = self.elapsed()
        if self.phase == "idle":
            if random.random() < 0.0007:
                self.clock_glitch_until = time.monotonic() + random.uniform(0.08, 0.22)
            if elapsed >= self.idle_duration:
                self.next_item()
                self.set_phase("prep")
        elif self.phase == "prep" and elapsed >= PREP_SECONDS:
            self.set_phase("tear")
        elif self.phase == "tear" and elapsed >= TEAR_SECONDS:
            self.set_phase("hold")
        elif self.phase == "hold" and elapsed >= HOLD_SECONDS:
            self.set_phase("collapse")
        elif self.phase == "collapse" and elapsed >= COLLAPSE_SECONDS:
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

    def glow_text(self, font, text: str, color, center, alpha: int, glow: int = 3):
        for radius in range(glow, 0, -1):
            ghost_alpha = max(8, alpha // (radius * 4))
            ghost = font.render(text, True, (*color, ghost_alpha))
            rect = ghost.get_rect(center=center)
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius)):
                self.screen.blit(ghost, rect.move(dx, dy))
        rendered = font.render(text, True, (*color, alpha))
        self.screen.blit(rendered, rendered.get_rect(center=center))

    def draw_content(self, alpha: int, decode: float = 1.0, breakup: float = 0.0) -> None:
        accent = self.item.accent(self.data)
        center_y = TIME_HEIGHT + (HEIGHT - TIME_HEIGHT) // 2 + 8
        title_text = decoded_text(self.item.title, decode)
        value_text = decoded_text(self.item.value(self.data), max(0.0, (decode - 0.18) / 0.82))
        jitter = int(14 * breakup)
        offset_x = random.randint(-jitter, jitter) if jitter else 0
        offset_y = random.randint(-3, 3) if breakup > 0.25 else 0
        self.glow_text(self.title_font, title_text, accent, (WIDTH // 2 + offset_x, center_y - 58 + offset_y), alpha, 2)
        self.glow_text(self.value_font, value_text, accent, (WIDTH // 2 - offset_x, center_y + 10 - offset_y), alpha, 4)
        subtitle = self.item.subtitle(self.data)
        if subtitle:
            subtitle_text = decoded_text(subtitle, max(0.0, (decode - 0.42) / 0.58))
            self.glow_text(self.subtitle_font, subtitle_text, accent, (WIDTH // 2, center_y + 76), alpha, 2)

    def draw(self) -> None:
        self.screen.fill(BLACK)
        elapsed = self.elapsed()
        accent = self.item.accent(self.data)
        strength = tear = scatter = push = energy = 0.0
        if self.phase == "prep":
            t = ease(elapsed / PREP_SECONDS)
            strength, scatter, energy = t, 0.08 * t, 0.30 * t
        elif self.phase == "tear":
            t = ease(elapsed / TEAR_SECONDS)
            strength, tear, scatter, energy = 1.0, t, 0.18 * t, 0.75
        elif self.phase == "hold":
            strength, tear, scatter, energy = 0.12, 0.78, 0.01, 0.10
        elif self.phase == "collapse":
            t = ease(elapsed / COLLAPSE_SECONDS)
            strength, tear, scatter, energy = 1.0 - t, 0.78 * (1.0 - t), 0.38 * t, 0.65 * t
        if self.item.key == "wind" and self.phase in ("prep", "tear", "hold"):
            push = 5.5
        self.rain.update(push, energy)
        self.rain.draw(self.screen, accent, strength, tear, scatter)
        if self.phase == "tear":
            t = ease_out(elapsed / TEAR_SECONDS)
            alpha = int(255 * clamp((t - 0.08) / 0.92, 0.0, 1.0))
            self.draw_content(alpha, t)
        elif self.phase == "hold":
            self.draw_content(255, 1.0)
            if random.random() < 0.10:
                y, h = random.randint(TIME_HEIGHT + 20, HEIGHT - 15), random.randint(1, 4)
                strip = self.screen.subsurface((0, y, WIDTH, h)).copy()
                self.screen.blit(strip, (random.randint(-10, 10), y))
        elif self.phase == "collapse":
            t = ease(elapsed / COLLAPSE_SECONDS)
            self.draw_content(int(255 * (1.0 - t)), 1.0 - t * 0.85, t)
        self.draw_time()
        pygame.display.flip()

    def run(self) -> None:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_SPACE:
                        self.next_item()
                        self.set_phase("prep")
            self.data.refresh()
            self.update_state()
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
