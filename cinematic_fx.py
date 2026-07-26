#!/usr/bin/env python3
"""Sharp cinematic post effects for the 480x320 Matrix display."""

import random

import pygame


class CinematicFX:
    """Light vignette and scanlines without softening the text or rain."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.vignette = self._build_vignette()
        self.scanlines = self._build_scanlines()
        self.green_haze = self._build_green_haze()
        self.flash_alpha = 0.0
        self.flash_decay = 0.0
        self.next_flicker = pygame.time.get_ticks() + random.randint(6000, 12000)
        self.flicker_alpha = 0

    def _build_vignette(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        # Keep the cinematic edge framing, but leave the center crisp and bright.
        for band in range(18, 0, -1):
            t = band / 18.0
            inset_x = int((1.0 - t) * self.width * 0.28)
            inset_y = int((1.0 - t) * self.height * 0.24)
            alpha = int(4 + 4 * t)
            pygame.draw.rect(
                surface,
                (0, 0, 0, alpha),
                (inset_x, inset_y, self.width - inset_x * 2, self.height - inset_y * 2),
                width=max(1, int(1 + t * 4)),
                border_radius=16,
            )

        pygame.draw.rect(surface, (0, 0, 0, 52), surface.get_rect(), width=10)
        return surface

    def _build_scanlines(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for y in range(0, self.height, 3):
            pygame.draw.line(surface, (0, 0, 0, 11), (0, y), (self.width, y))
        return surface

    def _build_green_haze(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        glow = pygame.Surface((self.width // 2, self.height // 2), pygame.SRCALPHA)
        pygame.draw.ellipse(
            glow,
            (0, 78, 25, 18),
            (-20, 12, glow.get_width() + 40, glow.get_height() - 18),
        )
        glow = pygame.transform.smoothscale(glow, (self.width, self.height))
        surface.blit(glow, (0, 0))
        return surface

    def trigger_flash(self, strength: int = 80, decay_seconds: float = 0.28) -> None:
        self.flash_alpha = float(max(0, min(130, strength)))
        self.flash_decay = self.flash_alpha / max(0.08, decay_seconds)

    def update(self, dt: float) -> None:
        if self.flash_alpha > 0.0:
            self.flash_alpha = max(0.0, self.flash_alpha - self.flash_decay * dt)

        now = pygame.time.get_ticks()
        if now >= self.next_flicker:
            self.flicker_alpha = random.randint(3, 8)
            self.next_flicker = now + random.randint(6500, 13000)
        elif self.flicker_alpha > 0:
            self.flicker_alpha = max(0, self.flicker_alpha - 2)

    def apply(self, surface: pygame.Surface) -> None:
        surface.blit(self.green_haze, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(self.scanlines, (0, 0))
        surface.blit(self.vignette, (0, 0))

        if self.flicker_alpha:
            flicker = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flicker.fill((185, 255, 205, self.flicker_alpha))
            surface.blit(flicker, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        if self.flash_alpha > 0.0:
            flash = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flash.fill((70, 255, 120, int(self.flash_alpha)))
            surface.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
