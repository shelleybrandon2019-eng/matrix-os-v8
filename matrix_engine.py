#!/usr/bin/env python3
"""Literal Matrix V2 rain loop adapted only to the current engine interface."""

import random
import time
from dataclasses import dataclass
from typing import List

import pygame

# Keep these exported colors for the current pages and transition module.
GREEN = (0, 255, 70)
DIM_GREEN = (0, 55, 22)
MID_GREEN = (0, 165, 48)
HEAD_GREEN = (225, 255, 232)

# These values are copied directly from v2_matrix.py.
MATRIX_GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789"
RAIN_GREEN = (0, 255, 0)
RAIN_BRIGHT = (210, 255, 210)
TIME_H = 62
COLUMN_SPACING = 18
CHAR_SPACING = 18
RAIN_FONT_SIZE = 18


@dataclass
class Stream:
    """One original V2 Drop object."""

    x: int
    y: float = 0.0
    speed: float = 120.0
    length: int = 12
    flash: int = 0

    def reset(self, height: int) -> None:
        self.y = float(random.randint(-height, 0))
        self.speed = float(random.randint(90, 260))
        self.length = random.randint(8, 20)
        self.flash = 0


class MatrixEngine:
    """The V2 rain code, without cinematic layers, caching, or fallbacks."""

    def __init__(self, width: int, height: int, _unused_font: pygame.font.Font) -> None:
        self.width = width
        self.height = height

        # Exact V2 font declaration. V2 never switched to an ASCII fallback.
        self.font = pygame.font.SysFont(
            "Noto Sans Mono CJK JP,DejaVu Sans Mono,monospace",
            RAIN_FONT_SIZE,
            bold=True,
        )
        self.glyph_set = MATRIX_GLYPHS
        self.char_w = COLUMN_SPACING
        self.char_h = CHAR_SPACING
        self.streams: List[Stream] = []
        self._last_update = time.monotonic()

        # Exact V2 layout: 0, 18, 36, 54 ...
        for x in range(0, width, COLUMN_SPACING):
            stream = Stream(x=x)
            stream.reset(height)
            self.streams.append(stream)

    def trigger_cinematic_flash(self, strength: int = 76) -> None:
        """The V2 reveal flashes one selected drop for 45 frames."""
        del strength
        if self.streams:
            random.choice(self.streams).flash = 45

    def update(self, _unused_intensity: float = 1.0) -> None:
        # V2 moves by speed * real frame delta. Ignore V9's speed multiplier.
        now = time.monotonic()
        dt = min(0.05, max(0.0, now - self._last_update))
        self._last_update = now

        for stream in self.streams:
            stream.y += stream.speed * dt

            if stream.flash > 0:
                stream.flash -= 1

            if stream.y > self.height + stream.length * CHAR_SPACING:
                stream.reset(self.height)

    def draw(self, surface: pygame.Surface) -> None:
        for stream in self.streams:
            for index in range(stream.length):
                y = stream.y - index * CHAR_SPACING
                if y < TIME_H or y > self.height:
                    continue

                # This is intentionally rendered fresh every frame, exactly like V2.
                glyph = random.choice(MATRIX_GLYPHS)
                if index == 0:
                    color = RAIN_BRIGHT if stream.flash > 0 else RAIN_GREEN
                else:
                    color = (0, max(35, 190 - index * 11), 0)

                surface.blit(
                    self.font.render(glyph, True, color),
                    (stream.x, int(y)),
                )
