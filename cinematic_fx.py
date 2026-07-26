#!/usr/bin/env python3
"""Lightweight cinematic post effects for the 480x320 Matrix display."""

import math
import random
from typing import Optional

import pygame


class CinematicFX:
    """Scanlines, vignette, bloom wash, and rare film-like flicker."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.vignette = self._build_vignette()
        self.scanlines = self._build_scanlines()
        self.green_haze = self._build_green_haze()
        self.flash_alpha = 0.0
        self.flash_decay = 0.0
        self.next_flicker = pygame.time.get_ticks() + random.randint(4000, 9000)
        self.flicker_alpha = 0

    def _build_vignette(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        cx = self.width / 2.0
        cy = self.height / 2.0
        max_distance = math.hypot(cx, cy)

        # Draw soft concentric edge bands instead of processing every pixel per frame.
        for band in range(24, 0, -1):
            t = band / 24.0
            inset_x = int((1.0 - t) * self.width * 0.32)
            inset_y = int((1.0 - t) * self.height * 0.28)
            alpha = int(8 + 7 * t)
            pygame.draw.rect(
                surface,
                (0, 0, 0, alpha),
                (inset_x, inset_y, self.width - inset_x * 2, self.height - inset_y * 2),
                width=max(1, int(2 + t * 5)),
                border_radius=18,
            )

        # Stronger outer frame makes the center feel brighter and deeper.
        pygame.draw.rect(surface, (0, 0, 0, 78), surface.get_rect(), width=12)
        return surface

    def _build_scanlines(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for y in range(0, self.height, 3):
            pygame.draw.line(surface, (0, 0, 0, 23), (0, y), (self.width, y))
        return surface

    def _build_green_haze(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        glow = pygame.Surface((self.width // 2, self.height // 2), pygame.SRCALPHA)
        pygame.draw.ellipse(
            glow,
            (0, 90, 30, 34),
            (-20, 10, glow.get_width() + 40, glow.get_height() - 15),
        )
        glow = pygame.transform.smoothscale(glow, (self.width, self.height))
        surface.blit(glow, (0, 0))
        return surface

    def trigger_flash(self, strength: int = 110, decay_seconds: float = 0.35) -> None:
        self.flash_alpha = float(max(0, min(180, strength)))
        self.flash_decay = self.flash_alpha / max(0.08, decay_seconds)

    def update(self, dt: float) -> None:
        if self.flash_alpha > 0.0:
            self.flash_alpha = max(0.0, self.flash_alpha - self.flash_decay * dt)

        now = pygame.time.get_ticks()
        if now >= self.next_flicker:
            self.flicker_alpha = random.randint(6, 16)
            self.next_flicker = now + random.randint(4500, 10000)
        elif self.flicker_alpha > 0:
            self.flicker_alpha = max(0, self.flicker_alpha - 2)

    def apply(self, surface: pygame.Surface) -> None:
        surface.blit(self.green_haze, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(self.scanlines, (0, 0))
        surface.blit(self.vignette, (0, 0))

        if self.flicker_alpha:
            flicker = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flicker.fill((180, 255, 200, self.flicker_alpha))
            surface.blit(flicker, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        if self.flash_alpha > 0.0:
            flash = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flash.fill((80, 255, 130, int(self.flash_alpha)))
            surface.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
