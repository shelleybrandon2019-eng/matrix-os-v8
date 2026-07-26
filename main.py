#!/usr/bin/env python3
"""Matrix OS V9.4 cinematic live display."""

import os
import random
import sys
import threading
import time
from datetime import datetime
from typing import Optional, Tuple

import pygame

from drop_transition import DropCollectMelt
from live_data import LiveData
from matrix_engine import GREEN, HEAD_GREEN, MatrixEngine

try:
    import requests
except ImportError:
    requests = None

WIDTH = 480
HEIGHT = 320
FPS = 60
FULLSCREEN = os.getenv("MATRIX_FULLSCREEN", "1") != "0"

PAGE_SECONDS = float(os.getenv("MATRIX_PAGE_SECONDS", "9"))
XRP_REFRESH_SECONDS = 30
CLOCK_Y = 43
PAGE_TITLE_Y = 112
TEMP_LABEL_Y = 194
TEMP_VALUE_Y = 252
TEMP_BRIGHT = (240, 255, 245)
COLLECT_SECONDS = 1.85
MELT_SECONDS = 2.05
STATIC_SECONDS = max(2.5, PAGE_SECONDS - COLLECT_SECONDS - MELT_SECONDS)

XRP_SOURCES = (
    ("COINBASE", "https://api.coinbase.com/v2/prices/XRP-USD/spot"),
    ("COINGECKO", "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd"),
    ("KRAKEN", "https://api.kraken.com/0/public/Ticker?pair=XRPUSD"),
)


def choose_font(size: int) -> pygame.font.Font:
    preferred = ["Liberation Mono", "DejaVu Sans Mono", "Noto Sans Mono", "monospace"]
    for name in preferred:
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def choose_rain_font(size: int) -> pygame.font.Font:
    preferred = [
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "Noto Sans Mono CJK JP",
        "IPAGothic",
        "TakaoGothic",
        "VL Gothic",
    ]
    for name in preferred:
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)

    common_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
    ]
    for path in common_paths:
        if os.path.exists(path):
            return pygame.font.Font(path, size)

    return choose_font(size)


def format_temp(value) -> str:
    return "--°F" if value is None else f"{value:.1f}°F"


def format_xrp(value) -> str:
    return "UPDATING" if value is None else f"${value:,.4f}"


