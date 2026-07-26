#!/usr/bin/env python3
"""Sharp multi-depth Matrix rain with long clean trails for Raspberry Pi."""

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

from cinematic_fx import CinematicFX

MATRIX_GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜ012345789Z:・.="
ASCII_GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|:;[]{}()"
GREEN = (0, 255, 70)
DIM_GREEN = (0, 55, 22)
MID_GREEN = (0, 165, 48)
HEAD_GREEN = (225, 255, 232)


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
    x: float
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

        if self.depth == 0:
            self.speed = random.uniform(2.0, 4.2)
            self.length = random.randint(10, 22)
            self.brightness = random.uniform(0.28, 0.48)
            self.mutate_rate = random.uniform(0.025, 0.065)
            self.drift = random.uniform(-1.5, 1.5)
        elif self.depth == 1:
            self.speed = random.uniform(4.0, 8.5)
            self.length = random.randint(14, 30)
            self.brightness = random.uniform(0.55, 0.82)
            self.mutate_rate = random.uniform(0.045, 0.105)
            self.drift = random.uniform(-2.5, 2.5)
        else:
            self.speed = random.uniform(8.5, 15.5)
            self.length = random.randint(20, 38)
            self.brightness = random.uniform(0.84, 1.0)
            self.mutate_rate = random.uniform(0.07, 0.14)
            self.drift = random.uniform(-3.5, 3.5)

        self.hero = self.depth == 2 and random.random() < 0.13
        if self.hero:
            self.speed *= random.uniform(1.08, 1.24)
            self.length += random.randint(7, 13)

        self.glyphs = [random.choice(glyph_set) for _ in range(self.length)]


class MatrixEngine:
    """Three-layer rain with cached glyphs, sharp heads, and persistent trails."""

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
        self._hero_cache: Dict[str, pygame.Surface] = {}
        self.trail_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.trail_surface.fill((0, 0, 0, 0))
        self.fx = CinematicFX(width, height)

        layer_specs = (
            (0, max(11, self.char_w + 3), 0),
            (1, max(7, self.char_w - 2), 1),
            (2, max(15, self.char_w + 6), 2),
        )

        for depth, spacing, stagger in layer_specs:
            offset = (spacing // 2) if stagger else 0
            for x in range(-spacing + offset, width + spacing, spacing):
                stream = Stream(float(x), 0.0, 5.0, 18, [], 0.06, 1.0, depth, 0.0)
                stream.reset(height, self.glyph_set)
                stream.y = random.uniform(-height, height)
                self.streams.append(stream)

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
                (raw.get_width() + 10, raw.get_height() + 10), pygame.SRCALPHA
            )
            center = padded.get_rect().center
            pygame.draw.circle(padded, (35, 255, 95, 32), center, max(6, raw.get_height() // 2))
            pygame.draw.circle(padded, (90, 255, 140, 15), center, max(9, raw.get_height() - 2))
            padded.blit(raw, raw.get_rect(center=center))
            image = padded
            self._head_cache[glyph] = image
        return image

    def _hero_image(self, glyph: str) -> pygame.Surface:
        image = self._hero_cache.get(glyph)
        if image is None:
            head = self._head_image(glyph)
            image = pygame.transform.smoothscale(
                head,
                (max(1, int(head.get_width() * 1.55)), max(1, int(head.get_height() * 1.55))),
            )
            image.set_alpha(132)
            self._hero_cache[glyph] = image
        return image

    def trigger_cinematic_flash(self, strength: int = 76) -> None:
        self.fx.trigger_flash(strength=strength, decay_seconds=0.26)

    def update(self, intensity: float = 1.0) -> None:
        self.fx.update(1.0 / 60.0)

        for stream in self.streams:
            stream.y += stream.speed * intensity

            if random.random() < stream.mutate_rate:
                stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(self.glyph_set)

            if stream.y - stream.length * self.char_h > self.height:
                stream.reset(self.height, self.glyph_set)

    def draw(self, surface: pygame.Surface) -> None:
        # Very slow fade keeps long trails while the crisp live glyph stays on top.
        self.trail_surface.fill(
            (248, 248, 248, 242), special_flags=pygame.BLEND_RGBA_MULT
        )

        for stream in self.streams:
            for index, glyph in enumerate(stream.glyphs):
                y = int(stream.y - index * self.char_h)
                if y < -self.char_h or y > self.height:
                    continue

                falloff = max(0.06, 1.0 - index / max(1, stream.length - 1))
                depth_weight = (0.46, 0.78, 1.0)[stream.depth]
                value = falloff * stream.brightness * depth_weight
                level = int(max(0, min(5, round(value * 5))))
                x = int(stream.x + stream.drift * ((y % 37) / 37.0 - 0.5))

                if index == 0:
                    head = self._head_image(glyph)
                    head_rect = head.get_rect(center=(x + self.char_w // 2, y + self.char_h // 2))
                    if stream.depth == 0:
                        surface.blit(self._glyph_image(glyph, max(2, level)), (x, y))
                    else:
                        surface.blit(head, head_rect, special_flags=pygame.BLEND_RGBA_ADD)

                    if stream.depth == 2:
                        self.trail_surface.blit(head, head_rect, special_flags=pygame.BLEND_RGBA_ADD)

                        # Add two clean echoes behind foreground heads for longer streaks.
                        self.trail_surface.blit(
                            self._glyph_image(glyph, 4),
                            (x, y - self.char_h),
                            special_flags=pygame.BLEND_RGBA_ADD,
                        )
                        self.trail_surface.blit(
                            self._glyph_image(glyph, 3),
                            (x, y - self.char_h * 2),
                            special_flags=pygame.BLEND_RGBA_ADD,
                        )

                        if stream.hero:
                            hero = self._hero_image(glyph)
                            hero_rect = hero.get_rect(
                                center=(x + self.char_w // 2, y + self.char_h // 2)
                            )
                            self.trail_surface.blit(
                                hero, hero_rect, special_flags=pygame.BLEND_RGBA_ADD
                            )
                else:
                    surface.blit(self._glyph_image(glyph, level), (x, y))

        surface.blit(self.trail_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        self.fx.apply(surface)
