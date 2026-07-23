#!/usr/bin/env python3
import os
import random
import sys
import time
from datetime import datetime

import pygame

from live_data import LiveData
from matrix_engine import GREEN, HEAD_GREEN, MatrixEngine

WIDTH = 480
HEIGHT = 320
FPS = 60
FULLSCREEN = os.getenv("MATRIX_FULLSCREEN", "1") != "0"


def choose_font(size: int, bold: bool = False) -> pygame.font.Font:
    preferred = [
        "Liberation Mono",
        "DejaVu Sans Mono",
        "Noto Sans Mono",
        "monospace",
    ]
    for name in preferred:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


class MatrixOS:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.rain_font = choose_font(15)
        self.clock_font = choose_font(42)
        self.label_font = choose_font(18)
        self.value_font = choose_font(39)
        self.small_font = choose_font(14)

        self.engine = MatrixEngine(WIDTH, HEIGHT, self.rain_font)
        self.data = LiveData()
        self.data.refresh(force=True)
        self.next_glitch = time.monotonic() + random.uniform(2.0, 5.0)
        self.glitch_until = 0.0

    def glow_text(self, text: str, font: pygame.font.Font, center, color=GREEN, glow=2) -> None:
        base = font.render(text, True, color)
        rect = base.get_rect(center=center)
        for radius in range(glow, 0, -1):
            ghost = font.render(text, True, tuple(max(0, c // (radius + 1)) for c in color))
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius)):
                self.screen.blit(ghost, rect.move(dx, dy))
        self.screen.blit(base, rect)

    def draw_clock(self) -> None:
        now = datetime.now()
        text = now.strftime("%I:%M:%S %p").lstrip("0")
        date_text = now.strftime("%A  %B %d, %Y").upper()
        if time.monotonic() > self.next_glitch:
            self.glitch_until = time.monotonic() + random.uniform(0.06, 0.18)
            self.next_glitch = time.monotonic() + random.uniform(2.5, 6.0)
        x = WIDTH // 2
        if time.monotonic() < self.glitch_until:
            x += random.randint(-7, 7)
        self.glow_text(text, self.clock_font, (x, 49), HEAD_GREEN, 2)
        self.glow_text(date_text, self.small_font, (WIDTH // 2, 78), GREEN, 1)

    def draw_xrp(self) -> None:
        self.glow_text("XRP", self.label_font, (WIDTH // 2, 218), GREEN, 1)
        if self.data.xrp_usd is None:
            value = self.data.error or "LOADING"
            font = self.label_font
        else:
            value = f"${self.data.xrp_usd:,.4f}"
            font = self.value_font
        self.glow_text(value, font, (WIDTH // 2, 255), HEAD_GREEN, 2)
        status = self.data.error if self.data.error else "LIVE FEED"
        self.glow_text(status, self.small_font, (WIDTH // 2, 287), GREEN, 1)

    def draw(self) -> None:
        self.screen.fill((0, 0, 0))
        self.engine.update()
        self.engine.draw(self.screen)
        self.draw_clock()
        self.draw_xrp()
        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            self.data.refresh()
            self.draw()
            self.clock.tick(FPS)


def main() -> int:
    try:
        MatrixOS().run()
        return 0
    except Exception as exc:
        print(f"Matrix OS failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
