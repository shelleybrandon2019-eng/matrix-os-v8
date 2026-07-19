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
IDLE_MIN_SECONDS, IDLE_MAX_SECONDS = 12, 24
PREP_SECONDS, TEAR_SECONDS = 1.35, 1.25
HOLD_SECONDS, COLLAPSE_SECONDS = 7.0, 1.55
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

    def reset(self) -> None:
        self.y = random.uniform(-HEIGHT, -10)
        self.speed = random.uniform(2.2, 6.0)
        self.length = random.randint(7, 18)
        self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]


class MatrixRain:
    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.char_w = max(11, font.size("W")[0])
        self.char_h = max(15, font.get_linesize())
        self.columns = []
        for x in range(0, WIDTH + self.char_w, self.char_w):
            length = random.randint(7, 18)
            self.columns.append(Drop(x, random.uniform(-HEIGHT, HEIGHT), random.uniform(2.2, 6.0), length, [random.choice(MATRIX_CHARS) for _ in range(length)]))

    def update(self, push: float = 0.0) -> None:
        for drop in self.columns:
            drop.y += drop.speed
            drop.sway = drop.sway * 0.85 + push * 0.15
            if random.random() < 0.04:
                drop.chars[random.randrange(len(drop.chars))] = random.choice(MATRIX_CHARS)
            if drop.y - drop.length * self.char_h > HEIGHT:
                drop.reset()

    def draw(self, surface, accent=None, accent_strength=0.0, tear=0.0, scatter=0.0):
        cx, cy = WIDTH // 2, HEIGHT // 2 + 20
        half_w = int(lerp(0, WIDTH * 0.42, ease_out(tear)))
        half_h = int(lerp(0, HEIGHT * 0.26, ease_out(tear)))
        for drop in self.columns:
            for index, char in enumerate(drop.chars):
                y = int(drop.y - index * self.char_h)
                if y < TIME_HEIGHT or y > HEIGHT:
                    continue
                x = int(drop.x + drop.sway)
                if tear > 0 and half_w and half_h:
                    nx = abs(x - cx) / half_w
                    ny = abs(y - cy) / half_h
                    if nx * nx + ny * ny < 1.0:
                        direction = -1 if x < cx else 1
                        x += int(direction * (1.0 - min(1.0, nx)) ** 2 * 90 * tear)
                        y += int((y - cy) * 0.18 * tear)
                        if random.random() < 0.60 * tear:
                            continue
                brightness = max(0.12, 1.0 - index / max(1, drop.length))
                color = WHITE_GREEN if index == 0 else mix(DIM_GREEN, GREEN, brightness)
                if accent and random.random() < accent_strength * (0.18 + brightness * 0.22):
                    color = mix(color, accent, 0.72)
                if scatter:
                    x += int(random.uniform(-18, 18) * scatter)
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

    def draw_content(self, alpha: int, scale: float = 1.0, breakup: float = 0.0) -> None:
        accent = self.item.accent(self.data)
        layer = pygame.Surface((WIDTH, HEIGHT - TIME_HEIGHT), pygame.SRCALPHA)
        center_y = (HEIGHT - TIME_HEIGHT) // 2 + 10
        title = self.title_font.render(self.item.title, True, (*accent, alpha))
        value = self.value_font.render(self.item.value(self.data), True, (*accent, alpha))
        title_rect = title.get_rect(center=(WIDTH // 2, center_y - 55))
        value_rect = value.get_rect(center=(WIDTH // 2, center_y + 10))
        if breakup:
            jitter = int(20 * breakup)
            title_rect.x += random.randint(-jitter, jitter)
            value_rect.x += random.randint(-jitter, jitter)
        layer.blit(title, (title_rect.x, title_rect.y - TIME_HEIGHT))
        layer.blit(value, (value_rect.x, value_rect.y - TIME_HEIGHT))
        subtitle = self.item.subtitle(self.data)
        if subtitle:
            sub = self.subtitle_font.render(subtitle, True, (*accent, alpha))
            rect = sub.get_rect(center=(WIDTH // 2, center_y + 72))
            layer.blit(sub, (rect.x, rect.y - TIME_HEIGHT))
        if scale != 1.0:
            layer = pygame.transform.smoothscale(layer, (max(1, int(WIDTH * scale)), max(1, int((HEIGHT - TIME_HEIGHT) * scale))))
            self.screen.blit(layer, layer.get_rect(center=(WIDTH // 2, TIME_HEIGHT + (HEIGHT - TIME_HEIGHT) // 2)))
        else:
            self.screen.blit(layer, (0, TIME_HEIGHT))

    def draw(self) -> None:
        self.screen.fill(BLACK)
        elapsed = self.elapsed()
        accent = self.item.accent(self.data)
        strength = tear = scatter = push = 0.0
        if self.phase == "prep":
            t = ease(elapsed / PREP_SECONDS)
            strength, scatter = t, 0.10 * t
        elif self.phase == "tear":
            t = ease(elapsed / TEAR_SECONDS)
            strength, tear, scatter = 1.0, t, 0.28 * t
        elif self.phase == "hold":
            strength, tear, scatter = 0.16, 1.0, 0.03
        elif self.phase == "collapse":
            t = ease(elapsed / COLLAPSE_SECONDS)
            strength, tear, scatter = 1.0 - t, 1.0 - t, 0.35 * t
        if self.item.key == "wind" and self.phase in ("prep", "tear", "hold"):
            push = 5.5
        self.rain.update(push)
        self.rain.draw(self.screen, accent, strength, tear, scatter)
        if self.phase == "tear":
            t = ease_out(elapsed / TEAR_SECONDS)
            self.draw_content(int(255 * t), lerp(0.88, 1.0, t))
        elif self.phase == "hold":
            self.draw_content(255, 1.0 + math.sin(time.monotonic() * 2.2) * 0.006)
            if random.random() < 0.10:
                y, h = random.randint(TIME_HEIGHT + 20, HEIGHT - 15), random.randint(1, 4)
                strip = self.screen.subsurface((0, y, WIDTH, h)).copy()
                self.screen.blit(strip, (random.randint(-10, 10), y))
        elif self.phase == "collapse":
            t = ease(elapsed / COLLAPSE_SECONDS)
            self.draw_content(int(255 * (1.0 - t)), lerp(1.0, 1.07, t), t)
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
