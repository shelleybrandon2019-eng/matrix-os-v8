#!/usr/bin/env python3
"""Matrix OS: clean fast rain, giant 24-hour cyber clock, dual Neo temp melt."""
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
from main import BLACK, FULLSCREEN, HEIGHT, WIDTH, choose_matrix_font, temp_color

FPS = 60
GREEN = (0, 255, 90)
SHADOW = (0, 24, 8)
WHITE_GREEN = (218, 255, 226)

MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "ｦｧｨｩｪｫｬｭｮｯｰﾞﾟ"
    "0123456789@#$%&*+=<>?/\\|:;.-_"
)

# A complete visual cycle stays quick and alive without hard-resetting the app.
RAIN_SECONDS = 6.0
FORM_SECONDS = 1.40
HOLD_SECONDS = 2.25
MELT_SECONDS = 2.65


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def format_temp(value: Optional[float]) -> str:
    return "--.-°F" if value is None else f"{value:.1f}°F"


def choose_cyber_font(size: int, *, bold: bool = True) -> pygame.font.Font:
    for name in (
        "Orbitron", "Audiowide", "Michroma", "Rajdhani", "Exo 2",
        "Eurostile", "Bank Gothic", "DejaVu Sans Mono",
        "Liberation Mono", "monospace",
    ):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


SEGMENTS = {
    "0": "abcdef",
    "1": "bc",
    "2": "abdeg",
    "3": "abcdg",
    "4": "bcfg",
    "5": "acdfg",
    "6": "acdefg",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
}


