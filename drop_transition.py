#!/usr/bin/env python3
"""Cinematic Matrix transition: rain forms the data, then pours back away."""

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
    hero: bool
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
    """Pull visible rain into the page, bloom it, then liquefy it downward."""

    def __init__(
        self,
        width: int,
        height: int,
        glyph_font: pygame.font.Font,
        glyph_set: str,
        target_surface: pygame.Surface,
        rain_points: Sequence[Point],
        max_particles: int = 640,
        sample_step: int = 5,
    ) -> None:
        self.width = width
        self.height = height
        self.font = glyph_font
        self.glyph_set = glyph_set
        self.target_surface = target_surface.copy()
        self.collect_seconds = 1.85
        self.melt_seconds = 2.05
        self.elapsed = 0.0
        self.mode = "collect"
        self.particles: List[GlyphParticle] = []
        self._glyph_cache: Dict[Tuple[str, Color, int], pygame.Surface] = {}
        self.trail_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.trail_surface.fill((0, 0, 0, 0))

        self.content_dimmer = pygame.Surface((width, height - 76), pygame.SRCALPHA)
        self.content_dimmer.fill((0, 0, 0, 88))

        small = pygame.transform.smoothscale(
            self.target_surface,
            (max(1, width // 6), max(1, height // 6)),
        )
        self.target_bloom = pygame.transform.smoothscale(small, (width, height))
        self.target_bloom.set_alpha(105)

        self.sweep = pygame.Surface((90, height), pygame.SRCALPHA)
        for x in range(self.sweep.get_width()):
            distance = abs(x - self.sweep.get_width() / 2) / (self.sweep.get_width() / 2)
            alpha = int(72 * max(0.0, 1.0 - distance) ** 2)
            pygame.draw.line(
                self.sweep,
                (90, 255, 145, alpha),
                (x, 0),
                (x, height),
            )

        targets = self._sample_targets(target_surface, sample_step)
        if len(targets) > max_particles:
            stride = len(targets) / max_particles
            targets = [targets[int(index * stride)] for index in range(max_particles)]

        source_points = list(rain_points)
        if not source_points:
            source_points = [
                (random.randrange(0, width), random.randrange(78, height))
                for _ in range(160)
            ]

        for index, (tx, ty, color) in enumerate(targets):
            sx, source_y = random.choice(source_points)
            sy = source_y - random.uniform(50.0, 205.0)
            sx += random.uniform(-12.0, 12.0)
            hero = index % 37 == 0 or random.random() < 0.025
            particle = GlyphParticle(
                glyph=random.choice(glyph_set),
                start_x=sx,
                start_y=sy,
                target_x=float(tx),
                target_y=float(ty),
                color=color,
                delay=random.uniform(0.0, 0.34),
                sway=random.uniform(7.0, 30.0),
                phase=random.uniform(0.0, math.tau),
                hero=hero,
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

    def _image(self, glyph: str, color: Color, scale: int = 100) -> pygame.Surface:
        key = (glyph, color, scale)
        image = self._glyph_cache.get(key)
        if image is None:
            raw = self.font.render(glyph, True, color)
            if scale != 100:
                image = pygame.transform.smoothscale(
                    raw,
                    (
                        max(1, int(raw.get_width() * scale / 100)),
                        max(1, int(raw.get_height() * scale / 100)),
                    ),
                )
            else:
                image = raw
            self._glyph_cache[key] = image
        return image

    def start_collect(self) -> None:
        self.mode = "collect"
        self.elapsed = 0.0
        self.trail_surface.fill((0, 0, 0, 0))
        for particle in self.particles:
            particle.delay = random.uniform(0.0, 0.34)
            particle.reset_to_start()

    def start_melt(self) -> None:
        self.mode = "melt"
        self.elapsed = 0.0
        self.trail_surface.fill((0, 0, 0, 0))
        for particle in self.particles:
            column_wave = ((particle.target_x % 64.0) / 64.0) * 0.27
            vertical_weight = (particle.target_y / max(1.0, self.height)) * 0.12
            particle.delay = column_wave + vertical_weight + random.uniform(0.0, 0.14)
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
                - math.sin(progress * math.pi) * 28.0 * remaining
            )

            if progress > 0.72:
                snap = smoothstep((progress - 0.72) / 0.28)
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
            wobble = math.sin(particle.phase + progress * 10.0)
            particle.x = particle.target_x + wobble * (1.0 + 7.0 * progress)
            particle.y = (
                particle.target_y
                + 12.0 * progress
                + 360.0 * gravity
                + (particle.target_y / max(1.0, self.height)) * 58.0 * progress
            )
            particle.visible = particle.y <= self.height + self.font.get_linesize() * 5

    def finished(self) -> bool:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        return self.elapsed >= duration

    def _draw_target_echo(self, surface: pygame.Surface) -> None:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        progress = clamp(self.elapsed / max(0.1, duration))

        if self.mode == "collect":
            bloom_alpha = int(125 * smoothstep((progress - 0.48) / 0.38))
            text_alpha = int(250 * smoothstep((progress - 0.66) / 0.34))
        else:
            bloom_alpha = int(110 * clamp(1.0 - progress * 1.35))
            text_alpha = int(250 * clamp(1.0 - progress * 1.60))

        bloom = self.target_bloom.copy()
        bloom.set_alpha(bloom_alpha)
        surface.blit(bloom, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        echo = self.target_surface.copy()
        echo.set_alpha(text_alpha)
        surface.blit(echo, (0, 0))

    def _draw_light_sweep(self, surface: pygame.Surface) -> None:
        duration = self.collect_seconds if self.mode == "collect" else self.melt_seconds
        progress = clamp(self.elapsed / max(0.1, duration))
        if self.mode == "collect":
            sweep_x = int(-self.sweep.get_width() + progress * (self.width + self.sweep.get_width()))
        else:
            sweep_x = int(self.width - progress * (self.width + self.sweep.get_width()))
        surface.blit(self.sweep, (sweep_x, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.content_dimmer, (0, 76))
        self._draw_target_echo(surface)
        self._draw_light_sweep(surface)

        self.trail_surface.fill(
            (225, 225, 225, 210), special_flags=pygame.BLEND_RGBA_MULT
        )
        line_height = max(8, self.font.get_linesize() - 3)

        for particle in self.particles:
            if not particle.visible:
                continue

            x = int(particle.x)
            y = int(particle.y)

            if self.mode == "collect" and 0.03 < particle.progress < 0.95:
                trail_count = 3 if not particle.hero else 6
                for trail_index in range(trail_count, 0, -1):
                    trail_color = mix(
                        DIM_GREEN,
                        HEAD_GREEN,
                        0.14 + 0.10 * min(trail_index, 5),
                    )
                    trail_y = y - trail_index * line_height
                    self.trail_surface.blit(
                        self._image(particle.glyph, trail_color),
                        (x, trail_y),
                        special_flags=pygame.BLEND_RGBA_ADD,
                    )

            if self.mode == "melt" and particle.progress > 0.04:
                trail_count = 3
                if particle.progress > 0.25:
                    trail_count = 5
                if particle.progress > 0.52:
                    trail_count = 8

                for trail_index in range(trail_count, 0, -1):
                    trail_color = mix(
                        DIM_GREEN,
                        particle.color,
                        0.10 + 0.07 * min(trail_index, 6),
                    )
                    trail_y = y - trail_index * line_height
                    self.trail_surface.blit(
                        self._image(particle.glyph, trail_color),
                        (x, trail_y),
                        special_flags=pygame.BLEND_RGBA_ADD,
                    )

            head_color = HEAD_GREEN if self.mode == "collect" else particle.color
            scale = 155 if particle.hero else 118
            head = self._image(particle.glyph, head_color, scale)
            head_rect = head.get_rect(center=(x, y))
            surface.blit(head, head_rect, special_flags=pygame.BLEND_RGBA_ADD)

        surface.blit(self.trail_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
