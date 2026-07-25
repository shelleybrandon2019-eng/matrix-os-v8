#!/usr/bin/env python3
"""Matrix glyph transition: rain drops collect into text, then melt away."""

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import pygame

from matrix_engine import GREEN, HEAD_GREEN

Color = Tuple[int, int, int]
Point = Tuple[float, float]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


@dataclass
class GlyphParticle:
    glyph: str
    start_x: float
    start_y: float
    target_x: float
    target_y: float
    color: Color
    delay: float
    sway: float
    phase: float
    x: float = 0.0
    y: float = 0.0
    visible: bool = True

    def reset_to_start(self) -> None:
        self.x = self.start_x
        self.y = self.start_y
        self.visible = True

    def reset_to_target(self) -> None:
        self.x = self.target_x
        self.y = self.target_y
        self.visible = True


class DropCollectMelt:
    """Build a page out of Matrix glyphs and drip it off-screen without fading."""

    def __init__(
        self,
        width: int,
        height: int,
        glyph_font: pygame.font.Font,
        glyph_set: str,
        target_surface: pygame.Surface,
        rain_points: Sequence[Point],
        max_particles: int = 620,
        sample_step: int = 7,
    ) -> None:
        self.width = width
        self.height = height
        self.font = glyph_font
        self.glyph_set = glyph_set
        self.collect_seconds = 1.45
        self.melt_seconds = 1.45
        self.elapsed = 0.0
        self.mode = "collect"
        self.particles: List[GlyphParticle] = []
        self._glyph_cache: Dict[Tuple[str, Color], pygame.Surface] = {}

        targets = self._sample_targets(target_surface, sample_step)
        if len(targets) > max_particles:
            random.shuffle(targets)
            targets = targets[:max_particles]

        source_points = list(rain_points)
        if not source_points:
            source_points = [
                (random.randrange(0, width), random.randrange(80, height))
                for _ in range(80)
            ]

        for tx, ty, color in targets:
            sx, sy = random.choice(source_points)
            sx += random.uniform(-5.0, 5.0)
            sy += random.uniform(-20.0, 20.0)
            particle = GlyphParticle(
                glyph=random.choice(glyph_set),
                start_x=sx,
                start_y=sy,
                target_x=float(tx),
                target_y=float(ty),
                color=color,
                delay=random.uniform(0.0, 0.42),
                sway=random.uniform(12.0, 42.0),
                phase=random.uniform(0.0, math.tau),
            )
            particle.reset_to_start()
            self.particles.append(particle)

    @staticmethod
    def _sample_targets(
        target_surface: pygame.Surface,
        sample_step: int,
    ) -> List[Tuple[int, int, Color]]:
        width, height = target_surface.get_size()
        targets: List[Tuple[int, int, Color]] = []
        offset = max(1, sample_step // 2)

        for y in range(78 + offset, height, sample_step):
            for x in range(offset, width, sample_step):
                red, green, blue, _alpha = target_surface.get_at((x, y))
                if green < 70 or green <= red + 20:
                    continue
                color = HEAD_GREEN if red > 100 and green > 210 else GREEN
                targets.append((x, y, color))

        return targets

    def _image(self, glyph: str, color: Color) -> pygame.Surface:
        key = (glyph, color)
        image = self._glyph_cache.get(key)
        if image is None:
            image = self.font.render(glyph, True, color)
            self._glyph_cache[key] = image
        return image

    def start_collect(self) -> None:
        self.mode = "collect"
        self.elapsed = 0.0
        for particle in self.particles:
            particle.reset_to_start()

    def start_melt(self) -> None:
        self.mode = "melt"
        self.elapsed = 0.0
        for particle in self.particles:
            particle.delay = random.uniform(0.0, 0.38)
            particle.phase = random.uniform(0.0, math.tau)
            particle.reset_to_target()

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.mode == "collect":
            self._update_collect()
        else:
            self._update_melt()

    def _update_collect(self) -> None:
        for particle in self.particles:
            available = max(0.2, self.collect_seconds - particle.delay)
            progress = clamp((self.elapsed - particle.delay) / available)
            eased = smoothstep(progress)

            # The drop keeps a small Matrix-like side sway while being pulled in.
            arc = math.sin(progress * math.pi) * particle.sway
            particle.x = (
                particle.start_x
                + (particle.target_x - particle.start_x) * eased
                + math.sin(particle.phase + progress * 8.0) * arc
            )
            particle.y = (
                particle.start_y
                + (particle.target_y - particle.start_y) * eased
                - math.sin(progress * math.pi) * 22.0
            )
            particle.visible = progress > 0.0

    def _update_melt(self) -> None:
        for particle in self.particles:
            progress = clamp(
                (self.elapsed - particle.delay)
                / max(0.15, self.melt_seconds - particle.delay)
            )
            if progress <= 0.0:
                particle.x = particle.target_x
                particle.y = particle.target_y
                particle.visible = True
                continue

            # Accelerating vertical drip; the glyph vanishes only after leaving screen.
            particle.x = (
                particle.target_x
                + math.sin(particle.phase + progress * 11.0)
                * (2.0 + 7.0 * progress)
            )
            particle.y = (
                particle.target_y
                + 22.0 * progress
                + 180.0 * progress * progress
                + (particle.target_y / max(1.0, self.height)) * 45.0 * progress
            )
            particle.visible = particle.y <= self.height + self.font.get_linesize()

    def finished(self) -> bool:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        return self.elapsed >= duration

    def draw(self, surface: pygame.Surface) -> None:
        for particle in self.particles:
            if not particle.visible:
                continue
            surface.blit(
                self._image(particle.glyph, particle.color),
                (int(particle.x), int(particle.y)),
            )
