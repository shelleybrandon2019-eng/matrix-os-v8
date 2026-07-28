#!/usr/bin/env python3
"""Matrix OS V10: Pi temperature cinema, with the clock owned by ESP32."""
from __future__ import annotations

import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

import pygame

from live_data import LiveData
from main import (
    BLACK,
    DIM_GREEN,
    FULLSCREEN,
    HEAD_GREEN,
    HEIGHT,
    WIDTH,
    CinematicRain,
    RainTextTransition,
    choose_font,
    choose_matrix_font,
    clamp,
    ease_in_out,
    temp_color,
)

FPS = 60
SCENE_SECONDS = 5.5
FORM_SECONDS = 1.65
HOLD_SECONDS = 4.8
MELT_SECONDS = 1.85
ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "scenes"

SCENES = [
    ("access_hall", "hallway"), ("reflection_lobby", "hallway"),
    ("wet_motel_corridor", "hallway"), ("server_aisle", "hallway"),
    ("underground_bunker", "hallway"), ("elevator_arrival", "hallway"),
    ("apartment_hall", "hallway"), ("catwalk_machine_room", "hallway"),
    ("security_checkpoint", "scan"), ("stairwell_descent", "hallway"),
    ("city_rain_street", "city"), ("neon_alley", "city"),
    ("rooftop_skyline", "city"), ("subway_entrance", "city"),
    ("bridge_walkway", "city"), ("overpass_storm", "storm"),
    ("fire_escape", "city"), ("shipping_yard", "city"),
    ("underpass_tunnel", "hallway"), ("motel_sign_street", "city"),
    ("code_waterfall", "code"), ("digital_void", "code"),
    ("data_vortex", "portal"), ("grid_floor_columns", "code"),
    ("cracked_code_wall", "breach"), ("shattered_glyph_glass", "breach"),
    ("code_portal_ring", "portal"), ("digital_canyon", "code"),
    ("floating_code_islands", "code"), ("fractal_cathedral", "code"),
    ("agent_corridor", "agent"), ("agent_scan", "agent"),
    ("agent_rooftop", "agent"), ("agent_subway", "agent"),
    ("shadow_crossing", "agent"), ("sentinel_unit", "robot"),
    ("runner_bot", "robot"), ("drone_scan", "robot"),
    ("machine_eye", "robot"), ("repair_bay", "robot"),
    ("outside_lightning", "storm"), ("code_storm", "storm"),
    ("thunder_rooftop", "storm"), ("electric_arc_room", "storm"),
    ("storm_bridge", "storm"), ("breach_slit", "breach"),
    ("signal_breach", "breach"), ("bullet_time_hall", "bullet"),
    ("frozen_rain", "bullet"), ("final_code_city", "city"),
]


def cover(image: pygame.Surface) -> pygame.Surface:
    scale = max(WIDTH / image.get_width(), HEIGHT / image.get_height())
    size = (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale)))
    image = pygame.transform.smoothscale(image, size)
    x = (image.get_width() - WIDTH) // 2
    y = (image.get_height() - HEIGHT) // 2
    return image.subsurface((x, y, WIDTH, HEIGHT)).copy()


