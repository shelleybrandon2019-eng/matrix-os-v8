#!/usr/bin/env python3
"""Matrix transition: rain drops collect into data, then melt back into rain."""

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
    """Pull visible rain into the page, hold it, then pour it downward."""

    def __init__(
        self,
        width: int,
        height: int,
        glyph_font: pygame.font.Font,
        glyph_set: str,
        target_surface: pygame.Surface,
        rain_points: Sequence[Point],
        max_particles: int = 680,
        sample_step: int = 5,
    ) -> None:
        self.width = width
        self.height = height
        self.font = glyph_font
        self.glyph_set = glyph_set
        self.target_surface = target_surface.copy()
        self.collect_seconds = 1.75
        self.melt_seconds = 1.85
        self.elapsed = 0.0
        self.mode = "collect"
        self.particles: List[GlyphParticle] = []
        self._glyph_cache: Dict[Tuple[str, Color], pygame.Surface] = {}
        self.badge_font = pygame.font.Font(None, 18)

        # Keep most of the rain visible. This is only enough shade to separate
        # the brighter collected drops from the background.
        self.content_dimmer = pygame.Surface((width, height - 76), pygame.SRCALPHA)
        self.content_dimmer.fill((0, 0, 0, 105))

        targets = self._sample_targets(target_surface, sample_step)
        if len(targets) > max_particles:
            stride = len(targets) / max_particles
            targets = [targets[int(index * stride)] for index in range(max_particles)]

        source_points = list(rain_points)
        if not source_points:
            source_points = [
                (random.randrange(0, width), random.randrange(78, height))
                for _ in range(140)
            ]

        for tx, ty, color in targets:
            sx, source_y = random.choice(source_points)
            # Start at or just above a real stream location, so it looks like
            # the page is stealing drops from the background rain.
            sy = source_y - random.uniform(45.0, 180.0)
            sx += random.uniform(-10.0, 10.0)
            particle = GlyphParticle(
                glyph=random.choice(glyph_set),
                start_x=sx,
                start_y=sy,
                target_x=float(tx),
                target_y=float(ty),
                color=color,
                delay=random.uniform(0.0, 0.30),
                sway=random.uniform(8.0, 28.0),
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
                red, green, _blue, _alpha = target_surface.get_at((x, y))
                if green < 70 or green <= red + 20:
                    continue
                color = HEAD_GREEN if red > 100 and green > 210 else GREEN
                targets.append((x, y, color))

        return targets

    def _image(self, glyph: str, color: Color) -> pygame.Surface:
        key = (glyph, color)
        image = self._glyph_cache.get(key)
        if image is None:
            raw = self.font.render(glyph, True, color)
            image = pygame.transform.smoothscale(
                raw,
                (
                    max(1, int(raw.get_width() * 1.18)),
                    max(1, int(raw.get_height() * 1.18)),
                ),
            )
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
            # Neighboring columns hang together before gravity breaks them loose.
            column_wave = ((particle.target_x % 62.0) / 62.0) * 0.24
            vertical_weight = (particle.target_y / max(1.0, self.height)) * 0.11
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
            available = max(0.24, self.collect_seconds - particle.delay)
            progress = clamp((self.elapsed - particle.delay) / available)
            eased = smoothstep(progress)
            particle.progress = progress

            remaining = 1.0 - eased
            arc = math.sin(progress * math.pi) * particle.sway * remaining
            particle.x = (
                particle.start_x
                + (particle.target_x - particle.start_x) * eased
                + math.sin(particle.phase + progress * 8.0) * arc
            )
            particle.y = (
                particle.start_y
                + (particle.target_y - particle.start_y) * eased
                - math.sin(progress * math.pi) * 24.0 * remaining
            )

            # Magnetic snap: the final part forms sharply instead of staying fuzzy.
            if progress > 0.76:
                snap = smoothstep((progress - 0.76) / 0.24)
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

            gravity = progress * progress
            particle.x = (
                particle.target_x
                + math.sin(particle.phase + progress * 10.0)
                * (1.0 + 6.0 * progress)
            )
            particle.y = (
                particle.target_y
                + 14.0 * progress
                + 330.0 * gravity
                + (particle.target_y / max(1.0, self.height)) * 52.0 * progress
            )
            particle.visible = particle.y <= self.height + self.font.get_linesize() * 4

    def finished(self) -> bool:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        return self.elapsed >= duration

    def _draw_target_echo(self, surface: pygame.Surface) -> None:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        global_progress = clamp(self.elapsed / max(0.1, duration))

        echo = self.target_surface.copy()
        if self.mode == "collect":
            alpha = int(245 * smoothstep((global_progress - 0.66) / 0.34))
        else:
            alpha = int(245 * clamp(1.0 - global_progress * 1.65))
        echo.set_alpha(alpha)
        surface.blit(echo, (0, 0))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.content_dimmer, (0, 76))
        self._draw_target_echo(surface)

        line_height = max(8, self.font.get_linesize() - 3)
        for particle in self.particles:
            if not particle.visible:
                continue

            x = int(particle.x)
            y = int(particle.y)

            if self.mode == "collect" and 0.05 < particle.progress < 0.92:
                # Bright falling head with a short tail makes the collection visible.
                for trail_index in range(3, 0, -1):
                    trail_color = mix(DIM_GREEN, HEAD_GREEN, 0.20 + trail_index * 0.13)
                    trail_y = y - trail_index * line_height
                    surface.blit(self._image(particle.glyph, trail_color), (x, trail_y))

            if self.mode == "melt" and particle.progress > 0.06:
                trail_count = 2
                if particle.progress > 0.28:
                    trail_count = 4
                if particle.progress > 0.55:
                    trail_count = 6

                for trail_index in range(trail_count, 0, -1):
                    trail_color = mix(
                        DIM_GREEN,
                        particle.color,
                        0.14 + 0.08 * min(trail_index, 5),
                    )
                    trail_y = y - trail_index * line_height
                    surface.blit(self._image(particle.glyph, trail_color), (x, trail_y))

            # Use a white-green head during collection, then page color during melt.
            head_color = HEAD_GREEN if self.mode == "collect" else particle.color
            surface.blit(self._image(particle.glyph, head_color), (x, y))

        badge = self.badge_font.render("V9.3 DROP FUN", True, HEAD_GREEN)
        surface.blit(badge, (self.width - badge.get_width() - 8, self.height - 19))
