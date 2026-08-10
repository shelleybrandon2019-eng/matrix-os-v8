#!/usr/bin/env python3
"""Ultra-dense Neo-style Matrix code vision for the 480x320 dashboard.

All code falls vertically. Density and luminance reveal a 3D code-world corridor,
while the screen stays packed with Matrix glyphs instead of empty black gaps.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

WIDTH = 480
HEIGHT = 320
VP_X = WIDTH // 2
VP_Y = int(HEIGHT * 0.50)

# Matrix rain only: half-width Japanese/Katakana glyphs, numbers, and symbols.
# Intentionally no A-Z/a-z characters.
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
            random.uniform(-HEIGHT * 0.18, HEIGHT * 1.18)
            if full_height
            else random.uniform(-HEIGHT * 1.75, -8)
        )
        self.speed = random.uniform(58.0, 168.0)
        self.length = random.randint(28, 54)
        self.brightness = random.uniform(0.76, 1.16)
        self.mutation = random.uniform(1.5, 4.6)
        self.hot = random.random() < 0.38
        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]


class DashboardRain:
    """Very dense vertical Matrix rain whose luminance reveals a 3D code world."""

    FONT_SIZES = (6, 7, 8, 10)
    PALETTE = (
        (0, 28, 8),
        (0, 43, 11),
        (0, 62, 16),
        (0, 88, 22),
        (0, 120, 29),
        (0, 160, 37),
        (0, 207, 48),
        (0, 255, 68),
    )
    HEAD = (225, 255, 230)

    INNER_LEFT = 178
    INNER_RIGHT = 302
    INNER_TOP = 86
    INNER_BOTTOM = 236

    def __init__(self) -> None:
        self.columns: List[CodeColumn] = []
        self.fonts: Dict[int, pygame.font.Font] = {
            size: _matrix_font(size) for size in self.FONT_SIZES
        }
        self.cache: Dict[Tuple[int, str, int, bool], pygame.Surface] = {}
        self.surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.geometry = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.time = 0.0

        # Four staggered layers. The first two are intentionally very tight so
        # the 480x320 panel reads as a wall of Matrix code rather than sparse rain.
        layer_specs = (
            (6, 6, 0.50, 0.62),
            (7, 8, 0.66, 0.76),
            (8, 11, 0.84, 0.92),
            (10, 17, 1.00, 1.02),
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
                    length=36,
                    spacing=y_spacing,
                    font_size=font_size,
                    glyphs=[],
                    brightness=1.0,
                    mutation=2.5,
                    hot=False,
                    layer=layer,
                )
                col.recycle(full_height=True)
                col.speed *= speed_mul
                col.brightness *= bright_mul
                self.columns.append(col)

        self._edges = [
            ((0, 0), (self.INNER_LEFT, self.INNER_TOP)),
            ((WIDTH - 1, 0), (self.INNER_RIGHT, self.INNER_TOP)),
            ((0, HEIGHT - 1), (self.INNER_LEFT, self.INNER_BOTTOM)),
            ((WIDTH - 1, HEIGHT - 1), (self.INNER_RIGHT, self.INNER_BOTTOM)),
            ((self.INNER_LEFT, self.INNER_TOP), (self.INNER_RIGHT, self.INNER_TOP)),
            ((self.INNER_RIGHT, self.INNER_TOP), (self.INNER_RIGHT, self.INNER_BOTTOM)),
            ((self.INNER_RIGHT, self.INNER_BOTTOM), (self.INNER_LEFT, self.INNER_BOTTOM)),
            ((self.INNER_LEFT, self.INNER_BOTTOM), (self.INNER_LEFT, self.INNER_TOP)),
        ]

    def _image(self, size: int, glyph: str, level: int, head: bool = False) -> pygame.Surface:
        level = max(0, min(7, level))
        key = (size, glyph, level, head)
        image = self.cache.get(key)
        if image is not None:
            return image
        color = self.HEAD if head else self.PALETTE[level]
        image = self.fonts[size].render(glyph, True, color)
        self.cache[key] = image
        return image

    @staticmethod
    def _distance_to_segment(px: float, py: float, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        qx = ax + t * dx
        qy = ay + t * dy
        return math.hypot(px - qx, py - qy)

    def _scene_gain(self, x: int, y: int) -> float:
        inside_back = (
            self.INNER_LEFT < x < self.INNER_RIGHT
            and self.INNER_TOP < y < self.INNER_BOTTOM
        )

        # The distant opening stays darker, but never turns into a large empty hole.
        gain = 0.72 if inside_back else 1.05

        nearest = min(self._distance_to_segment(x, y, a, b) for a, b in self._edges)
        if nearest < 2.4:
            gain += 1.30
        elif nearest < 5.5:
            gain += 0.80
        elif nearest < 11.0:
            gain += 0.34

        if not inside_back:
            dx = abs(x - VP_X) / max(1.0, WIDTH / 2)
            dy = abs(y - VP_Y) / max(1.0, HEIGHT / 2)
            gain += 0.15 * (dx + dy)
            gain += 0.11 * (0.5 + 0.5 * math.sin((x * 0.048) + (y * 0.034)))

        return max(0.40, min(2.50, gain))

    def update(self, dt: float, energy: float = 0.0) -> None:
        self.time += dt
        boost = 1.0 + max(0.0, min(1.0, energy)) * 0.22
        for col in self.columns:
            col.y += col.speed * boost * dt
            if col.glyphs and random.random() < dt * col.mutation:
                changes = 2 if random.random() < 0.32 else 1
                for _ in range(changes):
                    col.glyphs[random.randrange(len(col.glyphs))] = random.choice(MATRIX_CHARS)
            if col.y - col.length * col.spacing > HEIGHT + col.spacing:
                col.recycle()
                if col.layer == 0:
                    col.speed *= 0.50
                    col.brightness *= 0.62
                elif col.layer == 1:
                    col.speed *= 0.66
                    col.brightness *= 0.76
                elif col.layer == 2:
                    col.speed *= 0.84
                    col.brightness *= 0.92
                else:
                    col.brightness *= 1.02

    def _draw_geometry_glow(self) -> None:
        self.geometry.fill((0, 0, 0, 0))
        pulse = int(12 + 8 * (0.5 + 0.5 * math.sin(self.time * 1.1)))
        for a, b in self._edges:
            pygame.draw.line(self.geometry, (0, 125, 38, pulse), a, b, 1)

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        self.glow.fill((0, 0, 0, 0))
        self._draw_geometry_glow()

        energy_gain = 1.0 + max(0.0, min(1.0, energy)) * 0.20

        for col in self.columns:
            for index, glyph in enumerate(col.glyphs):
                y = int(col.y - index * col.spacing)
                if y < -col.spacing or y > HEIGHT:
                    continue

                # Long bright tails keep nearly every vertical lane populated.
                position = index / max(1, col.length - 1)
                trail = max(0.14, (1.0 - position) ** 0.86)
                scene = self._scene_gain(col.x, y)
                value = trail * col.brightness * scene * energy_gain
                level = max(0, min(7, int(value * 7.9)))

                near_edge = scene > 1.42
                is_head = index == 0 and col.hot and (near_edge or random.random() < 0.40)

                if is_head:
                    halo = self._image(col.font_size, glyph, 7, False)
                    halo.set_alpha(96)
                    self.glow.blit(halo, (col.x - 1, y))
                    self.glow.blit(halo, (col.x + 1, y))
                    self.glow.blit(halo, (col.x, y - 1))
                    halo.set_alpha(255)

                self.surface.blit(
                    self._image(col.font_size, glyph, level, is_head),
                    (col.x, y),
                )

        # Frequent pale-green flashes create the fuller Neo code-vision sparkle.
        for _ in range(4):
            if random.random() < 0.48:
                a, b = random.choice(self._edges)
                t = random.random()
                x = int(a[0] + (b[0] - a[0]) * t)
                y = int(a[1] + (b[1] - a[1]) * t)
                glyph = random.choice(MATRIX_CHARS)
                size = random.choice((7, 8, 10))
                self.glow.blit(self._image(size, glyph, 7, True), (x, y))

        self.geometry.set_alpha(95)
        destination.blit(self.geometry, (0, 0))
        self.geometry.set_alpha(255)

        self.glow.set_alpha(96)
        destination.blit(self.glow, (0, 0))
        self.glow.set_alpha(255)
        destination.blit(self.surface, (0, 0))
