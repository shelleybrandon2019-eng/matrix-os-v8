#!/usr/bin/env python3
import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame

MATRIX_GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜ012345789Z:・.="
ASCII_GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|:;[]{}()"
GREEN = (0, 255, 70)
DIM_GREEN = (0, 70, 28)
HEAD_GREEN = (205, 255, 215)


def mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def font_supports_matrix_glyphs(font: pygame.font.Font) -> bool:
    """Reject fonts that render Japanese glyphs as identical square placeholders."""
    samples = [font.render(char, True, (255, 255, 255)) for char in "ｱｶｻﾀﾅ"]
    signatures = []
    for surface in samples:
        signatures.append((surface.get_size(), pygame.image.tostring(surface, "RGBA")))
    return len(set(signatures)) > 1


@dataclass
class Stream:
    x: int
    y: float
    speed: float
    length: int
    glyphs: List[str]
    mutate_rate: float
    brightness: float = 1.0

    def reset(self, height: int, glyph_set: str) -> None:
        self.y = random.uniform(-height * 1.6, -20)
        roll = random.random()
        if roll < 0.16:
            self.speed = random.uniform(10.0, 17.0)
        elif roll < 0.46:
            self.speed = random.uniform(6.0, 11.0)
        else:
            self.speed = random.uniform(3.2, 7.2)
        self.length = random.randint(13, 31)
        self.glyphs = [random.choice(glyph_set) for _ in range(self.length)]
        self.mutate_rate = random.uniform(0.045, 0.14)
        self.brightness = random.uniform(0.72, 1.0)


class MatrixEngine:
    def __init__(self, width: int, height: int, font: pygame.font.Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.glyph_set = MATRIX_GLYPHS if font_supports_matrix_glyphs(font) else ASCII_GLYPHS
        self.char_w = max(9, font.size("W")[0])
        self.char_h = max(13, font.get_linesize())
        self.streams: List[Stream] = []

        # Tighter column spacing plus a staggered second layer creates more rain
        # without increasing glyph size.
        spacing = max(6, self.char_w - 3)
        for layer in range(2):
            offset = (spacing // 2) if layer else 0
            for x in range(-spacing + offset, width + spacing, spacing):
                stream = Stream(x, 0.0, 5.0, 16, [], 0.06)
                stream.reset(height, self.glyph_set)
                stream.y = random.uniform(-height, height)
                if layer:
                    stream.speed *= random.uniform(0.72, 0.92)
                    stream.brightness *= 0.78
                self.streams.append(stream)

    def update(self, intensity: float = 1.0) -> None:
        for stream in self.streams:
            stream.y += stream.speed * intensity
            if random.random() < stream.mutate_rate:
                stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(self.glyph_set)
            if stream.y - stream.length * self.char_h > self.height:
                stream.reset(self.height, self.glyph_set)

    def draw(self, surface: pygame.Surface) -> None:
        for stream in self.streams:
            for i, glyph in enumerate(stream.glyphs):
                y = int(stream.y - i * self.char_h)
                if y < -self.char_h or y > self.height:
                    continue
                brightness = max(0.10, 1.0 - i / max(1, stream.length - 1))
                brightness *= stream.brightness
                color = HEAD_GREEN if i == 0 and stream.brightness > 0.82 else mix(DIM_GREEN, GREEN, brightness)
                surface.blit(self.font.render(glyph, True, color), (stream.x, y))