class SceneAssets:
    def __init__(self) -> None:
        self.cache: dict[str, Optional[pygame.Surface]] = {}

    def get(self, slug: str) -> Optional[pygame.Surface]:
        if slug in self.cache:
            return self.cache[slug]
        candidates = []
        folder = ASSET_ROOT / slug
        if folder.is_dir():
            for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                candidates.extend(folder.glob(pattern))
        direct = ASSET_ROOT / f"{slug}.png"
        if direct.exists():
            candidates.append(direct)
        if not candidates:
            self.cache[slug] = None
            return None
        try:
            image = cover(pygame.image.load(str(random.choice(candidates))).convert())
            dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dark.fill((0, 20, 7, 125))
            image.blit(dark, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            green = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            green.fill((0, 55, 12, 70))
            image.blit(green, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self.cache[slug] = image
            return image
        except pygame.error:
            self.cache[slug] = None
            return None


class Director:
    EVENTS = (("outside", "OUTSIDE"), ("inside", "INSIDE"))

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN if FULLSCREEN else 0)
        pygame.mouse.set_visible(False)
        pygame.display.set_caption("Matrix OS V10 - Temperature Cinema")
        self.timer = pygame.time.Clock()
        self.rain = CinematicRain()
        self.data = LiveData()
        self.data.refresh(force=True)
        self.assets = SceneAssets()
        self.title_font = choose_font(66, bold=True)
        self.value_font = choose_font(92, bold=True)
        self.tiny_font = choose_matrix_font(9, bold=True)
        self.label_font = choose_font(14, bold=True)
        self.event_index = 0
        self.scene_index = 0
        self.phase = "scene"
        self.phase_start = time.monotonic()
        self.transition: Optional[RainTextTransition] = None

    def elapsed(self) -> float:
        return time.monotonic() - self.phase_start

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.phase_start = time.monotonic()

    def current_scene(self):
        return SCENES[self.scene_index % len(SCENES)]

    def event_data(self):
        key, title = self.EVENTS[self.event_index]
        value = self.data.outside_f if key == "outside" else self.data.inside_f
        text = "--°F" if value is None else f"{value:.0f}°F"
        return title, text, temp_color(value)

    def begin_form(self) -> None:
        title, value, accent = self.event_data()
        self.transition = RainTextTransition(
            self.rain, title, value, accent,
            self.title_font, self.value_font, self.tiny_font,
        )
        self.set_phase("form")

    def finish(self) -> None:
        self.transition = None
        self.event_index = (self.event_index + 1) % len(self.EVENTS)
        self.scene_index = (self.scene_index + 1) % len(SCENES)
        self.set_phase("scene")

    def update(self, dt: float) -> None:
        self.data.refresh()
        self.rain.update(dt, 0.30 if self.phase != "scene" else 0.08)
        e = self.elapsed()
        if self.phase == "scene" and e >= SCENE_SECONDS:
            self.begin_form()
        elif self.phase == "form" and self.transition:
            self.transition.update(dt)
            if self.transition.form_done():
                self.set_phase("hold")
        elif self.phase == "hold" and e >= HOLD_SECONDS and self.transition:
            self.transition.start_melt()
            self.set_phase("melt")
        elif self.phase == "melt" and self.transition:
            self.transition.update(dt)
            if self.transition.melt_done():
                self.finish()

    def draw_hallway(self, p: float) -> None:
        cx = WIDTH // 2
        pygame.draw.polygon(self.screen, (0, 16, 5), [(0, 0), (cx - 62, 100), (cx - 62, 235), (0, HEIGHT)])
        pygame.draw.polygon(self.screen, (0, 12, 4), [(WIDTH, 0), (cx + 62, 100), (cx + 62, 235), (WIDTH, HEIGHT)])
        for i in range(8):
            y = 55 + i * 31
            half = int(28 + y * 0.60)
            pygame.draw.line(self.screen, (0, 65 + i * 4, 20), (cx - half, y), (cx + half, y), 1)
        pygame.draw.rect(self.screen, (0, 90, 25), (cx - 42, 80, 84, 160), 2)

    def draw_city(self, p: float) -> None:
        random.seed(self.scene_index + 440)
        x = 0
        while x < WIDTH:
            w = random.randint(24, 64)
            h = random.randint(70, 225)
            pygame.draw.rect(self.screen, (0, random.randint(10, 35), 5), (x, HEIGHT - h, w, h))
            for wy in range(HEIGHT - h + 12, HEIGHT - 10, 16):
                if random.random() < 0.45:
                    pygame.draw.rect(self.screen, (0, random.randint(55, 135), 25), (x + 7, wy, 3, 5))
            x += w + random.randint(3, 10)
        pygame.draw.line(self.screen, (0, 100, 30), (0, 266), (WIDTH, 266), 2)

    def draw_portal(self, p: float) -> None:
        cx, cy = WIDTH // 2, 170
        pulse = 1.0 + math.sin(p * math.tau * 2) * 0.08
        for r in range(82, 18, -8):
            color = (0, max(25, 200 - r * 2), 35)
            pygame.draw.arc(self.screen, color, (cx - r * pulse, cy - r * pulse, r * 2 * pulse, r * 2 * pulse), p * 4, p * 4 + 4.8, 2)

    def draw_agent(self, p: float) -> None:
        x = int(-55 + (WIDTH + 110) * ease_in_out(p))
        y = 150
        pygame.draw.circle(self.screen, BLACK, (x, y - 28), 25)
        pygame.draw.circle(self.screen, (0, 170, 50), (x, y - 28), 25, 2)
        pygame.draw.polygon(self.screen, BLACK, [(x - 25, y), (x + 25, y), (x + 42, 255), (x - 42, 255)])
        pygame.draw.lines(self.screen, (0, 145, 42), False, [(x - 25, y), (x - 42, 255), (x + 42, 255), (x + 25, y)], 2)
        pygame.draw.line(self.screen, HEAD_GREEN, (x - 18, y - 31), (x - 2, y - 31), 3)
        pygame.draw.line(self.screen, HEAD_GREEN, (x + 2, y - 31), (x + 18, y - 31), 3)

    def draw_robot(self, p: float) -> None:
        x = int(-45 + (WIDTH + 90) * p)
        y = 185 - int(abs(math.sin(p * math.tau * 5)) * 8)
        pygame.draw.rect(self.screen, BLACK, (x - 20, y - 40, 40, 32))
        pygame.draw.rect(self.screen, (0, 210, 58), (x - 20, y - 40, 40, 32), 2)
        pygame.draw.circle(self.screen, HEAD_GREEN, (x - 8, y - 25), 3)
        pygame.draw.circle(self.screen, HEAD_GREEN, (x + 8, y - 25), 3)
        pygame.draw.rect(self.screen, BLACK, (x - 26, y, 52, 48))
        pygame.draw.rect(self.screen, (0, 180, 50), (x - 26, y, 52, 48), 2)

    def draw_storm(self, p: float) -> None:
        if math.sin(p * math.tau * 5) > 0.82:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((120, 255, 160, 90))
            self.screen.blit(flash, (0, 0))
        pts = [(WIDTH // 2, 0)]
        r = random.Random(self.scene_index)
        x, y = WIDTH // 2, 0
        while y < HEIGHT:
            x += r.randint(-34, 34)
            y += r.randint(18, 34)
            pts.append((x, y))
        pygame.draw.lines(self.screen, HEAD_GREEN, False, pts, 3)

    def draw_breach(self, p: float) -> None:
        x = WIDTH // 2
        width = int(4 + math.sin(p * math.pi) * 105)
        pygame.draw.line(self.screen, HEAD_GREEN, (x, 25), (x, HEIGHT - 20), max(2, width // 18))
        for y in range(25, HEIGHT - 20, 14):
            dx = int(math.sin(y * 0.18 + p * 12) * width)
            pygame.draw.line(self.screen, (0, 145, 40), (x - dx, y), (x + dx, y + 3), 1)

    def draw_bullet(self, p: float) -> None:
        for i in range(30):
            a = i * 0.7
            x = WIDTH // 2 + math.cos(a) * (30 + i * 6)
            y = HEIGHT // 2 + math.sin(a) * (20 + i * 3)
            pygame.draw.circle(self.screen, (80, 255, 120), (int(x), int(y)), 2)
        scan = int(p * WIDTH)
        pygame.draw.line(self.screen, HEAD_GREEN, (scan, 0), (scan, HEIGHT), 2)

    def draw_scene(self) -> None:
        slug, category = self.current_scene()
        image = self.assets.get(slug)
        if image:
            self.screen.blit(image, (0, 0))
        p = (self.elapsed() % SCENE_SECONDS) / SCENE_SECONDS
        if category == "hallway": self.draw_hallway(p)
        elif category == "city": self.draw_city(p)
        elif category in ("portal", "code"): self.draw_portal(p)
        elif category in ("agent", "scan"): self.draw_agent(p)
        elif category == "robot": self.draw_robot(p)
        elif category == "storm": self.draw_storm(p)
        elif category == "breach": self.draw_breach(p)
        elif category == "bullet": self.draw_bullet(p)
        label = slug.replace("_", " ").upper()
        image = self.label_font.render(label, True, (0, 115, 35))
        self.screen.blit(image, (12, HEIGHT - 24))

    def draw(self) -> None:
        self.screen.fill(BLACK)
        if self.phase == "scene":
            self.draw_scene()
        self.rain.draw(self.screen, 0.18 if self.phase == "scene" else 0.30)
        if self.transition and self.phase in ("form", "hold", "melt"):
            self.transition.draw(self.screen)
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
                        if self.phase == "scene": self.begin_form()
                        elif self.phase == "hold" and self.transition:
                            self.transition.start_melt(); self.set_phase("melt")
            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now
            self.update(dt)
            self.draw()
            self.timer.tick(FPS)


def main() -> int:
    try:
        Director().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix temperature cinema failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