def fetch_xrp() -> Tuple[Optional[float], str]:
    if requests is None:
        return None, "REQUESTS MISSING"

    for source, url in XRP_SOURCES:
        try:
            response = requests.get(
                url,
                timeout=6,
                headers={"User-Agent": "MatrixOS-V9.4/1.0"},
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
                return price, source
        except Exception:
            continue

    return None, "XRP STALE"


class XRPFeed:
    def __init__(self) -> None:
        self.price: Optional[float] = None
        self.source = "WAITING"
        self.last_refresh = -9999.0
        self.busy = False

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if self.busy:
            return
        if not force and now - self.last_refresh < XRP_REFRESH_SECONDS:
            return

        self.busy = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            price, source = fetch_xrp()
            if price is not None:
                self.price = price
            self.source = source
            self.last_refresh = time.monotonic()
        finally:
            self.busy = False


class MatrixOS:
    PAGES = ("ECOWITT", "GOVEE", "XRP")

    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS V9.4 - Cinematic")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.rain_font = choose_rain_font(15)
        self.clock_font = choose_font(64)
        self.page_font = choose_font(18)
        self.label_font = choose_font(21)
        self.value_font = choose_font(50)
        self.xrp_value_font = choose_font(68)
        self.source_font = choose_font(16)

        self.engine = MatrixEngine(WIDTH, HEIGHT, self.rain_font)
        self.data = LiveData()
        self.data.refresh(force=True)
        self.xrp = XRPFeed()
        self.xrp.refresh(force=True)

        self.page_index = 0
        self.pending_step = 1
        self.phase = "collect"
        self.phase_started = time.monotonic()
        self.effect: Optional[DropCollectMelt] = None

        self.next_glitch = time.monotonic() + random.uniform(3.5, 8.0)
        self.glitch_until = 0.0
        self.begin_collect()

    def glow_text_to(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        center,
        color=GREEN,
        glow: int = 2,
    ) -> None:
        base = font.render(text, True, color)
        rect = base.get_rect(center=center)

        for radius in range(glow, 0, -1):
            dim = tuple(max(0, c // (radius + 2)) for c in color)
            ghost = font.render(text, True, dim)
            offsets = (
                (radius, 0),
                (-radius, 0),
                (0, radius),
                (0, -radius),
                (radius, radius),
                (-radius, radius),
            )
            for dx, dy in offsets:
                surface.blit(ghost, rect.move(dx, dy))

        surface.blit(base, rect)

    def draw_clock(self) -> None:
        text = datetime.now().strftime("%I:%M %p").lstrip("0")
        now = time.monotonic()

        if now > self.next_glitch:
            self.glitch_until = now + random.uniform(0.05, 0.13)
            self.next_glitch = now + random.uniform(3.5, 8.0)

        x = WIDTH // 2
        if now < self.glitch_until:
            x += random.randint(-4, 4)

        self.glow_text_to(
            self.screen,
            text,
            self.clock_font,
            (x, CLOCK_Y),
            HEAD_GREEN,
            3,
        )

    def render_page(self, surface: pygame.Surface, page_index: int, glow: bool) -> None:
        page = self.PAGES[page_index]
        page_glow = 2 if glow else 0
        value_glow = 4 if glow else 0

        if page == "ECOWITT":
            self.glow_text_to(
                surface,
                "ECOWITT",
                self.page_font,
                (WIDTH // 2, PAGE_TITLE_Y),
                GREEN,
                page_glow,
            )
            items = (
                ("INSIDE", self.data.inside_f, 125),
                ("OUTSIDE", self.data.outside_f, 355),
            )
            self._draw_temp_items(surface, items, page_glow, value_glow)

        elif page == "GOVEE":
            self.glow_text_to(
                surface,
                "GOVEE",
                self.page_font,
                (WIDTH // 2, PAGE_TITLE_Y),
                GREEN,
                page_glow,
            )
            items = (
                ("FRONT ROOM", self.data.front_room_f, 125),
                ("BEDROOM", self.data.bedroom_f, 355),
            )
            self._draw_temp_items(surface, items, page_glow, value_glow)

        else:
            self.glow_text_to(
                surface,
                "XRP LIVE",
                self.page_font,
                (WIDTH // 2, PAGE_TITLE_Y),
                GREEN,
                page_glow,
            )
            self.glow_text_to(
                surface,
                "XRP / USD",
                self.label_font,
                (WIDTH // 2, 176),
                GREEN,
                page_glow,
            )
            self.glow_text_to(
                surface,
                format_xrp(self.xrp.price),
                self.xrp_value_font,
                (WIDTH // 2, 242),
                TEMP_BRIGHT,
                value_glow,
            )
            self.glow_text_to(
                surface,
                self.xrp.source,
                self.source_font,
                (WIDTH // 2, 292),
                GREEN,
                page_glow,
            )

    def _draw_temp_items(self, surface, items, page_glow: int, value_glow: int) -> None:
        for label, value, x in items:
            self.glow_text_to(
                surface,
                label,
                self.label_font,
                (x, TEMP_LABEL_Y),
                GREEN,
                page_glow,
            )
            self.glow_text_to(
                surface,
                format_temp(value),
                self.value_font,
                (x, TEMP_VALUE_Y),
                TEMP_BRIGHT,
                value_glow,
            )

    def rain_source_points(self):
        points = []
        for stream in self.engine.streams:
            for index in range(min(stream.length, 9)):
                y = stream.y - index * self.engine.char_h
                if 76 <= y <= HEIGHT:
                    points.append((stream.x, y))
        return points

    def build_effect(self, page_index: int) -> DropCollectMelt:
        target = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        target.fill((0, 0, 0, 0))
        self.render_page(target, page_index, glow=False)

        effect = DropCollectMelt(
            WIDTH,
            HEIGHT,
            self.rain_font,
            self.engine.glyph_set,
            target,
            self.rain_source_points(),
        )
        effect.collect_seconds = COLLECT_SECONDS
        effect.melt_seconds = MELT_SECONDS
        return effect

    def begin_collect(self) -> None:
        self.effect = self.build_effect(self.page_index)
        self.effect.start_collect()
        self.phase = "collect"
        self.phase_started = time.monotonic()
        self.glitch_until = time.monotonic() + 0.17
        self.engine.trigger_cinematic_flash(72)

    def begin_melt(self, step: int = 1) -> None:
        self.pending_step = step
        self.effect = self.build_effect(self.page_index)
        self.effect.start_melt()
        self.phase = "melt"
        self.phase_started = time.monotonic()
        self.glitch_until = time.monotonic() + 0.15
        self.engine.trigger_cinematic_flash(48)

    def update_phase(self, dt: float) -> None:
        elapsed = time.monotonic() - self.phase_started

        if self.phase == "collect":
            if self.effect is not None:
                self.effect.update(dt)
                if self.effect.finished():
                    self.phase = "hold"
                    self.phase_started = time.monotonic()

        elif self.phase == "hold":
            if elapsed >= STATIC_SECONDS:
                self.begin_melt(1)

        elif self.phase == "melt":
            if self.effect is not None:
                self.effect.update(dt)
                if self.effect.finished():
                    self.page_index = (self.page_index + self.pending_step) % len(self.PAGES)
                    self.begin_collect()

    def draw(self) -> None:
        self.screen.fill((0, 0, 0))

        rain_speed = 1.07 if self.phase != "hold" else 1.0
        self.engine.update(rain_speed)
        self.engine.draw(self.screen)

        if self.phase == "hold":
            self.render_page(self.screen, self.page_index, glow=True)
        elif self.effect is not None:
            self.effect.draw(self.screen)

        self.draw_clock()
        pygame.display.flip()

    def run(self) -> None:
        running = True
        last = time.monotonic()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                        self.begin_melt(1)
                    elif event.key == pygame.K_LEFT:
                        self.begin_melt(-1)

            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now

            self.data.refresh()
            self.xrp.refresh()
            self.update_phase(dt)
            self.draw()
            self.clock.tick(FPS)


def main() -> int:
    try:
        MatrixOS().run()
        return 0
    except Exception as exc:
        print(f"Matrix OS V9.4 failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
