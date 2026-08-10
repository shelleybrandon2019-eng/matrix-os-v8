#!/usr/bin/env python3
"""Matrix OS: thick code rain with Neo-style temperature reveals."""
from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pygame

from dashboard_rain import DashboardRain
from live_data import LiveData
from main import BLACK, FULLSCREEN, HEIGHT, WIDTH, choose_font, choose_matrix_font, temp_color

FPS = 60
GREEN = (0, 255, 90)
DIM_GREEN = (0, 110, 44)
SHADOW = (0, 28, 10)
WHITE_GREEN = (205, 255, 215)

MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "ｦｧｨｩｪｫｬｭｮｯｰﾞﾟ"
    "0123456789@#$%&*+=<>?/\\|:;.-_"
)

# Timing: thick rain -> Outside reveal -> short rain -> Inside reveal -> long rain.
RAIN_BEFORE_OUTSIDE = 6.0
RAIN_BETWEEN = 2.0
RAIN_AFTER_INSIDE = 8.0
FORM_SECONDS = 1.55
HOLD_SECONDS = 3.0
MELT_SECONDS = 1.65


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def format_temp(value: Optional[float]) -> str:
    return "--.-°F" if value is None else f"{value:.1f}°F"


@dataclass
class RevealGlyph:
    start_x: float
    start_y: float
    target_x: float
    target_y: float
    glyph: str
    delay: float
    fall_speed: float
    wobble: float


