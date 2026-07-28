#!/usr/bin/env python3
"""Matrix OS V10 clean baseline.

Pi owns cinematic Matrix rain and giant OUTSIDE/INSIDE reveals only.
ESP32 owns the clock. No placeholder scenes are rendered here.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

import pygame

from live_data import LiveData
from main import (
    BLACK,
    FULLSCREEN,
    HEIGHT,
    WIDTH,
    CinematicRain,
    RainTextTransition,
    choose_font,
    choose_matrix_font,
    temp_color,
)

FPS = 60
IDLE_SECONDS = float(os.getenv("MATRIX_TEMP_IDLE_SECONDS", "6.0"))
HOLD_SECONDS = float(os.getenv("MATRIX_TEMP_HOLD_SECONDS", "5.0"))


class Director:
    EVENTS = (("outside", "OUTSIDE"), ("inside", "INSIDE"))

    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS V10 - Clean Temperature Cinema")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()

        self.rain = CinematicRain()
        self.data = LiveData()
        self.data.refresh(force=True)

        self.title_font = choose_font(68, bold=True)
        self.value_font = choose_font(96, bold=True)
        self.tiny_font = choose_matrix_font(9, bold=True)

        self.event_index = 0
        self.phase = "idle"
        self.phase_started = time.monotonic()
        self.transition: Optional[RainTextTransition] = None

    def elapsed(self) -> float:
        return time.monotonic() - self.phase_started

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.phase_started = time.monotonic()

    def event_data(self):
        key, title = self.EVENTS[self.event_index]
        value = self.data.outside_f if key == "outside" else self.data.inside_f
        text = "--°F" if value is None else f"{value:.0f}°F"
        return title, text, temp_color(value)

    def begin_form(self) -> None:
        self.data.refresh(force=True)
        title, value, accent = self.event_data()
        self.transition = RainTextTransition(
            self.rain,
            title,
            value,
            accent,
            self.title_font,
            self.value_font,
            self.tiny_font,
        )
        self.set_phase("form")

    def finish_cycle(self) -> None:
        self.transition = None
        self.event_index = (self.event_index + 1) % len(self.EVENTS)
        self.set_phase("idle")

    def update(self, dt: float) -> None:
        self.data.refresh()
        energy = 0.28 if self.phase in ("form", "melt") else 0.0
        self.rain.update(dt, energy)

        elapsed = self.elapsed()
        if self.phase == "idle":
            if elapsed >= IDLE_SECONDS:
                self.begin_form()
        elif self.phase == "form" and self.transition is not None:
            self.transition.update(dt)
            if self.transition.form_done():
                self.set_phase("hold")
        elif self.phase == "hold" and self.transition is not None:
            if elapsed >= HOLD_SECONDS:
                self.transition.start_melt()
                self.set_phase("melt")
        elif self.phase == "melt" and self.transition is not None:
            self.transition.update(dt)
            if self.transition.melt_done():
                self.finish_cycle()

    def draw(self) -> None:
        self.screen.fill(BLACK)
        energy = 0.24 if self.phase in ("form", "melt") else 0.0
        self.rain.draw(self.screen, energy)
        if self.transition is not None and self.phase in ("form", "hold", "melt"):
            self.transition.draw(self.screen)
        pygame.display.flip()

    def run(self) -> None:
        last = time.monotonic()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                        if self.phase == "idle":
                            self.begin_form()
                        elif self.phase == "hold" and self.transition is not None:
                            self.transition.start_melt()
                            self.set_phase("melt")

            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now
            self.update(dt)
            self.draw()
            self.timer.tick(FPS)


def main() -> int:
    try:
        Director().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix OS clean temperature director failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
