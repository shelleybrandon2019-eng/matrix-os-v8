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


def choose_font(size: int) -> pygame.font.Font:
    preferred = ["Liberation Mono", "DejaVu Sans Mono", "Noto Sans Mono", "monospace"]
    for name in preferred:
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def format_temp(value):
    return "--°F" if value is None else f"{value:.1f}°F"


class MatrixOS:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.rain_font = choose_font(15)
        self.clock_font = choose_font(48)
        self.label_font = choose_font(19)
        self.value_font = choose_font(42)

        self.engine = MatrixEngine(WIDTH, HEIGHT, self.rain_font)
        self.data = LiveData()
        self.data.refresh(force=True)
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
        now = datetime.now()
        text = now.strftime("%I:%M:%S %p").lstrip("0")
        if time.monotonic() > self.next_glitch:
            self.glitch_until = time.monotonic() + random.uniform(0.05, 0.14)
            self.next_glitch = time.monotonic() + random.uniform(3.0, 7.0)
        x = WIDTH // 2 + (random.randint(-4, 4) if time.monotonic() < self.glitch_until else 0)
        self.glow_text(text, self.clock_font, (x, 42), HEAD_GREEN, 2)

    def draw_temperatures(self):
        items = [
            ("FRONT ROOM", self.data.front_room_f, 120, 137),
            ("BEDROOM", self.data.bedroom_f, 360, 137),
            ("INSIDE", self.data.inside_f, 120, 257),
            ("OUTSIDE", self.data.outside_f, 360, 257),
        ]
        for label, value, x, y in items:
            self.glow_text(label, self.label_font, (x, y - 28), GREEN, 1)
            self.glow_text(format_temp(value), self.value_font, (x, y + 15), HEAD_GREEN, 2)

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.engine.update()
        self.engine.draw(self.screen)
        self.draw_clock()
        self.draw_temperatures()
        pygame.display.flip()

    def run(self):
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
