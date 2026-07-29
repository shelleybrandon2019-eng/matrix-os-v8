#!/usr/bin/env python3
"""Matrix OS dashboard.

Pi display: permanent Matrix rain, compact clock, and four live temperatures.
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
ROW_SHADE = (0, 10, 4, 62)


class Dashboard:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS - Compact Clock and Temperature Dashboard")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()

        self.rain = CinematicRain()
        self.data = LiveData()
        self.data.refresh(force=True)

        clock_size = max(30, min(56, int(WIDTH * 0.145)))
        label_size = max(12, min(22, int(WIDTH * 0.048)))
        value_size = max(17, min(29, int(WIDTH * 0.068)))
        tiny_size = max(8, min(12, int(WIDTH * 0.027)))

        self.clock_font = choose_font(clock_size, bold=True)
        self.label_font = choose_matrix_font(label_size, bold=True)
        self.value_font = choose_font(value_size, bold=True)
        self.tiny_font = choose_matrix_font(tiny_size, bold=True)
        self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    @staticmethod
    def temperature_text(value: Optional[float]) -> str:
        return "--.-°F" if value is None else f"{value:.1f}°F"

    def draw_centered(self, text: str, font: pygame.font.Font, color, y: int) -> pygame.Rect:
        shadow = font.render(text, True, (0, 35, 12))
        image = font.render(text, True, color)
        rect = image.get_rect(center=(WIDTH // 2, y))
        self.screen.blit(shadow, rect.move(1, 2))
        self.screen.blit(image, rect)
        return rect

    def draw_row(self, label: str, value: Optional[float], y: int) -> None:
        margin = max(13, int(WIDTH * 0.055))
        row_height = max(32, int(HEIGHT * 0.105))

        self.overlay.fill((0, 0, 0, 0))
        pygame.draw.rect(
            self.overlay,
            ROW_SHADE,
            (margin - 6, y - row_height // 2, WIDTH - (margin * 2) + 12, row_height),
            border_radius=max(4, WIDTH // 60),
        )
        self.screen.blit(self.overlay, (0, 0))

        label_image = self.label_font.render(label.upper(), True, GREEN)
        value_color = temp_color(value) if value is not None else DIM_GREEN
        value_text = self.temperature_text(value)
        value_image = self.value_font.render(value_text, True, value_color)

        label_shadow = self.label_font.render(label.upper(), True, (0, 35, 12))
        value_shadow = self.value_font.render(value_text, True, (0, 35, 12))

        label_rect = label_image.get_rect(midleft=(margin, y))
        value_rect = value_image.get_rect(midright=(WIDTH - margin, y))

        self.screen.blit(label_shadow, label_rect.move(1, 1))
        self.screen.blit(value_shadow, value_rect.move(1, 1))
        self.screen.blit(label_image, label_rect)
        self.screen.blit(value_image, value_rect)

    def draw(self) -> None:
        self.screen.fill(BLACK)
        self.rain.draw(self.screen, 0.12)

        now = datetime.now()
        clock_text = now.strftime("%I:%M").lstrip("0")
        ampm = now.strftime("%p")

        clock_y = max(35, int(HEIGHT * 0.09))
        clock_rect = self.draw_centered(clock_text, self.clock_font, GREEN, clock_y)

        ampm_image = self.tiny_font.render(ampm, True, GREEN)
        ampm_rect = ampm_image.get_rect(midleft=(clock_rect.right + 5, clock_rect.centery + 4))
        self.screen.blit(ampm_image, ampm_rect)

        divider_y = int(HEIGHT * 0.17)
        pygame.draw.line(self.screen, (0, 170, 65), (int(WIDTH * 0.11), divider_y), (int(WIDTH * 0.89), divider_y), 1)

        rows = (
            ("Outside", self.data.outside_f),
            ("Inside", self.data.inside_f),
            ("Front Room", self.data.front_room_f),
            ("Bedroom", self.data.bedroom_f),
        )

        top = int(HEIGHT * 0.29)
        bottom = int(HEIGHT * 0.80)
        spacing = (bottom - top) // 3
        for index, (label, value) in enumerate(rows):
            self.draw_row(label, value, top + index * spacing)

        status_image = self.tiny_font.render("MATRIX ONLINE", True, DIM_GREEN)
        status_rect = status_image.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.91)))
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
            self.rain.update(dt, 0.12)
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