class NeoReveal:
    """Matrix glyphs gather into a temperature, hold, then dissolve back into rain."""

    def __init__(
        self,
        title: str,
        value: str,
        accent: Tuple[int, int, int],
        title_font: pygame.font.Font,
        value_font: pygame.font.Font,
        glyph_font: pygame.font.Font,
    ) -> None:
        self.title = title
        self.value = value
        self.accent = accent
        self.title_font = title_font
        self.value_font = value_font
        self.glyph_font = glyph_font
        self.phase = "form"
        self.elapsed = 0.0
        self.finished = False
        self.glyphs: List[RevealGlyph] = []
        self.cache: Dict[Tuple[str, Tuple[int, int, int]], pygame.Surface] = {}
        self._build_shape()

    def _build_shape(self) -> None:
        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        title_img = self.title_font.render(self.title, True, (255, 255, 255))
        value_img = self.value_font.render(self.value, True, (255, 255, 255))

        title_rect = title_img.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.42)))
        value_rect = value_img.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.62)))
        mask.blit(title_img, title_rect)
        mask.blit(value_img, value_rect)

        targets: List[Tuple[int, int]] = []
        step = 5
        for y in range(35, HEIGHT - 20, step):
            for x in range(15, WIDTH - 15, step):
                if mask.get_at((x, y)).a > 40:
                    targets.append((x, y))

        if len(targets) > 430:
            targets = random.sample(targets, 430)

        for tx, ty in targets:
            # Start particles mostly above the screen so the letters feel like
            # they are being discovered inside the falling code, with a few
            # entering from the side for the characteristic Neo-code shimmer.
            if random.random() < 0.76:
                sx = tx + random.uniform(-36.0, 36.0)
                sy = random.uniform(-170.0, -12.0)
            elif random.random() < 0.5:
                sx = random.uniform(-70.0, -8.0)
                sy = random.uniform(0.0, HEIGHT)
            else:
                sx = random.uniform(WIDTH + 8.0, WIDTH + 70.0)
                sy = random.uniform(0.0, HEIGHT)

            self.glyphs.append(
                RevealGlyph(
                    start_x=sx,
                    start_y=sy,
                    target_x=float(tx),
                    target_y=float(ty),
                    glyph=random.choice(MATRIX_CHARS),
                    delay=random.uniform(0.0, 0.32),
                    fall_speed=random.uniform(95.0, 185.0),
                    wobble=random.uniform(-18.0, 18.0),
                )
            )

    def _glyph_image(self, glyph: str, color: Tuple[int, int, int]) -> pygame.Surface:
        key = (glyph, color)
        image = self.cache.get(key)
        if image is None:
            image = self.glyph_font.render(glyph, True, color)
            self.cache[key] = image
        return image

    @staticmethod
    def _draw_centered(
        screen: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        y: int,
        alpha: int = 255,
    ) -> None:
        shadow = font.render(text, True, SHADOW)
        image = font.render(text, True, color)
        if alpha < 255:
            shadow.set_alpha(alpha)
            image.set_alpha(alpha)
        rect = image.get_rect(center=(WIDTH // 2, y))
        screen.blit(shadow, rect.move(2, 2))
        screen.blit(image, rect)

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.phase == "form" and self.elapsed >= FORM_SECONDS:
            self.phase = "hold"
            self.elapsed = 0.0
        elif self.phase == "hold" and self.elapsed >= HOLD_SECONDS:
            self.phase = "melt"
            self.elapsed = 0.0
        elif self.phase == "melt" and self.elapsed >= MELT_SECONDS:
            self.finished = True

    def draw(self, screen: pygame.Surface) -> None:
        title_y = int(HEIGHT * 0.42)
        value_y = int(HEIGHT * 0.62)

        if self.phase == "form":
            for particle in self.glyphs:
                raw = (self.elapsed - particle.delay) / max(0.01, FORM_SECONDS - particle.delay)
                t = smoothstep(raw)
                if t <= 0.0:
                    continue
                x = particle.start_x + (particle.target_x - particle.start_x) * t
                y = particle.start_y + (particle.target_y - particle.start_y) * t
                # Early particles are green; the final lock-in gets pale white-green heads.
                if t > 0.86 and random.random() < 0.18:
                    color = WHITE_GREEN
                else:
                    color = (0, int(120 + 135 * t), int(28 + 48 * t))
                screen.blit(self._glyph_image(particle.glyph, color), (int(x), int(y)))

            crisp = int(255 * clamp((self.elapsed / FORM_SECONDS - 0.62) / 0.38, 0.0, 1.0))
            if crisp:
                self._draw_centered(screen, self.title, self.title_font, GREEN, title_y, crisp)
                self._draw_centered(screen, self.value, self.value_font, self.accent, value_y, crisp)

        elif self.phase == "hold":
            # Fully readable moment, while code still flickers through the letter shapes.
            self._draw_centered(screen, self.title, self.title_font, GREEN, title_y)
            self._draw_centered(screen, self.value, self.value_font, self.accent, value_y)

            for _ in range(38):
                particle = random.choice(self.glyphs)
                color = WHITE_GREEN if random.random() < 0.14 else GREEN
                x = particle.target_x + random.uniform(-2.0, 2.0)
                y = particle.target_y + random.uniform(-2.0, 2.0)
                screen.blit(self._glyph_image(random.choice(MATRIX_CHARS), color), (int(x), int(y)))

        else:  # melt
            t = smoothstep(self.elapsed / MELT_SECONDS)
            alpha = int(255 * (1.0 - t))
            if alpha > 0:
                self._draw_centered(screen, self.title, self.title_font, GREEN, title_y, alpha)
                self._draw_centered(screen, self.value, self.value_font, self.accent, value_y, alpha)

            for particle in self.glyphs:
                x = particle.target_x + math.sin(self.elapsed * 8.0 + particle.target_y * 0.055) * particle.wobble * t
                y = particle.target_y + particle.fall_speed * (t ** 1.65)
                color = WHITE_GREEN if random.random() < 0.06 else GREEN
                image = self._glyph_image(particle.glyph, color)
                if alpha < 255:
                    image = image.copy()
                    image.set_alpha(alpha)
                screen.blit(image, (int(x), int(y)))


class MatrixDashboard:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS - Neo Temperature Reveal")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()

        self.rain = DashboardRain()
        self.data = LiveData()
        self.data.refresh(force=True)

        self.clock_font = choose_font(max(32, min(56, int(WIDTH * 0.145))), bold=True)
        self.ampm_font = choose_matrix_font(max(8, min(12, int(WIDTH * 0.027))), bold=True)
        self.title_font = choose_matrix_font(max(28, min(42, int(WIDTH * 0.090))), bold=True)
        self.value_font = choose_font(max(46, min(66, int(WIDTH * 0.135))), bold=True)
        self.glyph_font = choose_matrix_font(max(9, min(13, int(WIDTH * 0.027))), bold=True)

        self.mode = "rain_before"
        self.mode_elapsed = 0.0
        self.reveal: Optional[NeoReveal] = None

    def _make_reveal(self, title: str, value: Optional[float]) -> NeoReveal:
        return NeoReveal(
            title,
            format_temp(value),
            temp_color(value),
            self.title_font,
            self.value_font,
            self.glyph_font,
        )

    def _draw_clock(self) -> None:
        now = datetime.now()
        clock_text = now.strftime("%I:%M").lstrip("0")
        ampm = now.strftime("%p")

        shadow = self.clock_font.render(clock_text, True, SHADOW)
        image = self.clock_font.render(clock_text, True, GREEN)
        rect = image.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.11)))
        self.screen.blit(shadow, rect.move(1, 2))
        self.screen.blit(image, rect)

        ampm_img = self.ampm_font.render(ampm, True, GREEN)
        ampm_rect = ampm_img.get_rect(midleft=(rect.right + 5, rect.centery + 4))
        self.screen.blit(ampm_img, ampm_rect)

    def _advance(self) -> None:
        if self.mode == "rain_before":
            self.data.refresh(force=True)
            self.reveal = self._make_reveal("OUTSIDE", self.data.outside_f)
            self.mode = "outside"
        elif self.mode == "outside":
            self.reveal = None
            self.mode = "rain_between"
        elif self.mode == "rain_between":
            self.data.refresh(force=True)
            self.reveal = self._make_reveal("INSIDE", self.data.inside_f)
            self.mode = "inside"
        elif self.mode == "inside":
            self.reveal = None
            self.mode = "rain_after"
        else:
            self.mode = "rain_before"
        self.mode_elapsed = 0.0

    def update(self, dt: float) -> None:
        self.data.refresh()
        energy = 0.58 if self.reveal is not None else 0.42
        self.rain.update(dt, energy)
        self.mode_elapsed += dt

        if self.reveal is not None:
            self.reveal.update(dt)
            if self.reveal.finished:
                self._advance()
            return

        duration = {
            "rain_before": RAIN_BEFORE_OUTSIDE,
            "rain_between": RAIN_BETWEEN,
            "rain_after": RAIN_AFTER_INSIDE,
        }.get(self.mode, RAIN_AFTER_INSIDE)
        if self.mode_elapsed >= duration:
            self._advance()

    def draw(self) -> None:
        self.screen.fill(BLACK)

        # Run the code thicker/brighter than the old dashboard. During reveals,
        # the same code continues behind the forming temperature instead of cutting away.
        energy = 0.62 if self.reveal is not None else 0.48
        self.rain.draw(self.screen, energy)

        if self.reveal is None:
            self._draw_clock()
        else:
            # Slight shadow behind the reveal gives the code-world shape a moment
            # to become readable without ever replacing the Matrix background.
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 54))
            self.screen.blit(veil, (0, 0))
            self.reveal.draw(self.screen)

        pygame.display.flip()

    def run(self) -> None:
        last = time.monotonic()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                        self._advance()

            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now

            self.update(dt)
            self.draw()
            self.timer.tick(FPS)


def main() -> int:
    try:
        MatrixDashboard().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix dashboard failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
