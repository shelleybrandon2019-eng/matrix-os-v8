#!/usr/bin/env python3
"""Matrix Hub V12 — Sandman rain assembly.

480x320 Raspberry Pi dashboard:
- permanent Matrix rain
- compact clock
- one large temperature scene at a time
- label/value gather out of falling rain particles
- hold clearly, then crumble/melt back into the rain
- demo temperatures drift periodically (easy to swap back to live data later)
"""
from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime

os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame
from pygame.locals import FULLSCREEN, QUIT, KEYDOWN, K_ESCAPE, K_q

W, H = 480, 320
FPS = 60

BLACK = (0, 0, 0)
GREEN = (0, 255, 82)
GREEN_MID = (0, 176, 62)
GREEN_DIM = (0, 88, 35)
GREEN_FAINT = (0, 42, 18)
WHITE_GREEN = (205, 255, 220)
YELLOW = (255, 224, 36)
ORANGE = (255, 120, 25)
RED = (255, 52, 35)

GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz<>+-*/{}[]:;=#$%@!?|λμΩ"
LABELS = ("OUTSIDE", "INSIDE", "FRONT ROOM", "BEDROOM")

SCENE_SECONDS = 9.0
GATHER_END = 2.7
HOLD_END = 6.3
MELT_END = 8.5
TEMP_DRIFT_SECONDS = 18.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_out_cubic(x):
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 3


def ease_in_cubic(x):
    x = clamp(x, 0.0, 1.0)
    return x ** 3


def choose_font(size, bold=False):
    for name in ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "monospace"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def temp_color(v):
    if v >= 86:
        return ORANGE
    if v >= 78:
        return YELLOW
    if v <= 64:
        return (90, 210, 255)
    return GREEN


@dataclass
class RainColumn:
    x: int
    y: float
    speed: float
    length: int
    phase: int


class MatrixRain:
    def __init__(self, font):
        self.font = font
        self.char_h = max(10, font.get_height())
        self.columns = []
        self.cache = {}
        gap = 12
        for x in range(-4, W + 8, gap):
            self.columns.append(
                RainColumn(
                    x=x,
                    y=random.uniform(-H, H),
                    speed=random.uniform(62, 155),
                    length=random.randint(8, 22),
                    phase=random.randrange(10000),
                )
            )

    def update(self, dt):
        for c in self.columns:
            c.y += c.speed * dt
            if c.y - c.length * self.char_h > H + 30:
                c.y = random.uniform(-100, -10)
                c.speed = random.uniform(62, 155)
                c.length = random.randint(8, 22)
                c.phase = random.randrange(10000)

    def draw(self, screen, t, dim_factor=1.0):
        tick = int(t * 8)
        for col_i, c in enumerate(self.columns):
            for i in range(c.length):
                yy = int(c.y - i * self.char_h)
                if yy < -self.char_h or yy > H:
                    continue

                n = (c.phase + i * 19 + tick * 7 + col_i * 31) % len(GLYPHS)
                ch = GLYPHS[n]

                if i == 0:
                    color = WHITE_GREEN
                elif i < 3:
                    color = GREEN
                elif i < 8:
                    color = GREEN_MID
                else:
                    color = GREEN_DIM

                if dim_factor < 1.0:
                    color = tuple(int(v * dim_factor) for v in color)

                key = (ch, color)
                img = self.cache.get(key)
                if img is None:
                    img = self.font.render(ch, True, color)
                    self.cache[key] = img
                screen.blit(img, (c.x, yy))


@dataclass
class Particle:
    sx: float
    sy: float
    tx: float
    ty: float
    size: int
    drift: float
    phase: float
    color_mix: float
    vx: float = 0.0
    vy: float = 0.0


