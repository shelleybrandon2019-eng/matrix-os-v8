#!/usr/bin/env python3
"""Large sparse Dozer-style Matrix rain for the 480x320 dashboard.

Pure vertical code rain only. Very few streams, oversized Matrix glyphs, and long
white-to-green tails make the display read like the operator screens instead of a
wall of tiny text. Rain glyphs are Matrix characters only: no numeric digits.

Motion follows the classic Matrix-rain cadence: each stream advances about
0.4-1.75 character rows per frame at 60 FPS, scaled to its actual glyph spacing.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

WIDTH = 480
HEIGHT = 320

# Matrix-style kana only. No Arabic digits or ASCII punctuation in the rain.
MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
    "ﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝｦｧｨｩｪｫｬｭｮｯｰﾞﾟ"
)


def _matrix_font(size: int) -> pygame.font.Font:
    for name in (
        "Noto Sans Mono CJK JP",
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAGothic",
        "TakaoGothic",
        "VL Gothic",
        "DejaVu Sans Mono",
        "monospace",
    ):
        path = pygame.font.match_font(name, bold=True)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


@dataclass
class CodeColumn:
    x: int
    y: float
    speed: float
    length: int
    spacing: int
    font_size: int
    glyphs: List[str]
    brightness: float
    mutation: float
    hot: bool
    layer: int

    def recycle(self, *, full_height: bool = False) -> None:
        self.y = (
            random.uniform(-HEIGHT * 0.12, HEIGHT * 1.08)
            if full_height
            else random.uniform(-HEIGHT * 0.58, -10)
        )

        # Match the cadence of the reference Matrix implementation:
        # drops += random.uniform(0.8, 3.5) * 0.5 each 60 Hz frame.
        # Converting character rows/frame to pixels/second gives:
        # row_speed * 0.5 * 60 * actual glyph spacing.
        row_speed = random.uniform(0.8, 3.5)
        self.speed = row_speed * 30.0 * self.spacing

        self.length = random.randint(50, 84)
        self.brightness = random.uniform(0.84, 1.15)
        self.mutation = random.uniform(2.4, 3.4)
        self.hot = random.random() < 0.84
        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]


class DashboardRain:
    """Sparse oversized Matrix streams with long luminous tracking tails."""

    FONT_SIZES = (11, 14, 17, 20)
    PALETTE = (
        (0, 14, 4),
        (0, 22, 6),
        (0, 34, 9),
        (0, 48, 12),
        (0, 68, 17),
        (0, 96, 23),
        (0, 136, 31),
        (0, 192, 47),
    )

    LEAD_COLORS = (
        (234, 255, 238),
        (220, 255, 228),
        (204, 255, 216),
        (182, 255, 201),
        (154, 255, 181),
        (120, 252, 156),
        (84, 246, 128),
        (46, 235, 98),
        (12, 220, 72),
    )

    def __init__(self) -> None:
        self.columns: List[CodeColumn] = []
        self.fonts: Dict[int, pygame.font.Font] = {
            size: _matrix_font(size) for size in self.FONT_SIZES
        }
        self.cache: Dict[Tuple[int, str, int, int], pygame.Surface] = {}
        self.surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.time = 0.0

        # Keep Brandon's sparse, oversized operator-screen look. Speed is no longer
        # tied to these visual layers; every column independently gets the movie-like
        # 0.8-3.5 row-speed range when it is recycled.
        layer_specs = (
            (11, 18, 0.74),
            (14, 26, 0.86),
            (17, 36, 0.98),
            (20, 48, 1.05),
        )

        for layer, (font_size, x_spacing, bright_mul) in enumerate(layer_specs):
            font = self.fonts[font_size]
            y_spacing = max(font_size, font.get_linesize() - 2)
            offset = random.randint(0, x_spacing - 1)

            for x in range(-x_spacing + offset, WIDTH + x_spacing, x_spacing):
                col = CodeColumn(
                    x=x,
                    y=0.0,
                    speed=100.0,
                    length=62,
                    spacing=y_spacing,
                    font_size=font_size,
                    glyphs=[],
                    brightness=1.0,
                    mutation=3.0,
                    hot=False,
                    layer=layer,
                )
                col.recycle(full_height=True)
                col.brightness *= bright_mul
                self.columns.append(col)

    def _image(
        self,
        size: int,
        glyph: str,
        level: int,
        lead_index: int = -1,
    ) -> pygame.Surface:
        level = max(0, min(7, level))
        lead_key = max(-1, min(len(self.LEAD_COLORS) - 1, lead_index))
        key = (size, glyph, level, lead_key)

        image = self.cache.get(key)
        if image is not None:
            return image

        color = self.LEAD_COLORS[lead_key] if lead_key >= 0 else self.PALETTE[level]
        image = self.fonts[size].render(glyph, True, color)
        self.cache[key] = image
        return image

    def update(self, dt: float, energy: float = 0.0) -> None:
        self.time += dt

        # Keep speed constant through normal rain and temperature reveals. The
        # reference Matrix effect gets its life from independent column speeds,
        # not from globally speeding up/slowing down the whole screen.
        for col in self.columns:
            col.y += col.speed * dt

            # The reference changes a glyph with ~5% probability each 60 Hz frame,
            # roughly three mutations per second per stream.
            if col.glyphs and random.random() < dt * col.mutation:
                col.glyphs[random.randrange(len(col.glyphs))] = random.choice(MATRIX_CHARS)

            if col.y - col.length * col.spacing > HEIGHT + col.spacing:
                col.recycle()
                bright_mul = (0.74, 0.86, 0.98, 1.05)[col.layer]
                col.brightness *= bright_mul

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        energy_gain = 1.0 + max(0.0, min(1.0, energy)) * 0.07

        for col in self.columns:
            for index, glyph in enumerate(col.glyphs):
                y = int(col.y - index * col.spacing)
                if y < -col.spacing or y > HEIGHT:
                    continue

                position = index / max(1, col.length - 1)

                # Long hanging tails behind a bright head.
                trail = max(0.045, (1.0 - position) ** 0.52)
                value = trail * col.brightness * energy_gain
                level = max(0, min(7, int(value * 7.2)))

                lead_index = (
                    index
                    if col.hot and index < len(self.LEAD_COLORS)
                    else -1
                )

                self.surface.blit(
                    self._image(col.font_size, glyph, level, lead_index),
                    (col.x, y),
                )

        destination.blit(self.surface, (0, 0))
