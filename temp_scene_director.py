#!/usr/bin/env python3
"""Matrix OS: ultra-dense code rain, giant cyber clock, dual Neo temperature reveal."""
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
WHITE_GREEN = (220, 255, 225)

MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "ｦｧｨｩｪｫｬｭｮｯｰﾞﾟ"
    "0123456789@#$%&*+=<>?/\\|:;.-_"
)

RAIN_SECONDS = 5.5
FORM_SECONDS = 1.55
HOLD_SECONDS = 3.6
MELT_SECONDS = 1.75


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
    """Huge angular neon clock that uses most of the screen width."""

    def __init__(self) -> None:
        self.ampm_font = choose_cyber_font(15, bold=True)
        self.glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    def draw_digit(self, surface: pygame.Surface, digit: str, x: int, y: int,
                   w: int, h: int, thickness: int, color) -> None:
        for seg in SEGMENTS.get(digit, ""):
            pygame.draw.polygon(surface, color, segment_polygon(x, y, w, h, thickness, seg))

    def draw(self, screen: pygame.Surface) -> None:
        now = datetime.now()
        text = now.strftime("%I:%M").lstrip("0")
        ampm = now.strftime("%p")

        digit_w = 76
        digit_h = 94
        thickness = 12
        gap = 8
        colon_w = 20

        widths = [colon_w if ch == ":" else digit_w for ch in text]
        total = sum(widths) + gap * (len(text) - 1)
        scale = min(1.0, (WIDTH - 28) / max(1, total))
        digit_w = int(digit_w * scale)
        digit_h = int(digit_h * scale)
        thickness = max(8, int(thickness * scale))
        gap = max(5, int(gap * scale))
        colon_w = max(14, int(colon_w * scale))
        widths = [colon_w if ch == ":" else digit_w for ch in text]
        total = sum(widths) + gap * (len(text) - 1)

        start_x = (WIDTH - total) // 2
        y = 4

        self.glow.fill((0, 0, 0, 0))
        x = start_x
        for ch, cw in zip(text, widths):
            if ch == ":":
                dot = max(7, thickness - 2)
                cx = x + cw // 2
                for cy in (y + digit_h // 3, y + digit_h * 2 // 3):
                    pygame.draw.rect(self.glow, (0,255,90,150),
                                     (cx-dot//2, cy-dot//2, dot, dot), border_radius=2)
            else:
                self.draw_digit(self.glow, ch, x, y, digit_w, digit_h,
                                thickness + 4, (0,155,50,90))
            x += cw + gap

        self.glow.set_alpha(145)
        screen.blit(self.glow, (0, 0))
        self.glow.set_alpha(255)

        x = start_x
        for ch, cw in zip(text, widths):
            if ch == ":":
                dot = max(7, thickness - 2)
                cx = x + cw // 2
                for cy in (y + digit_h // 3, y + digit_h * 2 // 3):
                    pygame.draw.rect(screen, GREEN,
                                     (cx-dot//2, cy-dot//2, dot, dot), border_radius=2)
            else:
                self.draw_digit(screen, ch, x, y, digit_w, digit_h, thickness, GREEN)
            x += cw + gap

        am = self.ampm_font.render(ampm, True, GREEN)
        am_shadow = self.ampm_font.render(ampm, True, SHADOW)
        am_rect = am.get_rect(topright=(WIDTH - 9, y + digit_h - 18))
        screen.blit(am_shadow, am_rect.move(1, 1))
        screen.blit(am, am_rect)


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
    """OUTSIDE and INSIDE form together from code and melt back into the rain."""

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
            ("OUTSIDE", label_font, GREEN, 132),
            (format_temp(outside), value_font, temp_color(outside), 171),
            ("INSIDE", label_font, GREEN, 222),
            (format_temp(inside), value_font, temp_color(inside), 261),
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
            image = font.render(text, True, (255,255,255))
            mask.blit(image, image.get_rect(center=(WIDTH//2, y)))

        targets: List[Tuple[int,int]] = []
        for y in range(112, 300, 5):
            for x in range(10, WIDTH-10, 5):
                if mask.get_at((x,y)).a > 35:
                    targets.append((x,y))
        if len(targets) > 570:
            targets = random.sample(targets, 570)

        for tx, ty in targets:
            if random.random() < 0.82:
                sx = tx + random.uniform(-34, 34)
                sy = random.uniform(-120, 105)
            elif random.random() < 0.5:
                sx = random.uniform(-65, -5)
                sy = random.uniform(90, HEIGHT)
            else:
                sx = random.uniform(WIDTH+5, WIDTH+65)
                sy = random.uniform(90, HEIGHT)
            self.particles.append(RevealGlyph(
                sx, sy, float(tx), float(ty), random.choice(MATRIX_CHARS),
                random.uniform(0.0,0.34), random.uniform(95,190),
                random.uniform(-18,18)))

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.phase == "form" and self.elapsed >= FORM_SECONDS:
            self.phase, self.elapsed = "hold", 0.0
        elif self.phase == "hold" and self.elapsed >= HOLD_SECONDS:
            self.phase, self.elapsed = "melt", 0.0
        elif self.phase == "melt" and self.elapsed >= MELT_SECONDS:
            self.finished = True

    def draw_text(self, screen: pygame.Surface, alpha: int = 255) -> None:
        for text, font, color, y in self.layout:
            shadow = font.render(text, True, SHADOW)
            image = font.render(text, True, color)
            if alpha < 255:
                shadow.set_alpha(alpha)
                image.set_alpha(alpha)
            rect = image.get_rect(center=(WIDTH//2, y))
            screen.blit(shadow, rect.move(2,2))
            screen.blit(image, rect)

    def draw(self, screen: pygame.Surface) -> None:
        if self.phase == "form":
            for p in self.particles:
                raw = (self.elapsed - p.delay) / max(0.01, FORM_SECONDS-p.delay)
                t = smoothstep(raw)
                if t <= 0:
                    continue
                x = p.sx + (p.tx-p.sx)*t
                y = p.sy + (p.ty-p.sy)*t
                color = WHITE_GREEN if t > .88 and random.random() < .16 else (0, int(120+135*t), int(25+55*t))
                screen.blit(self.glyph_image(p.glyph,color),(int(x),int(y)))
            crisp = int(255*clamp((self.elapsed/FORM_SECONDS-.60)/.40,0,1))
            if crisp:
                self.draw_text(screen, crisp)

        elif self.phase == "hold":
            self.draw_text(screen)
            for _ in range(48):
                p = random.choice(self.particles)
                color = WHITE_GREEN if random.random() < .16 else GREEN
                screen.blit(self.glyph_image(random.choice(MATRIX_CHARS),color),
                            (int(p.tx+random.uniform(-2,2)), int(p.ty+random.uniform(-2,2))))

        else:
            t = smoothstep(self.elapsed/MELT_SECONDS)
            alpha = int(255*(1-t))
            if alpha:
                self.draw_text(screen, alpha)
            for p in self.particles:
                x = p.tx + math.sin(self.elapsed*8+p.ty*.05)*p.wobble*t
                y = p.ty + p.fall*(t**1.65)
                image = self.glyph_image(p.glyph, WHITE_GREEN if random.random()<.07 else GREEN)
                if alpha < 255:
                    image = image.copy(); image.set_alpha(alpha)
                screen.blit(image,(int(x),int(y)))


class MatrixDashboard:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS - Giant Cyber Clock")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()

        self.rain = DashboardRain()
        self.data = LiveData()
        self.data.refresh(force=True)
        self.clock = CyberClock()

        self.label_font = choose_cyber_font(27, bold=True)
        self.value_font = choose_cyber_font(43, bold=True)
        self.glyph_font = choose_matrix_font(11, bold=True)

        self.reveal: Optional[DualNeoReveal] = None
        self.elapsed = 0.0

    def start_reveal(self) -> None:
        self.data.refresh(force=True)
        self.reveal = DualNeoReveal(self.data.outside_f, self.data.inside_f,
                                    self.label_font, self.value_font, self.glyph_font)
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        self.data.refresh()
        energy = 0.74 if self.reveal else 0.62
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
        self.rain.draw(self.screen, 0.78 if self.reveal else 0.68)

        if self.reveal:
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            # Only darken the lower reveal area; keep the giant clock/rain alive.
            pygame.draw.rect(veil, (0,0,0,42), (0,112,WIDTH,188))
            self.screen.blit(veil,(0,0))
            self.reveal.draw(self.screen)

        # Clock is ALWAYS last/top and therefore always visible.
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
            dt = min(.05, now-last)
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
