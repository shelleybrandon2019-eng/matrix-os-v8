#!/usr/bin/env python3
"""Cinematic multi-depth Matrix rain engine optimized for a Raspberry Pi."""

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

MATRIX_GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜ012345789Z:・.="
ASCII_GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|:;[]{}()"
GREEN = (0, 255, 70)
DIM_GREEN = (0, 55, 22)
MID_GREEN = (0, 165, 48)
HEAD_GREEN = (215, 255, 225)


def mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


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
    x: int
    y: float
    speed: float
    length: int
    glyphs: List[str]
    mutate_rate: float
    brightness: float
    depth: int
    drift: float
    hero: bool = False

    def reset(self, height: int, glyph_set: str) -> None:
        self.y = random.uniform(-height * 1.8, -20)

        if self.depth == 0:  # distant rain
            self.speed = random.uniform(2.0, 4.2)
            self.length = random.randint(10, 22)
            self.brightness = random.uniform(0.28, 0.48)
            self.mutate_rate = random.uniform(0.025, 0.065)
            self.drift = random.uniform(-0.025, 0.025)
        elif self.depth == 1:  # main rain field
            self.speed = random.uniform(4.0, 8.5)
            self.length = random.randint(14, 30)
            self.brightness = random.uniform(0.55, 0.82)
            self.mutate_rate = random.uniform(0.045, 0.105)
            self.drift = random.uniform(-0.045, 0.045)
        else:  # fast foreground streaks
            self.speed = random.uniform(8.5, 15.5)
            self.length = random.randint(18, 34)
            self.brightness = random.uniform(0.82, 1.0)
            self.mutate_rate = random.uniform(0.07, 0.14)
            self.drift = random.uniform(-0.07, 0.07)

        self.hero = self.depth == 2 and random.random() < 0.11
        if self.hero:
            self.speed *= random.uniform(1.08, 1.28)
            self.length += random.randint(5, 10)

        self.glyphs = [random.choice(glyph_set) for _ in range(self.length)]


class MatrixEngine:
    """Three-layer rain with cached glyphs, bloom heads, and persistent trails."""

    def __init__(self, width: int, height: int, font: pygame.font.Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.glyph_set = MATRIX_GLYPHS if font_supports_matrix_glyphs(font) else ASCII_GLYPHS
        self.char_w = max(9, font.size("W")[0])
        self.char_h = max(13, font.get_linesize())
        self.streams: List[Stream] = []
        self._glyph_cache: Dict[Tuple[str, int], pygame.Surface] = {}
        self._head_cache: Dict[str, pygame.Surface] = {}
        self.trail_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.trail_surface.fill((0, 0, 0, 0))

        # Layer 0 is sparse and dim, layer 1 carries the scene, layer 2 creates
        # occasional bright foreground streaks. The combined field feels dense
        # without requiring every column to be equally bright.
        layer_specs = (
            (0, max(11, self.char_w + 3), 0),
            (1, max(7, self.char_w - 2), 1),
            (2, max(15, self.char_w + 6), 2),
        )

        for depth, spacing, stagger in layer_specs:
            offset = (spacing // 2) if stagger else 0
            for x in range(-spacing + offset, width + spacing, spacing):
                stream = Stream(x, 0.0, 5.0, 18, [], 0.06, 1.0, depth, 0.0)
                stream.reset(height, self.glyph_set)
                stream.y = random.uniform(-height, height)
                self.streams.append(stream)

        # Draw back-to-front so bright foreground drops sit naturally on top.
        self.streams.sort(key=lambda item: item.depth)

    def _glyph_image(self, glyph: str, level: int) -> pygame.Surface:
        key = (glyph, level)
        image = self._glyph_cache.get(key)
        if image is None:
            palette = (
                (0, 34, 13),
                (0, 66, 24),
                (0, 105, 34),
                (0, 150, 44),
                (0, 205, 56),
                GREEN,
            )
            image = self.font.render(glyph, True, palette[max(0, min(5, level))])
            self._glyph_cache[key] = image
        return image

    def _head_image(self, glyph: str) -> pygame.Surface:
        image = self._head_cache.get(glyph)
        if image is None:
            raw = self.font.render(glyph, True, HEAD_GREEN)
            padded = pygame.Surface(
                (raw.get_width() + 12, raw.get_height() + 12), pygame.SRCALPHA
            )
            center = padded.get_rect().center
            pygame.draw.circle(padded, (35, 255, 95, 42), center, max(8, raw.get_height() // 2))
            pygame.draw.circle(padded, (90, 255, 140, 28), center, max(11, raw.get_height()))
            padded.blit(raw, raw.get_rect(center=center))
            image = padded
            self._head_cache[glyph] = image
        return image

    def update(self, intensity: float = 1.0) -> None:
        for stream in self.streams:
            stream.y += stream.speed * intensity
            stream.x += stream.drift * intensity

            if random.random() < stream.mutate_rate:
                stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(self.glyph_set)

            if stream.y - stream.length * self.char_h > self.height:
                # Keep the original column while allowing a tiny cinematic wander.
                stream.x = int(round(stream.x))
                stream.reset(self.height, self.glyph_set)

    def draw(self, surface: pygame.Surface) -> None:
        # Fade old foreground highlights instead of erasing them immediately.
        self.trail_surface.fill(
            (235, 235, 235, 218), special_flags=pygame.BLEND_RGBA_MULT
        )

        for stream in self.streams:
            for index, glyph in enumerate(stream.glyphs):
                y = int(stream.y - index * self.char_h)
                if y < -self.char_h or y > self.height:
                    continue

                falloff = max(0.06, 1.0 - index / max(1, stream.length - 1))
                depth_weight = (0.50, 0.78, 1.0)[stream.depth]
                value = falloff * stream.brightness * depth_weight
                level = int(max(0, min(5, round(value * 5))))
                x = int(stream.x)

                if index == 0:
                    head = self._head_image(glyph)
                    head_rect = head.get_rect(center=(x + self.char_w // 2, y + self.char_h // 2))
                    if stream.depth == 0:
                        surface.blit(self._glyph_image(glyph, max(2, level)), (x, y))
                    else:
                        surface.blit(head, head_rect, special_flags=pygame.BLEND_RGBA_ADD)
                        surface.blit(self.font.render(glyph, True, HEAD_GREEN), (x, y))

                    if stream.depth == 2:
                        # Bright foreground heads leave a short optical trail.
                        self.trail_surface.blit(head, head_rect, special_flags=pygame.BLEND_RGBA_ADD)
                        if stream.hero:
                            hero_glow = pygame.transform.smoothscale(
                                head,
                                (head.get_width() * 2, head.get_height() * 2),
                            )
                            hero_rect = hero_glow.get_rect(
                                center=(x + self.char_w // 2, y + self.char_h // 2)
                            )
                            self.trail_surface.blit(
                                hero_glow, hero_rect, special_flags=pygame.BLEND_RGBA_ADD
                            )
                else:
                    surface.blit(self._glyph_image(glyph, level), (x, y))

        surface.blit(self.trail_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
