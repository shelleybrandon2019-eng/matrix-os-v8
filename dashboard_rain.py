#!/usr/bin/env python3
"""Large sparse Dozer-style Matrix rain for the 480x320 dashboard.

Pure vertical code rain only. Fewer streams, larger glyphs, and long white-to-green
tails make the display read like the Matrix operator screens instead of a wall of
small text.
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
            random.uniform(-HEIGHT * 0.10, HEIGHT * 1.10)
            if full_height
            else random.uniform(-HEIGHT * 0.50, -8)
        )
        self.speed = random.uniform(56.0, 142.0)
        self.length = random.randint(52, 86)
        self.brightness = random.uniform(0.84, 1.15)
        self.mutation = random.uniform(1.15, 3.2)
        self.hot = random.random() < 0.82
        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]


class DashboardRain:
    """Sparse, oversized Matrix streams with long luminous tracking tails."""

    FONT_SIZES = (9, 11, 13, 15)

    PALETTE = (
        (0, 16, 5),
        (0, 26, 7),
        (0, 40, 10),
        (0, 58, 14),
        (0, 82, 19),
        (0, 112, 25),
        (0, 152, 34),
        (0, 205, 50),
    )

    LEAD_COLORS = (
        (232, 255, 236),
        (214, 255, 224),
        (192, 255, 207),
        (164, 255, 187),
        (132, 255, 164),
        (98, 252, 141),
        (66, 246, 116),
        (34, 237, 91),
        (8, 224, 70),
    )

    def __init__(self) -> None:
        self.columns: List[CodeColumn] = []
        self.fonts: Dict[int, pygame.font.Font] = {
            size: _matrix_font(size) for size in self.FONT_SIZES
        }
        self.cache: Dict[Tuple[int, str, int, int], pygame.Surface] = {}
        self.surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.time = 0.0

        # Roughly half the old stream count, but each stream is much larger and longer.
        # This is closer to the chunky operator-screen code look.
        layer_specs = (
            (9, 11, 0.60, 0.72),
            (11, 16, 0.76, 0.84),
            (13, 23, 0.90, 0.96),
            (15, 32, 1.00, 1.04),
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
                    length=64,
                    spacing=y_spacing,
                    font_size=font_size,
                    glyphs=[],
                    brightness=1.0,
                    mutation=2.0,
                    hot=False,
                    layer=layer,
                )
                col.recycle(full_height=True)
                col.speed *= speed_mul
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
        boost = 1.04 + max(0.0, min(1.0, energy)) * 0.12
        multipliers = (
            (0.60, 0.72),
            (0.76, 0.84),
            (0.90, 0.96),
            (1.00, 1.04),
        )

        for col in self.columns:
            col.y += col.speed * boost * dt

            if col.glyphs and random.random() < dt * col.mutation:
                changes = 2 if random.random() < 0.16 else 1
                for _ in range(changes):
                    col.glyphs[random.randrange(len(col.glyphs))] = random.choice(MATRIX_CHARS)

            if col.y - col.length * col.spacing > HEIGHT + col.spacing:
                col.recycle()
                speed_mul, bright_mul = multipliers[col.layer]
                col.speed *= speed_mul
                col.brightness *= bright_mul

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        energy_gain = 1.0 + max(0.0, min(1.0, energy)) * 0.08

        for col in self.columns:
            for index, glyph in enumerate(col.glyphs):
                y = int(col.y - index * col.spacing)
                if y < -col.spacing or y > HEIGHT:
                    continue

                position = index / max(1, col.length - 1)

                # Long smooth tails: the visible streak hangs behind the bright leader.
                trail = max(0.055, (1.0 - position) ** 0.56)
                value = trail * col.brightness * energy_gain
                level = max(0, min(7, int(value * 7.3)))

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
