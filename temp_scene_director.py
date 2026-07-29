#!/usr/bin/env python3
"""Matrix OS dashboard.

Pi display: permanent Matrix rain, large clock on top, and four live temperatures.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from typing import Optional

import pygame

from live_data import LiveData
from main import BLACK, FULLSCREEN, HEIGHT, WIDTH, CinematicRain, choose_font, choose_matrix_font, temp_color

FPS = 60
GREEN = (0, 255, 90)
DIM_GREEN = (0, 125, 52)
PANEL = (0, 8, 3, 185)


class Dashboard:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS - Clock and Temperature Dashboard")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()

        self.rain = CinematicRain()
        self.data = LiveData()
        self.data.refresh(force=True)

        clock_size = max(44, min(92, int(WIDTH * 0.22)))
        label_size = max(18, min(34, int(WIDTH * 0.075)))
        value_size = max(24, min(46, int(WIDTH * 0.105)))
        tiny_size = max(9, min(15, int(WIDTH * 0.035)))

        self.clock_font = choose_font(clock_size, bold=True)
        self.label_font = choose_matrix_font(label_size, bold=True)
        self.value_font = choose_font(value_size, bold=True)
        self.tiny_font = choose_matrix_font(tiny_size, bold=True)

        self.panel = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    @staticmethod
    def temperature_text(value: Optional[float]) -> str:
        return "--.-°F" if value is None else f"{value:.1f}°F"

    def draw_centered(self, text: str, font: pygame.font.Font, color, y: int) -> pygame.Rect:
        shadow = font.render(text, True, (0, 35, 12))
        image = font.render(text, True, color)
        rect = image.get_rect(center=(WIDTH // 2, y))
        self.screen.blit(shadow, rect.move(2, 3))
        self.screen.blit(image, rect)
        return rect

    def draw_row(self, label: str, value: Optional[float], y: int) -> None:
        margin = max(18, int(WIDTH * 0.07))
        label_image = self.label_font.render(label.upper(), True, GREEN)
        value_color = temp_color(value) if value is not None else DIM_GREEN
        value_image = self.value_font.render(self.temperature_text(value), True, value_color)

        label_shadow = self.label_font.render(label.upper(), True, (0, 35, 12))
        value_shadow = self.value_font.render(self.temperature_text(value), True, (0, 35, 12))

        label_rect = label_image.get_rect(midleft=(margin, y))
        value_rect = value_image.get_rect(midright=(WIDTH - margin, y))

        self.screen.blit(label_shadow, label_rect.move(2, 2))
        self.screen.blit(value_shadow, value_rect.move(2, 2))
        self.screen.blit(label_image, label_rect)
        self.screen.blit(value_image, value_rect)

        line_y = y + max(label_rect.height, value_rect.height) // 2 + 9
        pygame.draw.line(self.screen, (0, 90, 35), (margin, line_y), (WIDTH - margin, line_y), 1)

    def draw(self) -> None:
        self.screen.fill(BLACK)
        self.rain.draw(self.screen, 0.0)

        self.panel.fill((0, 0, 0, 0))
        pygame.draw.rect(
            self.panel,
            PANEL,
            (max(8, WIDTH // 30), max(8, HEIGHT // 40), WIDTH - max(16, WIDTH // 15), HEIGHT - max(16, HEIGHT // 20)),
            border_radius=max(8, WIDTH // 35),
        )
        self.screen.blit(self.panel, (0, 0))

        now = datetime.now()
        clock_text = now.strftime("%I:%M").lstrip("0")
        ampm = now.strftime("%p")

        clock_y = max(52, int(HEIGHT * 0.13))
        clock_rect = self.draw_centered(clock_text, self.clock_font, GREEN, clock_y)

        ampm_image = self.tiny_font.render(ampm, True, GREEN)
        ampm_rect = ampm_image.get_rect(midleft=(clock_rect.right + 7, clock_rect.centery + 7))
        self.screen.blit(ampm_image, ampm_rect)

        divider_y = int(HEIGHT * 0.235)
        pygame.draw.line(self.screen, GREEN, (int(WIDTH * 0.08), divider_y), (int(WIDTH * 0.92), divider_y), 2)

        rows = (
            ("Outside", self.data.outside_f),
            ("Inside", self.data.inside_f),
            ("Front Room", self.data.front_room_f),
            ("Bedroom", self.data.bedroom_f),
        )

        top = int(HEIGHT * 0.32)
        bottom = int(HEIGHT * 0.84)
        spacing = (bottom - top) // 3
        for index, (label, value) in enumerate(rows):
            self.draw_row(label, value, top + index * spacing)

        status = "MATRIX SYSTEM ONLINE"
        status_image = self.tiny_font.render(status, True, DIM_GREEN)
        status_rect = status_image.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.94)))
        self.screen.blit(status_image, status_rect)

        pygame.display.flip()

    def run(self) -> None:
        last = time.monotonic()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now

            self.data.refresh()
            self.rain.update(dt, 0.0)
            self.draw()
            self.timer.tick(FPS)


def main() -> int:
    try:
        Dashboard().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix dashboard failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