def segment_polygon(x: int, y: int, w: int, h: int, t: int, key: str) -> List[Tuple[int, int]]:
    b = max(2, t // 3)
    mid = h // 2
    if key == "a":
        return [(x+b,y),(x+w-b,y),(x+w,y+b),(x+w-b,y+t),(x+b,y+t),(x,y+b)]
    if key == "g":
        yy = y + mid - t//2
        return [(x+b,yy),(x+w-b,yy),(x+w,yy+t//2),(x+w-b,yy+t),(x+b,yy+t),(x,yy+t//2)]
    if key == "d":
        yy = y + h - t
        return [(x+b,yy),(x+w-b,yy),(x+w,yy+t-b),(x+w-b,yy+t),(x+b,yy+t),(x,yy+t-b)]
    if key == "f":
        return [(x,y+b),(x+b,y),(x+t,y+b),(x+t,y+mid-b),(x+b,y+mid),(x,y+mid-b)]
    if key == "b":
        xx = x + w - t
        return [(xx,y+b),(xx+t-b,y),(xx+t,y+b),(xx+t,y+mid-b),(xx+t-b,y+mid),(xx,y+mid-b)]
    if key == "e":
        yy = y + mid
        return [(x,yy+b),(x+b,yy),(x+t,yy+b),(x+t,y+h-b),(x+b,y+h),(x,y+h-b)]
    xx = x + w - t
    yy = y + mid
    return [(xx,yy+b),(xx+t-b,yy),(xx+t,yy+b),(xx+t,y+h-b),(xx+t-b,y+h),(xx,y+h-b)]


class CyberClock:
    """Oversized angular 24-hour neon clock."""

    def __init__(self) -> None:
        self.glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    def draw_digit(self, surface: pygame.Surface, digit: str, x: int, y: int,
                   w: int, h: int, thickness: int, color) -> None:
        for seg in SEGMENTS.get(digit, ""):
            pygame.draw.polygon(surface, color, segment_polygon(x, y, w, h, thickness, seg))

    def draw(self, screen: pygame.Surface) -> None:
        # 24-hour time, including the leading zero.
        text = datetime.now().strftime("%H:%M")

        # Bigger than the old clock but still leaves a small edge margin on 480px.
        digit_w = 96
        digit_h = 112
        thickness = 15
        gap = 8
        colon_w = 18

        widths = [colon_w if ch == ":" else digit_w for ch in text]
        total = sum(widths) + gap * (len(text) - 1)
        scale = min(1.0, (WIDTH - 18) / max(1, total))

        digit_w = int(digit_w * scale)
        digit_h = int(digit_h * scale)
        thickness = max(9, int(thickness * scale))
        gap = max(5, int(gap * scale))
        colon_w = max(12, int(colon_w * scale))

        widths = [colon_w if ch == ":" else digit_w for ch in text]
        total = sum(widths) + gap * (len(text) - 1)
        start_x = (WIDTH - total) // 2
        y = 1

        self.glow.fill((0, 0, 0, 0))
        x = start_x
        for ch, cw in zip(text, widths):
            if ch == ":":
                dot = max(8, thickness - 3)
                cx = x + cw // 2
                for cy in (y + digit_h // 3, y + digit_h * 2 // 3):
                    pygame.draw.rect(
                        self.glow,
                        (0, 255, 90, 150),
                        (cx-dot//2, cy-dot//2, dot, dot),
                        border_radius=2,
                    )
            else:
                self.draw_digit(
                    self.glow, ch, x, y, digit_w, digit_h,
                    thickness + 5, (0, 160, 52, 92),
                )
            x += cw + gap

        self.glow.set_alpha(150)
        screen.blit(self.glow, (0, 0))
        self.glow.set_alpha(255)

        x = start_x
        for ch, cw in zip(text, widths):
            if ch == ":":
                dot = max(8, thickness - 3)
                cx = x + cw // 2
                for cy in (y + digit_h // 3, y + digit_h * 2 // 3):
                    pygame.draw.rect(
                        screen, GREEN,
                        (cx-dot//2, cy-dot//2, dot, dot),
                        border_radius=2,
                    )
            else:
                self.draw_digit(
                    screen, ch, x, y, digit_w, digit_h, thickness, GREEN
                )
            x += cw + gap


@dataclass
class RevealGlyph:
    sx: float
    sy: float
    tx: float
    ty: float
    glyph: str
    delay: float
    fall: float
    wobble: float


class DualNeoReveal:
    """Temps form cleanly, hold solid, then physically melt downward into rain."""

    MELT_COLORS = (
        (210, 255, 220),
        (145, 255, 175),
        (78, 250, 132),
        (24, 240, 95),
        (0, 220, 68),
    )

    def __init__(self, outside: Optional[float], inside: Optional[float],
                 label_font: pygame.font.Font, value_font: pygame.font.Font,
                 glyph_font: pygame.font.Font) -> None:
        self.label_font = label_font
        self.value_font = value_font
        self.glyph_font = glyph_font
        self.phase = "form"
        self.elapsed = 0.0
        self.finished = False
        self.cache: Dict[Tuple[str, Tuple[int,int,int]], pygame.Surface] = {}
        self.particles: List[RevealGlyph] = []
        self.layout = [
            ("OUTSIDE", label_font, GREEN, 137),
            (format_temp(outside), value_font, temp_color(outside), 178),
            ("INSIDE", label_font, GREEN, 229),
            (format_temp(inside), value_font, temp_color(inside), 270),
        ]
        self.build_particles()

    def glyph_image(self, glyph: str, color: Tuple[int,int,int]) -> pygame.Surface:
        key = (glyph, color)
        image = self.cache.get(key)
        if image is None:
            image = self.glyph_font.render(glyph, True, color)
            self.cache[key] = image
        return image

    def build_particles(self) -> None:
        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for text, font, _color, y in self.layout:
            image = font.render(text, True, (255, 255, 255))
            mask.blit(image, image.get_rect(center=(WIDTH//2, y)))

        targets: List[Tuple[int, int]] = []
        for y in range(116, 304, 5):
            for x in range(8, WIDTH - 8, 5):
                if mask.get_at((x, y)).a > 35:
                    targets.append((x, y))

        # Enough material for a convincing dissolve without flooding the Pi.
        if len(targets) > 520:
            targets = random.sample(targets, 520)

        for tx, ty in targets:
            if random.random() < 0.88:
                sx = tx + random.uniform(-28, 28)
                sy = random.uniform(-105, 112)
            elif random.random() < 0.5:
                sx = random.uniform(-45, -5)
                sy = random.uniform(100, HEIGHT)
            else:
                sx = random.uniform(WIDTH + 5, WIDTH + 45)
                sy = random.uniform(100, HEIGHT)

            self.particles.append(
                RevealGlyph(
                    sx=sx,
                    sy=sy,
                    tx=float(tx),
                    ty=float(ty),
                    glyph=random.choice(MATRIX_CHARS),
                    delay=random.uniform(0.0, 0.28),
                    fall=random.uniform(150, 285),
                    wobble=random.uniform(-14, 14),
                )
            )

    def update(self, dt: float) -> None:
        self.elapsed += dt

        if self.phase == "form" and self.elapsed >= FORM_SECONDS:
            self.phase, self.elapsed = "hold", 0.0
        elif self.phase == "hold" and self.elapsed >= HOLD_SECONDS:
            self.phase, self.elapsed = "melt", 0.0
        elif self.phase == "melt" and self.elapsed >= MELT_SECONDS:
            self.finished = True

    def backdrop_alpha(self) -> int:
        """Darken the whole rain field so no hidden shape/image shows behind temps."""
        if self.phase == "form":
            t = smoothstep(self.elapsed / FORM_SECONDS)
            return int(235 * t)
        if self.phase == "hold":
            return 235

        t = smoothstep(self.elapsed / MELT_SECONDS)
        return int(235 * (1.0 - t))

    def draw_text(self, screen: pygame.Surface, alpha: int = 255) -> None:
        for text, font, color, y in self.layout:
            shadow = font.render(text, True, SHADOW)
            image = font.render(text, True, color)

            if alpha < 255:
                shadow.set_alpha(alpha)
                image.set_alpha(alpha)

            rect = image.get_rect(center=(WIDTH//2, y))
            screen.blit(shadow, rect.move(2, 2))
            screen.blit(image, rect)

    def draw(self, screen: pygame.Surface) -> None:
        if self.phase == "form":
            global_t = clamp(self.elapsed / FORM_SECONDS, 0.0, 1.0)

            # Code flies in, but gets out of the way as the clean solid text appears.
            particle_alpha = int(
                255 * (1.0 - smoothstep((global_t - 0.62) / 0.30))
            )

            if particle_alpha > 0:
                for p in self.particles:
                    raw = (self.elapsed - p.delay) / max(0.01, FORM_SECONDS - p.delay)
                    t = smoothstep(raw)
                    if t <= 0:
                        continue

                    x = p.sx + (p.tx - p.sx) * t
                    y = p.sy + (p.ty - p.sy) * t
                    stage = min(4, int(t * 4.99))
                    image = self.glyph_image(p.glyph, self.MELT_COLORS[4 - stage])
                    if particle_alpha < 255:
                        image = image.copy()
                        image.set_alpha(particle_alpha)
                    screen.blit(image, (int(x), int(y)))

            crisp = int(255 * smoothstep((global_t - 0.50) / 0.34))
            if crisp:
                self.draw_text(screen, crisp)

        elif self.phase == "hold":
            # Intentionally clean: no random glyphs or rain drawn through the letters.
            self.draw_text(screen)

        else:
            t = clamp(self.elapsed / MELT_SECONDS, 0.0, 1.0)
            drop_t = smoothstep(t)

            # Keep it solid briefly, then the actual text gives way to falling code.
            text_fade = clamp((t - 0.12) / 0.34, 0.0, 1.0)
            text_alpha = int(255 * (1.0 - smoothstep(text_fade)))
            if text_alpha:
                self.draw_text(screen, text_alpha)

            particle_alpha = int(
                255 * (1.0 - smoothstep(clamp((t - 0.72) / 0.28, 0.0, 1.0)))
            )

            if particle_alpha:
                color_index = min(
                    len(self.MELT_COLORS) - 1,
                    int(drop_t * len(self.MELT_COLORS)),
                )
                color = self.MELT_COLORS[color_index]

                for p in self.particles:
                    # Mostly vertical fall: it should become rain, not explode sideways.
                    x = p.tx + math.sin(self.elapsed * 7.0 + p.ty * 0.04) * p.wobble * drop_t
                    y = p.ty + p.fall * (drop_t ** 1.55)
                    image = self.glyph_image(p.glyph, color)

                    if particle_alpha < 255:
                        image = image.copy()
                        image.set_alpha(particle_alpha)

                    screen.blit(image, (int(x), int(y)))


class MatrixDashboard:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS - 24H Cyber Clock")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()

        self.rain = DashboardRain()
        self.data = LiveData()
        self.data.refresh(force=True)
        self.clock = CyberClock()

        self.label_font = choose_cyber_font(29, bold=True)
        self.value_font = choose_cyber_font(46, bold=True)
        self.glyph_font = choose_matrix_font(11, bold=True)

        self.reveal: Optional[DualNeoReveal] = None
        self.elapsed = 0.0

    def start_reveal(self) -> None:
        # Use the latest cached sensor values. Do not force another network request
        # right at the transition; that can visibly freeze the rain on a Pi.
        self.data.refresh()
        self.reveal = DualNeoReveal(
            self.data.outside_f,
            self.data.inside_f,
            self.label_font,
            self.value_font,
            self.glyph_font,
        )
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        self.data.refresh()
        energy = 0.66 if self.reveal else 0.58
        self.rain.update(dt, energy)
        self.elapsed += dt

        if self.reveal:
            self.reveal.update(dt)
            if self.reveal.finished:
                self.reveal = None
                self.elapsed = 0.0
        elif self.elapsed >= RAIN_SECONDS:
            self.start_reveal()

    def draw(self) -> None:
        self.screen.fill(BLACK)
        self.rain.draw(self.screen, 0.64 if self.reveal else 0.58)

        if self.reveal:
            # Full-screen fade, not a rectangle/panel, so there is no visible
            # "thing behind" the temperature scene.
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((0, 0, 0, self.reveal.backdrop_alpha()))
            self.screen.blit(veil, (0, 0))
            self.reveal.draw(self.screen)

        # Clock stays on top and visible through every phase.
        self.clock.draw(self.screen)
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
                        self.start_reveal()

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
