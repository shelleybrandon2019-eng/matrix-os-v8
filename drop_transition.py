#!/usr/bin/env python3
"""Matrix glyph transition: rain drops collect into text, then melt away."""

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import pygame

from matrix_engine import DIM_GREEN, GREEN, HEAD_GREEN

Color = Tuple[int, int, int]
Point = Tuple[float, float]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def mix(a: Color, b: Color, amount: float) -> Color:
    amount = clamp(amount)
    return tuple(int(a[i] + (b[i] - a[i]) * amount) for i in range(3))


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
    progress: float = 0.0

    def reset_to_start(self) -> None:
        self.x = self.start_x
        self.y = self.start_y
        self.visible = True
        self.progress = 0.0

    def reset_to_target(self) -> None:
        self.x = self.target_x
        self.y = self.target_y
        self.visible = True
        self.progress = 0.0


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
        max_particles: int = 600,
        sample_step: int = 6,
    ) -> None:
        self.width = width
        self.height = height
        self.font = glyph_font
        self.glyph_set = glyph_set
        self.collect_seconds = 1.65
        self.melt_seconds = 1.90
        self.elapsed = 0.0
        self.mode = "collect"
        self.particles: List[GlyphParticle] = []
        self._glyph_cache: Dict[Tuple[str, Color], pygame.Surface] = {}

        targets = self._sample_targets(target_surface, sample_step)
        if len(targets) > max_particles:
            # Keep the shape balanced instead of removing one whole region at random.
            stride = len(targets) / max_particles
            targets = [targets[int(index * stride)] for index in range(max_particles)]

        source_points = list(rain_points)
        if not source_points:
            source_points = [
                (random.randrange(0, width), random.randrange(80, height))
                for _ in range(100)
            ]

        for tx, ty, color in targets:
            sx, sy = random.choice(source_points)
            sx += random.uniform(-4.0, 4.0)
            sy += random.uniform(-16.0, 16.0)
            particle = GlyphParticle(
                glyph=random.choice(glyph_set),
                start_x=sx,
                start_y=sy,
                target_x=float(tx),
                target_y=float(ty),
                color=color,
                delay=random.uniform(0.0, 0.30),
                sway=random.uniform(6.0, 20.0),
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
            particle.delay = random.uniform(0.0, 0.30)
            particle.reset_to_start()

    def start_melt(self) -> None:
        self.mode = "melt"
        self.elapsed = 0.0
        for particle in self.particles:
            # Uneven column delays make sections hang and stretch like liquid.
            column_wave = ((particle.target_x % 54.0) / 54.0) * 0.24
            vertical_weight = (particle.target_y / max(1.0, self.height)) * 0.12
            particle.delay = column_wave + vertical_weight + random.uniform(0.0, 0.12)
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
            available = max(0.25, self.collect_seconds - particle.delay)
            progress = clamp((self.elapsed - particle.delay) / available)
            eased = smoothstep(progress)
            particle.progress = progress

            # Strong movement early, then a tight magnetic snap into the text shape.
            remaining = 1.0 - eased
            arc = math.sin(progress * math.pi) * particle.sway * remaining
            particle.x = (
                particle.start_x
                + (particle.target_x - particle.start_x) * eased
                + math.sin(particle.phase + progress * 7.0) * arc
            )
            particle.y = (
                particle.start_y
                + (particle.target_y - particle.start_y) * eased
                - math.sin(progress * math.pi) * 16.0 * remaining
            )

            if progress > 0.86:
                snap = smoothstep((progress - 0.86) / 0.14)
                particle.x += (particle.target_x - particle.x) * snap
                particle.y += (particle.target_y - particle.y) * snap

            particle.visible = progress > 0.0

    def _update_melt(self) -> None:
        for particle in self.particles:
            progress = clamp(
                (self.elapsed - particle.delay)
                / max(0.18, self.melt_seconds - particle.delay)
            )
            particle.progress = progress

            if progress <= 0.0:
                particle.x = particle.target_x
                particle.y = particle.target_y
                particle.visible = True
                continue

            # Slow stretch first, then gravity takes over and pulls the glyph away.
            gravity = progress * progress
            particle.x = (
                particle.target_x
                + math.sin(particle.phase + progress * 9.0)
                * (1.0 + 4.5 * progress)
            )
            particle.y = (
                particle.target_y
                + 12.0 * progress
                + 255.0 * gravity
                + (particle.target_y / max(1.0, self.height)) * 55.0 * progress
            )
            particle.visible = particle.y <= self.height + self.font.get_linesize() * 3

    def finished(self) -> bool:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        return self.elapsed >= duration

    def draw(self, surface: pygame.Surface) -> None:
        line_height = max(8, self.font.get_linesize() - 4)

        for particle in self.particles:
            if not particle.visible:
                continue

            x = int(particle.x)
            y = int(particle.y)

            if self.mode == "melt" and particle.progress > 0.10:
                # Dim copies above the falling glyph create stringy liquid trails.
                trail_count = 1
                if particle.progress > 0.34:
                    trail_count = 2
                if particle.progress > 0.62:
                    trail_count = 3

                for trail_index in range(trail_count, 0, -1):
                    trail_color = mix(DIM_GREEN, particle.color, 0.20 + 0.12 * trail_index)
                    trail_y = y - trail_index * line_height
                    surface.blit(
                        self._image(particle.glyph, trail_color),
                        (x, trail_y),
                    )

            surface.blit(
                self._image(particle.glyph, particle.color),
                (x, y),
            )
