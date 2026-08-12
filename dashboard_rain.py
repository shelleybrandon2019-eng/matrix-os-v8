#!/usr/bin/env python3
"""Fast, clean Neo-style Matrix rain for the 480x320 dashboard.

Pure vertical code rain only: no tunnel, oval, corridor, perspective geometry,
or hidden background image. Fewer streams use longer tails so the rain reads
as falling streaks instead of a wall of glyphs.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

WIDTH = 480
HEIGHT = 320

MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "ｦｧｨｩｪｫｬｭｮｯｰﾞﾟ"
    "0123456789@#$%&*+=<>?/\\|:;.-_"
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
            random.uniform(-HEIGHT * 0.08, HEIGHT * 1.12)
            if full_height
            else random.uniform(-HEIGHT * 0.42, -6)
        )
        self.speed = random.uniform(68.0, 178.0)
        self.length = random.randint(46, 78)
        self.brightness = random.uniform(0.82, 1.14)
        self.mutation = random.uniform(1.35, 3.8)
        self.hot = random.random() < 0.72
        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]


class DashboardRain:
    """Fewer falling streams with long pale-head-to-green tails."""

    FONT_SIZES = (6, 7, 8, 10)
    PALETTE = (
        (0, 20, 6),
        (0, 32, 9),
        (0, 48, 12),
        (0, 68, 16),
        (0, 94, 22),
        (0, 128, 29),
        (0, 170, 38),
        (0, 222, 56),
    )

    LEAD_COLORS = (
        (224, 255, 230),
        (196, 255, 210),
        (164, 255, 188),
        (128, 255, 164),
        (90, 252, 137),
        (50, 246, 108),
        (16, 232, 79),
    )

    def __init__(self) -> None:
        self.columns: List[CodeColumn] = []
        self.fonts: Dict[int, pygame.font.Font] = {
            size: _matrix_font(size) for size in self.FONT_SIZES
        }
        self.cache: Dict[Tuple[int, str, int, int], pygame.Surface] = {}
        self.surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.time = 0.0

        layer_specs = (
            (6, 7, 0.54, 0.70),
            (7, 9, 0.70, 0.82),
            (8, 13, 0.88, 0.96),
            (10, 19, 1.00, 1.04),
        )

        for layer, (font_size, x_spacing, speed_mul, bright_mul) in enumerate(layer_specs):
            font = self.fonts[font_size]
            y_spacing = max(font_size, font.get_linesize() - 3)
            offset = random.randint(0, x_spacing - 1)

            for x in range(-x_spacing + offset, WIDTH + x_spacing, x_spacing):
                col = CodeColumn(
                    x=x,
                    y=0.0,
                    speed=100.0,
                    length=58,
                    spacing=y_spacing,
                    font_size=font_size,
                    glyphs=[],
                    brightness=1.0,
                    mutation=2.2,
                    hot=False,
                    layer=layer,
                )
                col.recycle(full_height=True)
                col.speed *= speed_mul
                col.brightness *= bright_mul
                self.columns.append(col)

    def _image(self, size: int, glyph: str, level: int, lead_index: int = -1) -> pygame.Surface:
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
        boost = 1.08 + max(0.0, min(1.0, energy)) * 0.14
        multipliers = (
            (0.54, 0.70),
            (0.70, 0.82),
            (0.88, 0.96),
            (1.00, 1.04),
        )

        for col in self.columns:
            col.y += col.speed * boost * dt

            if col.glyphs and random.random() < dt * col.mutation:
                changes = 2 if random.random() < 0.22 else 1
                for _ in range(changes):
                    col.glyphs[random.randrange(len(col.glyphs))] = random.choice(MATRIX_CHARS)

            if col.y - col.length * col.spacing > HEIGHT + col.spacing:
                col.recycle()
                speed_mul, bright_mul = multipliers[col.layer]
                col.speed *= speed_mul
                col.brightness *= bright_mul

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        energy_gain = 1.0 + max(0.0, min(1.0, energy)) * 0.10

        for col in self.columns:
            for index, glyph in enumerate(col.glyphs):
                y = int(col.y - index * col.spacing)
                if y < -col.spacing or y > HEIGHT:
                    continue

                position = index / max(1, col.length - 1)
                trail = max(0.08, (1.0 - position) ** 0.72)
                value = trail * col.brightness * energy_gain
                level = max(0, min(7, int(value * 7.45)))

                lead_index = index if col.hot and index < len(self.LEAD_COLORS) else -1

                self.surface.blit(
                    self._image(col.font_size, glyph, level, lead_index),
                    (col.x, y),
                )

        destination.blit(self.surface, (0, 0))
