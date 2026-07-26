#!/usr/bin/env python3
"""Original Matrix V2-style rain adapted to the current Matrix OS interface."""

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

MATRIX_GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789"
ASCII_GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|:;[]{}()"

# Keep these exported colors for the current page and transition modules.
GREEN = (0, 255, 70)
DIM_GREEN = (0, 55, 22)
MID_GREEN = (0, 165, 48)
HEAD_GREEN = (225, 255, 232)

# Exact V2 rain palette.
RAIN_GREEN = (0, 255, 0)
RAIN_BRIGHT = (210, 255, 210)
TIME_H = 62
COLUMN_SPACING = 18
CHAR_SPACING = 18


def font_supports_matrix_glyphs(font: pygame.font.Font) -> bool:
    """Reject fonts that render Japanese glyphs as identical square placeholders."""
    samples = [font.render(char, True, (255, 255, 255)) for char in "ｱｶｻﾀﾅ"]
    signatures = [
        (surface.get_size(), pygame.image.tostring(surface, "RGBA"))
        for surface in samples
    ]
    return len(set(signatures)) > 1


@dataclass
class Stream:
    """One original V2 rain column."""

    x: int
    y: float
    speed: float
    length: int
    flash: int = 0

    def reset(self, height: int) -> None:
        self.y = float(random.randint(-height, 0))
        self.speed = float(random.randint(90, 260))
        self.length = random.randint(8, 20)
        self.flash = 0


class MatrixEngine:
    """Single-layer V2 rain: sharp heads and clean character-chain trails."""

    def __init__(self, width: int, height: int, font: pygame.font.Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.glyph_set = (
            MATRIX_GLYPHS if font_supports_matrix_glyphs(font) else ASCII_GLYPHS
        )

        # The original V2 used fixed 18-pixel spacing for both columns and glyphs.
        self.char_w = COLUMN_SPACING
        self.char_h = CHAR_SPACING
        self.streams: List[Stream] = []
        self._glyph_cache: Dict[Tuple[str, Tuple[int, int, int]], pygame.Surface] = {}
        self._last_update = time.monotonic()

        for x in range(0, width, COLUMN_SPACING):
            stream = Stream(x=x, y=0.0, speed=120.0, length=12)
            stream.reset(height)
            self.streams.append(stream)

    def _glyph_image(
        self,
        glyph: str,
        color: Tuple[int, int, int],
    ) -> pygame.Surface:
        key = (glyph, color)
        image = self._glyph_cache.get(key)
        if image is None:
            image = self.font.render(glyph, True, color)
            self._glyph_cache[key] = image
        return image

    def trigger_cinematic_flash(self, strength: int = 76) -> None:
        """Reuse the existing transition hook to flash a few V2 rain heads."""
        if not self.streams:
            return

        count = min(len(self.streams), max(1, strength // 24))
        for stream in random.sample(self.streams, count):
            stream.flash = 45

    def update(self, intensity: float = 1.0) -> None:
        now = time.monotonic()
        dt = min(0.05, max(0.0, now - self._last_update))
        self._last_update = now

        for stream in self.streams:
            stream.y += stream.speed * dt * intensity

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

                # V2 intentionally changes every glyph on every frame.
                glyph = random.choice(self.glyph_set)

                if index == 0:
                    color = RAIN_BRIGHT if stream.flash > 0 else RAIN_GREEN
                else:
                    color = (0, max(35, 190 - index * 11), 0)

                surface.blit(
                    self._glyph_image(glyph, color),
                    (stream.x, int(y)),
                )
