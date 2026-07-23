#!/usr/bin/env python3
import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame

GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
GREEN = (0, 255, 70)
DIM_GREEN = (0, 70, 28)
HEAD_GREEN = (205, 255, 215)


def mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


@dataclass
class Stream:
    x: int
    y: float
    speed: float
    length: int
    glyphs: List[str]
    mutate_rate: float

    def reset(self, height: int) -> None:
        self.y = random.uniform(-height * 1.4, -20)
        roll = random.random()
        if roll < 0.12:
            self.speed = random.uniform(10.0, 16.0)
        elif roll < 0.38:
            self.speed = random.uniform(6.0, 10.0)
        else:
            self.speed = random.uniform(3.5, 6.5)
        self.length = random.randint(10, 26)
        self.glyphs = [random.choice(GLYPHS) for _ in range(self.length)]
        self.mutate_rate = random.uniform(0.035, 0.11)


class MatrixEngine:
    def __init__(self, width: int, height: int, font: pygame.font.Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.char_w = max(9, font.size("W")[0])
        self.char_h = max(13, font.get_linesize())
        self.streams: List[Stream] = []
        for x in range(-self.char_w, width + self.char_w, self.char_w):
            stream = Stream(x, 0.0, 5.0, 16, [], 0.06)
            stream.reset(height)
            stream.y = random.uniform(-height, height)
            self.streams.append(stream)

    def update(self, intensity: float = 1.0) -> None:
        for stream in self.streams:
            stream.y += stream.speed * intensity
            if random.random() < stream.mutate_rate:
                stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(GLYPHS)
            if stream.y - stream.length * self.char_h > self.height:
                stream.reset(self.height)

    def draw(self, surface: pygame.Surface) -> None:
        for stream in self.streams:
            for i, glyph in enumerate(stream.glyphs):
                y = int(stream.y - i * self.char_h)
                if y < -self.char_h or y > self.height:
                    continue
                brightness = max(0.08, 1.0 - i / max(1, stream.length - 1))
                color = HEAD_GREEN if i == 0 else mix(DIM_GREEN, GREEN, brightness)
                surface.blit(self.font.render(glyph, True, color), (stream.x, y))