class SandText:
    def __init__(self, label_font, value_font):
        self.label_font = label_font
        self.value_font = value_font
        self.label = ""
        self.value_text = ""
        self.value_color = GREEN
        self.label_surface = None
        self.value_surface = None
        self.particles = []

    def _render_centered_mask(self, label, value_text):
        surf = pygame.Surface((W, H), pygame.SRCALPHA, 32)

        label_img = self.label_font.render(label, True, (255, 255, 255))
        value_img = self.value_font.render(value_text, True, (255, 255, 255))

        label_rect = label_img.get_rect(center=(W // 2, 137))
        value_rect = value_img.get_rect(center=(W // 2, 218))

        surf.blit(label_img, label_rect)
        surf.blit(value_img, value_rect)

        self.label_surface = (label_img, label_rect)
        self.value_surface = (value_img, value_rect)
        return surf, label_rect, value_rect

    def reset(self, label, value):
        self.label = label
        self.value_text = f"{value:.1f}°F"
        self.value_color = temp_color(value)
        mask_surf, label_rect, value_rect = self._render_centered_mask(self.label, self.value_text)
        mask = pygame.mask.from_surface(mask_surf)

        points = mask.outline()
        step = 4
        for y in range(78, 268, step):
            for x in range(24, W - 24, step):
                if mask.get_at((x, y)):
                    points.append((x, y))

        if len(points) > 1650:
            stride = max(1, len(points) // 1650)
            points = points[::stride][:1650]

        random.shuffle(points)
        self.particles = []
        for idx, (tx, ty) in enumerate(points):
            if random.random() < 0.78:
                sx = tx + random.uniform(-80, 80)
                sy = random.uniform(-260, -10)
            else:
                sx = random.choice((-1, 1)) * random.uniform(W * 0.55, W * 0.95) + W / 2
                sy = random.uniform(-40, H * 0.85)

            is_value = ty > 170
            self.particles.append(
                Particle(
                    sx=sx,
                    sy=sy,
                    tx=float(tx),
                    ty=float(ty),
                    size=random.choice((1, 2, 2, 2, 3)),
                    drift=random.uniform(-18, 18),
                    phase=random.uniform(0, math.tau),
                    color_mix=1.0 if is_value else 0.0,
                    vx=random.uniform(-42, 42),
                    vy=random.uniform(72, 175),
                )
            )

    def draw(self, screen, phase_t):
        if phase_t < GATHER_END:
            p = ease_out_cubic(phase_t / GATHER_END)
            for particle in self.particles:
                wobble = math.sin(particle.phase + phase_t * 5.5) * (1.0 - p) * 16
                x = particle.sx + (particle.tx - particle.sx) * p + wobble
                y = particle.sy + (particle.ty - particle.sy) * p

                base = self.value_color if particle.color_mix > 0.5 else GREEN
                k = 0.45 + 0.55 * p
                color = tuple(int(v * k) for v in base)
                pygame.draw.rect(screen, color, (int(x), int(y), particle.size, particle.size))

            if p > 0.84:
                alpha = int(255 * ((p - 0.84) / 0.16))
                self._draw_crisp(screen, alpha)
            return

        if phase_t < HOLD_END:
            self._draw_crisp(screen, 255)
            hold_t = phase_t - GATHER_END
            for i, particle in enumerate(self.particles[::8]):
                if (i + int(hold_t * 8)) % 4:
                    continue
                base = self.value_color if particle.color_mix > 0.5 else GREEN
                pygame.draw.rect(
                    screen,
                    base,
                    (
                        int(particle.tx + math.sin(particle.phase + hold_t * 3) * 1.5),
                        int(particle.ty + math.cos(particle.phase + hold_t * 2) * 1.0),
                        1,
                        2,
                    ),
                )
            return

        if phase_t < MELT_END:
            mp = (phase_t - HOLD_END) / (MELT_END - HOLD_END)
            fade = 1.0 - ease_in_cubic(mp)
            if mp < 0.18:
                self._draw_crisp(screen, int(255 * (1.0 - mp / 0.18)))

            for particle in self.particles:
                fall = ease_in_cubic(mp)
                x = particle.tx + particle.vx * fall * 0.85 + math.sin(
                    particle.phase + phase_t * 7
                ) * 5 * fall
                y = particle.ty + particle.vy * (fall ** 1.25) * 1.15 + 90 * fall * fall
                if y > H + 5:
                    continue
                base = self.value_color if particle.color_mix > 0.5 else GREEN
                color = tuple(int(v * max(0.18, fade)) for v in base)
                pygame.draw.rect(screen, color, (int(x), int(y), particle.size, particle.size))

    def _draw_crisp(self, screen, alpha):
        label_img, label_rect = self.label_surface
        value_img, value_rect = self.value_surface

        glow_label = self.label_font.render(self.label, True, (0, 110, 42))
        glow_value = self.value_font.render(self.value_text, True, tuple(max(0, v // 3) for v in self.value_color))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            screen.blit(glow_label, label_rect.move(dx, dy))
            screen.blit(glow_value, value_rect.move(dx, dy))

        label_final = self.label_font.render(self.label, True, GREEN)
        value_final = self.value_font.render(self.value_text, True, self.value_color)
        label_final.set_alpha(alpha)
        value_final.set_alpha(alpha)
        screen.blit(label_final, label_rect)
        screen.blit(value_final, value_rect)


class MatrixHub:
    def __init__(self):
        pygame.init()
        flags = FULLSCREEN
        self.screen = pygame.display.set_mode((W, H), flags)
        pygame.display.set_caption("Matrix Hub V12 - Sandman")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.rain_font = choose_font(17, bold=False)
        self.clock_font = choose_font(43, bold=True)
        self.ampm_font = choose_font(17, bold=True)
        self.label_font = choose_font(54, bold=True)
        self.value_font = choose_font(67, bold=True)
        self.tiny_font = choose_font(11, bold=True)

        self.rain = MatrixRain(self.rain_font)
        self.sand = SandText(self.label_font, self.value_font)

        self.temps = {
            "OUTSIDE": round(random.uniform(76.0, 88.0), 1),
            "INSIDE": round(random.uniform(69.0, 75.0), 1),
            "FRONT ROOM": round(random.uniform(71.0, 79.0), 1),
            "BEDROOM": round(random.uniform(66.0, 73.0), 1),
        }
        self.bounds = {
            "OUTSIDE": (65.0, 96.0, 0.9),
            "INSIDE": (67.0, 78.0, 0.35),
            "FRONT ROOM": (68.0, 83.0, 0.45),
            "BEDROOM": (64.0, 77.0, 0.40),
        }

        used = set()
        for label in LABELS:
            while self.temps[label] in used:
                lo, hi, _ = self.bounds[label]
                self.temps[label] = round(clamp(self.temps[label] + 0.3, lo, hi), 1)
            used.add(self.temps[label])

        self.scene_index = 0
        self.scene_started = time.monotonic()
        self.last_temp_drift = self.scene_started
        self.sand.reset(LABELS[self.scene_index], self.temps[LABELS[self.scene_index]])

    def drift_temperatures(self):
        for label in LABELS:
            lo, hi, max_step = self.bounds[label]
            step = random.choice((-1, -0.5, 0, 0, 0.5, 1)) * max_step
            self.temps[label] = round(clamp(self.temps[label] + step, lo, hi), 1)

        used = set()
        for label in LABELS:
            while self.temps[label] in used:
                lo, hi, _ = self.bounds[label]
                self.temps[label] = round(clamp(self.temps[label] + 0.2, lo, hi), 1)
            used.add(self.temps[label])

    def draw_clock(self):
        now = datetime.now()
        clock_text = now.strftime("%I:%M").lstrip("0")
        ampm = now.strftime("%p")

        img = self.clock_font.render(clock_text, True, GREEN)
        rect = img.get_rect(center=(W // 2 - 12, 34))

        shadow = self.clock_font.render(clock_text, True, (0, 55, 20))
        self.screen.blit(shadow, rect.move(2, 2))
        self.screen.blit(img, rect)

        am = self.ampm_font.render(ampm, True, GREEN)
        self.screen.blit(am, am.get_rect(midleft=(rect.right + 7, rect.centery + 4)))

        pygame.draw.line(self.screen, (0, 155, 52), (65, 63), (W - 65, 63), 1)

    def draw_status(self, phase_t):
        if phase_t >= MELT_END:
            msg = "MATRIX RAIN"
        elif phase_t < GATHER_END:
            msg = "ASSEMBLING"
        elif phase_t < HOLD_END:
            msg = "MATRIX ONLINE"
        else:
            msg = "DISSOLVING"

        img = self.tiny_font.render(msg, True, GREEN_DIM)
        self.screen.blit(img, img.get_rect(center=(W // 2, H - 10)))

    def next_scene(self, now):
        self.scene_index = (self.scene_index + 1) % len(LABELS)
        label = LABELS[self.scene_index]
        self.sand.reset(label, self.temps[label])
        self.scene_started = now

    def run(self):
        running = True
        last = time.monotonic()

        while running:
            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now

            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN and event.key in (K_ESCAPE, K_q):
                    running = False

            if now - self.last_temp_drift >= TEMP_DRIFT_SECONDS:
                self.drift_temperatures()
                self.last_temp_drift = now

            phase_t = now - self.scene_started
            if phase_t >= SCENE_SECONDS:
                self.next_scene(now)
                phase_t = 0.0

            self.rain.update(dt)

            self.screen.fill(BLACK)

            if GATHER_END <= phase_t < HOLD_END:
                rain_dim = 0.40
            elif HOLD_END <= phase_t < MELT_END:
                rain_dim = 0.62
            else:
                rain_dim = 0.84

            self.rain.draw(self.screen, now, rain_dim)
            self.draw_clock()
            self.sand.draw(self.screen, phase_t)
            self.draw_status(phase_t)

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    MatrixHub().run()
