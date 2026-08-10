#!/usr/bin/env python3
"""Animated Matrix-code perspective tunnel for the 480x320 dashboard."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

WIDTH = 480
HEIGHT = 320
VP_X = WIDTH // 2
VP_Y = int(HEIGHT * 0.47)

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
class TunnelStream:
    end_x: float
    end_y: float
    phase: float
    speed: float
    glyphs: List[str]
    mutation: float
    hot: bool


class DashboardRain:
    """Dense code tunnel that appears to rush outward from a central vanishing point."""

    FONT_SIZES = (6, 7, 8, 9, 10, 11, 12, 13, 14)
    GLYPHS_PER_RAY = 14

    PALETTE = (
        (0, 22, 7),
        (0, 34, 10),
        (0, 48, 13),
        (0, 68, 18),
        (0, 92, 23),
        (0, 124, 30),
        (0, 164, 38),
        (0, 215, 50),
    )

    def __init__(self) -> None:
        self.streams: List[TunnelStream] = []
        self.fonts: Dict[int, pygame.font.Font] = {
            size: _matrix_font(size) for size in self.FONT_SIZES
        }
        self.cache: Dict[Tuple[int, str, int, bool], pygame.Surface] = {}
        self.surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.lines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.time = 0.0

        # Rays around all four sides create the corridor/tunnel perspective.
        endpoints: List[Tuple[float, float]] = []

        # Ceiling and floor: lots of rays so they read like streams of code.
        for x in range(-8, WIDTH + 9, 14):
            endpoints.append((float(x), -8.0))
            endpoints.append((float(x), float(HEIGHT + 8)))

        # Side walls: slightly wider spacing because the vertical distance is shorter.
        for y in range(6, HEIGHT, 15):
            endpoints.append((-8.0, float(y)))
            endpoints.append((float(WIDTH + 8), float(y)))

        random.shuffle(endpoints)
        for i, (end_x, end_y) in enumerate(endpoints):
            self.streams.append(
                TunnelStream(
                    end_x=end_x,
                    end_y=end_y,
                    phase=random.random(),
                    speed=random.uniform(0.055, 0.115),
                    glyphs=[random.choice(MATRIX_CHARS) for _ in range(self.GLYPHS_PER_RAY)],
                    mutation=random.uniform(0.65, 1.9),
                    hot=(i % 7 == 0),
                )
            )

    def _image(self, size: int, glyph: str, level: int, head: bool = False) -> pygame.Surface:
        level = max(0, min(7, level))
        key = (size, glyph, level, head)
        image = self.cache.get(key)
        if image is not None:
            return image

        if head:
            color = (205, 255, 215)
        else:
            color = self.PALETTE[level]
        image = self.fonts[size].render(glyph, True, color)
        self.cache[key] = image
        return image

    @staticmethod
    def _perspective(depth: float) -> float:
        # Pack far-away code tightly around the vanishing point, then rapidly
        # expand it as it approaches the viewer/screen edge.
        depth = max(0.0, min(1.0, depth))
        return depth ** 1.82

    def update(self, dt: float, energy: float = 0.0) -> None:
        self.time += dt
        boost = 1.0 + max(0.0, min(1.0, energy)) * 0.30

        for stream in self.streams:
            stream.phase = (stream.phase + stream.speed * boost * dt) % 1.0

            if stream.glyphs and random.random() < dt * stream.mutation:
                changes = 2 if random.random() < 0.18 else 1
                for _ in range(changes):
                    stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(MATRIX_CHARS)

    def _draw_tunnel_lines(self) -> None:
        self.lines.fill((0, 0, 0, 0))

        # Faint perspective rails give the code the corridor geometry from the
        # reference without looking like a wire-frame graphic.
        for index, stream in enumerate(self.streams):
            if index % 4 != 0:
                continue
            pygame.draw.line(
                self.lines,
                (0, 64, 18, 34),
                (VP_X, VP_Y),
                (int(stream.end_x), int(stream.end_y)),
                1,
            )

        # Moving nested rectangles deepen the illusion of traveling through a hall.
        for ring in range(9):
            depth = ((self.time * 0.12) + ring / 9.0) % 1.0
            t = self._perspective(depth)
            half_w = max(2, int((WIDTH * 0.54) * t))
            half_h = max(2, int((HEIGHT * 0.55) * t))
            rect = pygame.Rect(VP_X - half_w, VP_Y - half_h, half_w * 2, half_h * 2)
            alpha = int(16 + 45 * t)
            pygame.draw.rect(self.lines, (0, 105, 30, alpha), rect, 1)

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        self.glow.fill((0, 0, 0, 0))
        self._draw_tunnel_lines()

        for stream in self.streams:
            dx = stream.end_x - VP_X
            dy = stream.end_y - VP_Y

            # Each ray contains a moving chain of glyphs at different depths.
            # Wrapping the normalized depth makes the tunnel continuously flow
            # toward the viewer instead of falling straight down.
            points: List[Tuple[float, int, int, str]] = []
            for index, glyph in enumerate(stream.glyphs):
                depth = (stream.phase + index / self.GLYPHS_PER_RAY) % 1.0
                t = self._perspective(depth)
                x = int(VP_X + dx * t)
                y = int(VP_Y + dy * t)
                size = self.FONT_SIZES[min(len(self.FONT_SIZES) - 1, int(t * len(self.FONT_SIZES)))]
                points.append((t, x, y, glyph))

            # Draw far to near so large foreground glyphs sit naturally on top.
            points.sort(key=lambda item: item[0])
            for point_index, (t, x, y, glyph) in enumerate(points):
                # Near code is brighter and larger; distant code stays visible
                # enough to form the dense center of the tunnel.
                level = max(1, min(7, int(1.0 + t * 6.6)))
                size = self.FONT_SIZES[min(len(self.FONT_SIZES) - 1, int(t * len(self.FONT_SIZES)))]

                is_head = stream.hot and t > 0.86 and point_index == len(points) - 1
                if is_head:
                    glow = self._image(size, glyph, 7, False)
                    glow.set_alpha(95)
                    self.glow.blit(glow, (x - 2, y))
                    self.glow.blit(glow, (x + 2, y))
                    self.glow.blit(glow, (x, y - 1))
                    glow.set_alpha(255)

                image = self._image(size, glyph, level, is_head)
                self.surface.blit(image, (x, y))

        # Keep the tunnel luminous but restrained enough for the dashboard text.
        self.lines.set_alpha(180)
        destination.blit(self.lines, (0, 0))
        self.lines.set_alpha(255)

        self.glow.set_alpha(72)
        destination.blit(self.glow, (0, 0))
        self.glow.set_alpha(255)
        destination.blit(self.surface, (0, 0))
