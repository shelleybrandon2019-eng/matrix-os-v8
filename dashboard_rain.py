#!/usr/bin/env python3
"""Dense, readable Matrix rain tuned for the 480x320 dashboard."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

WIDTH = 480
HEIGHT = 320
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
class Stream:
    x: int
    y: float
    speed: float
    length: int
    spacing: int
    depth: int
    font_size: int
    glyphs: List[str]
    mutation: float
    phase: float

    def recycle(self, *, full_height: bool = False) -> None:
        if full_height:
            self.y = random.uniform(-HEIGHT * 0.2, HEIGHT * 1.05)
        else:
            self.y = random.uniform(-HEIGHT * 1.35, -10)

        if self.depth == 0:
            self.speed = random.uniform(34.0, 72.0)
            self.length = random.randint(15, 30)
            self.mutation = random.uniform(0.7, 1.5)
        elif self.depth == 1:
            self.speed = random.uniform(68.0, 126.0)
            self.length = random.randint(12, 25)
            self.mutation = random.uniform(1.2, 2.5)
        else:
            self.speed = random.uniform(110.0, 190.0)
            self.length = random.randint(9, 19)
            self.mutation = random.uniform(2.0, 4.0)

        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
        self.phase = random.random() * 10.0


class DashboardRain:
    """Three-depth code rain with bright heads, long readable trails and dense coverage."""

    # depth, font size, x spacing
    LAYERS = (
        (0, 8, 12),
        (1, 10, 16),
        (2, 12, 23),
    )

    # Eight trail intensities for each depth. These are deliberately brighter
    # than the cinematic scene engine because the dashboard has text drawn over it.
    PALETTES = {
        0: (
            (0, 15, 5), (0, 23, 7), (0, 31, 9), (0, 40, 11),
            (0, 50, 14), (0, 62, 17), (0, 76, 20), (0, 92, 24),
        ),
        1: (
            (0, 23, 7), (0, 34, 10), (0, 48, 13), (0, 66, 17),
            (0, 88, 22), (0, 115, 28), (0, 148, 35), (0, 185, 43),
        ),
        2: (
            (0, 31, 9), (0, 48, 13), (0, 70, 18), (0, 96, 23),
            (0, 126, 29), (0, 162, 36), (0, 205, 45), (0, 245, 58),
        ),
    }

    HEADS = {
        0: (35, 125, 55),
        1: (95, 240, 125),
        2: (215, 255, 220),
    }

    def __init__(self) -> None:
        self.streams: List[Stream] = []
        self.fonts: Dict[int, pygame.font.Font] = {}
        self.cache: Dict[Tuple[int, str, int, bool], pygame.Surface] = {}
        self.surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        for depth, font_size, x_spacing in self.LAYERS:
            font = _matrix_font(font_size)
            self.fonts[font_size] = font
            y_spacing = max(font_size + 1, font.get_linesize() - 1)
            # Stagger layers so they do not stack on the same vertical grid.
            offset = random.randint(0, max(1, x_spacing - 1))
            for x in range(-x_spacing + offset, WIDTH + x_spacing, x_spacing):
                stream = Stream(
                    x=x,
                    y=0.0,
                    speed=80.0,
                    length=15,
                    spacing=y_spacing,
                    depth=depth,
                    font_size=font_size,
                    glyphs=[],
                    mutation=1.0,
                    phase=0.0,
                )
                stream.recycle(full_height=True)
                self.streams.append(stream)

    def _image(self, stream: Stream, glyph: str, level: int, head: bool = False) -> pygame.Surface:
        key = (stream.font_size, glyph, level, head)
        image = self.cache.get(key)
        if image is not None:
            return image

        if head:
            color = self.HEADS[stream.depth]
        else:
            color = self.PALETTES[stream.depth][max(0, min(7, level))]
        image = self.fonts[stream.font_size].render(glyph, True, color)
        self.cache[key] = image
        return image

    def update(self, dt: float, energy: float = 0.0) -> None:
        boost = 1.0 + min(1.0, max(0.0, energy)) * 0.16
        for stream in self.streams:
            stream.y += stream.speed * boost * dt
            stream.phase += dt

            # Keep code alive. Near streams mutate faster than distant streams.
            chance = dt * stream.mutation
            if stream.glyphs and random.random() < chance:
                count = 2 if stream.depth == 2 and random.random() < 0.25 else 1
                for _ in range(count):
                    stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(MATRIX_CHARS)

            tail_y = stream.y - stream.length * stream.spacing
            if tail_y > HEIGHT + stream.spacing:
                stream.recycle()

    def draw(self, destination: pygame.Surface, energy: float = 0.0) -> None:
        self.surface.fill((0, 0, 0, 0))
        self.glow.fill((0, 0, 0, 0))

        for stream in self.streams:
            for index, glyph in enumerate(stream.glyphs):
                y = int(stream.y - index * stream.spacing)
                if y < -stream.spacing or y > HEIGHT:
                    continue

                # Long luminous fade: first few characters stay vivid, then
                # smoothly sink into the black background.
                position = index / max(1, stream.length - 1)
                intensity = max(0.0, 1.0 - position)
                intensity = intensity ** 1.25
                level = max(0, min(7, int(intensity * 7.99)))

                # Every stream has a bright head. Foreground heads get a tiny
                # soft halo so they read like the classic white-green lead glyph.
                is_head = index == 0
                if is_head and stream.depth == 2:
                    halo = self._image(stream, glyph, 7, False)
                    halo.set_alpha(90)
                    self.glow.blit(halo, (stream.x - 1, y))
                    self.glow.blit(halo, (stream.x + 1, y))
                    halo.set_alpha(255)

                self.surface.blit(self._image(stream, glyph, level, is_head), (stream.x, y))

        # A very light glow keeps the green rich on the physical 480x320 panel
        # without turning the dashboard into a neon fog.
        self.glow.set_alpha(80)
        destination.blit(self.glow, (0, 0))
        self.glow.set_alpha(255)
        destination.blit(self.surface, (0, 0))
