#!/usr/bin/env python3
"""Neo-style Matrix code vision for the 480x320 dashboard.

Vertical Matrix rain stays vertical, while brightness/density reveal a 3D corridor
(walls, ceiling, floor, and a darker doorway) like the classic code-vision scene.
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
VP_Y = int(HEIGHT * 0.49)

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

    def recycle(self, *, full_height: bool = False) -> None:
        self.y = random.uniform(-HEIGHT * 0.3, HEIGHT * 1.1) if full_height else random.uniform(-HEIGHT * 1.5, -8)
        self.speed = random.uniform(62.0, 145.0)
        self.length = random.randint(18, 38)
        self.brightness = random.uniform(0.62, 1.0)
        self.mutation = random.uniform(1.2, 3.6)
        self.hot = random.random() < 0.27
        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]


class DashboardRain:
    """Vertical Matrix rain whose luminance reveals a 3D code-world corridor."""

    FONT_SIZES = (7, 8, 9, 10)
    PALETTE = (
        (0, 16, 5),
        (0, 27, 8),
        (0, 43, 12),
        (0, 64, 17),
        (0, 91, 23),
        (0, 128, 31),
        (0, 176, 42),
        (0, 232, 57),
    )
    HEAD = (215, 255, 220)

    # Back opening / vanishing-area geometry.
    INNER_LEFT = 181
    INNER_RIGHT = 299
    INNER_TOP = 89
    INNER_BOTTOM = 232

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

        # Dense, staggered vertical rain. All movement is downward on screen.
        for layer, (font_size, x_spacing) in enumerate(((7, 9), (8, 13), (10, 21))):
            font = self.fonts[font_size]
            y_spacing = max(font_size + 1, font.get_linesize() - 2)
            offset = random.randint(0, x_spacing - 1)
            for x in range(-x_spacing + offset, WIDTH + x_spacing, x_spacing):
                col = CodeColumn(
                    x=x,
                    y=0.0,
                    speed=90.0,
                    length=25,
                    spacing=y_spacing,
                    font_size=font_size,
                    glyphs=[],
                    brightness=1.0,
                    mutation=2.0,
                    hot=False,
                )
                col.recycle(full_height=True)
                # Back layer is dimmer/slower; foreground layer is brighter/faster.
                if layer == 0:
                    col.speed *= 0.66
                    col.brightness *= 0.48
                elif layer == 1:
                    col.speed *= 0.84
                    col.brightness *= 0.72
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
        """Brightness map: code itself reveals the corridor geometry."""
        inside_back = (
            self.INNER_LEFT < x < self.INNER_RIGHT
            and self.INNER_TOP < y < self.INNER_BOTTOM
        )

        # Outer corridor surfaces are active; the distant opening is darker.
        gain = 0.46 if inside_back else 0.94

        # Strong code ridges at perspective corners and doorway edges.
        nearest = min(self._distance_to_segment(x, y, a, b) for a, b in self._edges)
        if nearest < 2.2:
            gain += 1.20
        elif nearest < 5.0:
            gain += 0.72
        elif nearest < 10.0:
            gain += 0.28

        # Subtle surface bands give walls/floor/ceiling depth without wireframe lines.
        if not inside_back:
            dx = abs(x - VP_X) / max(1.0, WIDTH / 2)
            dy = abs(y - VP_Y) / max(1.0, HEIGHT / 2)
            gain += 0.12 * (dx + dy)
            gain += 0.08 * (0.5 + 0.5 * math.sin((x * 0.045) + (y * 0.03)))

        return max(0.18, min(2.25, gain))

    def update(self, dt: float, energy: float = 0.0) -> None:
        self.time += dt
        boost = 1.0 + max(0.0, min(1.0, energy)) * 0.16
        for col in self.columns:
            col.y += col.speed * boost * dt
            if col.glyphs and random.random() < dt * col.mutation:
                changes = 2 if random.random() < 0.22 else 1
                for _ in range(changes):
                    col.glyphs[random.randrange(len(col.glyphs))] = random.choice(MATRIX_CHARS)
            if col.y - col.length * col.spacing > HEIGHT + col.spacing:
                col.recycle()

    def _draw_geometry_glow(self) -> None:
        """Very faint code-world edges; glyph brightness does most of the work."""
        self.geometry.fill((0, 0, 0, 0))
        pulse = int(16 + 7 * (0.5 + 0.5 * math.sin(self.time * 1.1)))
        for a, b in self._edges:
            pygame.draw.line(self.geometry, (0, 125, 38, pulse), a, b, 1)

        # Tiny distant portal/doorway glow.
        rect = pygame.Rect(
            self.INNER_LEFT,
            self.INNER_TOP,
            self.INNER_RIGHT - self.INNER_LEFT,
            self.INNER_BOTTOM - self.INNER_TOP,
        )
        pygame.draw.rect(self.geometry, (0, 92, 26, 20), rect, 1)

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        self.glow.fill((0, 0, 0, 0))
        self._draw_geometry_glow()

        for col in self.columns:
            for index, glyph in enumerate(col.glyphs):
                y = int(col.y - index * col.spacing)
                if y < -col.spacing or y > HEIGHT:
                    continue

                # Classic falling-string fade: bright lead glyph, then luminous tail.
                position = index / max(1, col.length - 1)
                trail = max(0.035, (1.0 - position) ** 1.30)
                scene = self._scene_gain(col.x, y)
                value = trail * col.brightness * scene
                level = max(0, min(7, int(value * 7.0)))

                near_edge = scene > 1.40
                is_head = index == 0 and col.hot and (near_edge or random.random() < 0.28)

                if is_head:
                    halo = self._image(col.font_size, glyph, 7, False)
                    halo.set_alpha(82)
                    self.glow.blit(halo, (col.x - 1, y))
                    self.glow.blit(halo, (col.x + 1, y))
                    self.glow.blit(halo, (col.x, y - 1))
                    halo.set_alpha(255)

                self.surface.blit(
                    self._image(col.font_size, glyph, level, is_head),
                    (col.x, y),
                )

        # Sparse white-green code flares along world edges, like Neo's code vision.
        if random.random() < 0.22:
            a, b = random.choice(self._edges)
            t = random.random()
            x = int(a[0] + (b[0] - a[0]) * t)
            y = int(a[1] + (b[1] - a[1]) * t)
            glyph = random.choice(MATRIX_CHARS)
            size = random.choice((8, 9, 10))
            flare = self._image(size, glyph, 7, True)
            self.glow.blit(flare, (x, y))

        self.geometry.set_alpha(150)
        destination.blit(self.geometry, (0, 0))
        self.geometry.set_alpha(255)

        self.glow.set_alpha(78)
        destination.blit(self.glow, (0, 0))
        self.glow.set_alpha(255)
        destination.blit(self.surface, (0, 0))
