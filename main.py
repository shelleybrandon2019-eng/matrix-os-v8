#!/usr/bin/env python3
import os
import random
import sys
import threading
import time
from datetime import datetime
from typing import Optional, Tuple

import pygame

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

PAGE_SECONDS = float(os.getenv("MATRIX_PAGE_SECONDS", "8"))
XRP_REFRESH_SECONDS = 30
CLOCK_Y = 43
PAGE_TITLE_Y = 105

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
    """Choose a font that actually contains the Japanese Matrix rain glyphs."""
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

    # Never fall back to a font that turns Japanese symbols into square boxes.
    # MatrixEngine detects this fallback and uses its box-free ASCII glyph set.
    return choose_font(size)


def format_temp(value):
    return "--°F" if value is None else f"{value:.1f}°F"


def format_xrp(value):
    return "UPDATING" if value is None else f"${value:,.4f}"


def fetch_xrp() -> Tuple[Optional[float], str]:
    if requests is None:
        return None, "REQUESTS MISSING"

    for source, url in XRP_SOURCES:
        try:
            response = requests.get(
                url,
                timeout=6,
                headers={"User-Agent": "MatrixOS-V9/1.0"},
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
        pygame.display.set_caption("Matrix OS V9")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.rain_font = choose_rain_font(15)
        self.clock_font = choose_font(64)
        self.page_font = choose_font(18)
        self.label_font = choose_font(21)
        self.value_font = choose_font(48)
        self.xrp_value_font = choose_font(68)
        self.source_font = choose_font(16)

        self.engine = MatrixEngine(WIDTH, HEIGHT, self.rain_font)
        self.data = LiveData()
        self.data.refresh(force=True)
        self.xrp = XRPFeed()
        self.xrp.refresh(force=True)

        self.page_index = 0
        self.page_started = time.monotonic()
        self.next_glitch = time.monotonic() + random.uniform(3.0, 7.0)
        self.glitch_until = 0.0

    def glow_text(self, text, font, center, color=GREEN, glow=2):
        base = font.render(text, True, color)
        rect = base.get_rect(center=center)
        for radius in range(glow, 0, -1):
            dim = tuple(max(0, c // (radius + 2)) for c in color)
            ghost = font.render(text, True, dim)
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius)):
                self.screen.blit(ghost, rect.move(dx, dy))
        self.screen.blit(base, rect)

    def draw_clock(self):
        # No seconds: this lets the clock stay much larger and cleaner.
        text = datetime.now().strftime("%I:%M %p").lstrip("0")
        if time.monotonic() > self.next_glitch:
            self.glitch_until = time.monotonic() + random.uniform(0.05, 0.14)
            self.next_glitch = time.monotonic() + random.uniform(3.0, 7.0)
        x = WIDTH // 2 + (random.randint(-4, 4) if time.monotonic() < self.glitch_until else 0)
        self.glow_text(text, self.clock_font, (x, CLOCK_Y), HEAD_GREEN, 2)

    def update_page(self):
        if time.monotonic() - self.page_started >= PAGE_SECONDS:
            self.page_index = (self.page_index + 1) % len(self.PAGES)
            self.page_started = time.monotonic()
            self.glitch_until = time.monotonic() + 0.20

    def draw_page_title(self, title):
        self.glow_text(title, self.page_font, (WIDTH // 2, PAGE_TITLE_Y), GREEN, 1)

    def draw_temp_pair(self, title, left_label, left_value, right_label, right_value):
        self.draw_page_title(title)
        items = [
            (left_label, left_value, 125),
            (right_label, right_value, 355),
        ]
        for label, value, x in items:
            self.glow_text(label, self.label_font, (x, 166), GREEN, 1)
            self.glow_text(format_temp(value), self.value_font, (x, 224), HEAD_GREEN, 2)

    def draw_xrp(self):
        self.draw_page_title("XRP LIVE")
        self.glow_text("XRP / USD", self.label_font, (WIDTH // 2, 160), GREEN, 1)
        self.glow_text(format_xrp(self.xrp.price), self.xrp_value_font, (WIDTH // 2, 224), HEAD_GREEN, 3)
        self.glow_text(self.xrp.source, self.source_font, (WIDTH // 2, 282), GREEN, 1)

    def draw_content(self):
        page = self.PAGES[self.page_index]
        if page == "ECOWITT":
            self.draw_temp_pair(
                "ECOWITT",
                "INSIDE",
                self.data.inside_f,
                "OUTSIDE",
                self.data.outside_f,
            )
        elif page == "GOVEE":
            self.draw_temp_pair(
                "GOVEE",
                "FRONT ROOM",
                self.data.front_room_f,
                "BEDROOM",
                self.data.bedroom_f,
            )
        else:
            self.draw_xrp()

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.engine.update()
        self.engine.draw(self.screen)
        self.draw_clock()
        self.draw_content()
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                        self.page_index = (self.page_index + 1) % len(self.PAGES)
                        self.page_started = time.monotonic()
                    elif event.key == pygame.K_LEFT:
                        self.page_index = (self.page_index - 1) % len(self.PAGES)
                        self.page_started = time.monotonic()

            self.data.refresh()
            self.xrp.refresh()
            self.update_page()
            self.draw()
            self.clock.tick(FPS)


def main() -> int:
    try:
        MatrixOS().run()
        return 0
    except Exception as exc:
        print(f"Matrix OS V9 failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
