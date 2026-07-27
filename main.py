#!/usr/bin/env python3
"""Matrix OS: dark cinematic Matrix rain with Inside/Outside form-and-melt transitions."""

from __future__ import annotations

import math
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import pygame

from live_data import LiveData


WIDTH, HEIGHT, FPS = 480, 320, 60
FULLSCREEN = os.getenv("MATRIX_FULLSCREEN", "1") != "0"

IDLE_SECONDS = 3.8
FORM_SECONDS = 1.75
HOLD_SECONDS = 4.8
MELT_SECONDS = 1.95

FLOOR_Y = 226

MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|"
)

BLACK = (0, 0, 0)
GREEN = (0, 205, 55)
BRIGHT_GREEN = (0, 255, 76)
DIM_GREEN = (0, 33, 12)
HEAD_GREEN = (205, 255, 215)

Color = Tuple[int, int, int]
Point = Tuple[float, float]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ease_in_out(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a: Color, b: Color, t: float) -> Color:
    t = clamp(t, 0.0, 1.0)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def choose_font(size: int, *, bold: bool = False) -> pygame.font.Font:
    for name in ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "monospace"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def choose_matrix_font(size: int, *, bold: bool = True) -> pygame.font.Font:
    for name in (
        "Noto Sans Mono CJK JP",
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAGothic",
        "TakaoGothic",
        "VL Gothic",
        "DejaVu Sans Mono",
    ):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def temp_color(value: Optional[float]) -> Color:
    if value is None:
        return HEAD_GREEN
    if value < 50:
        return (65, 145, 255)
    if value < 65:
        return (45, 215, 235)
    if value < 78:
        return (115, 255, 150)
    if value < 88:
        return (255, 205, 55)
    return (255, 75, 38)


def format_temp(value: Optional[float]) -> str:
    return "--°F" if value is None else f"{value:.1f}°F"


@dataclass
class RainStream:
    x: float
    y: float
    speed: float
    length: int
    glyphs: List[str]
    brightness: float
    spacing: int
    font: pygame.font.Font
    depth: int
    pulse: float = 1.0
    head_hot: bool = False
    drift: float = 0.0

    def reset(self, height: int) -> None:
        self.y = random.uniform(-height * 1.8, -20)
        if self.depth == 0:
            self.speed = random.uniform(16.0, 38.0)
            self.length = random.randint(24, 50)
            self.brightness = random.uniform(0.10, 0.25)
            self.head_hot = False
        elif self.depth == 1:
            self.speed = random.uniform(34.0, 78.0)
            self.length = random.randint(17, 34)
            self.brightness = random.uniform(0.24, 0.52)
            self.head_hot = random.random() < 0.16
        else:
            self.speed = random.uniform(76.0, 158.0)
            self.length = random.randint(12, 27)
            self.brightness = random.uniform(0.48, 0.88)
            self.head_hot = random.random() < 0.62

        self.glyphs = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
        self.pulse = 1.0
        self.drift = random.uniform(-0.12, 0.12)


class CinematicRain:
    """Dark layered code rain inspired by the Matrix city look."""

    LAYER_CONFIG = (
        # depth, font size, column spacing
        (0, 9, 12),
        (1, 13, 18),
        (2, 17, 27),
    )

    PALETTES = {
        0: (
            (0, 8, 3),
            (0, 14, 5),
            (0, 20, 7),
            (0, 27, 9),
            (0, 34, 11),
            (0, 42, 14),
            (0, 53, 17),
            (0, 66, 20),
        ),
        1: (
            (0, 12, 4),
            (0, 22, 7),
            (0, 34, 11),
            (0, 49, 15),
            (0, 67, 20),
            (0, 88, 25),
            (0, 112, 31),
            (0, 145, 39),
        ),
        2: (
            (0, 18, 7),
            (0, 31, 11),
            (0, 48, 16),
            (0, 70, 22),
            (0, 96, 29),
            (0, 128, 36),
            (0, 170, 46),
            (0, 220, 61),
        ),
    }

    def __init__(self) -> None:
        self.layers: List[RainStream] = []
        self.rain_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.reflection_surface = pygame.Surface((WIDTH, HEIGHT - FLOOR_Y), pygame.SRCALPHA)
        self._reflection_frame = 0

        for depth, font_size, spacing in self.LAYER_CONFIG:
            font = choose_matrix_font(font_size, bold=True)
            offset = spacing // 2 if depth == 1 else random.randint(0, max(0, spacing - 1))
            for x in range(-spacing + offset, WIDTH + spacing, spacing):
                stream = RainStream(
                    x=float(x),
                    y=random.uniform(-HEIGHT, HEIGHT),
                    speed=50.0,
                    length=20,
                    glyphs=[],
                    brightness=1.0,
                    spacing=max(font_size + 1, font.get_linesize()),
                    font=font,
                    depth=depth,
                )
                stream.reset(HEIGHT)
                stream.y = random.uniform(-HEIGHT, HEIGHT)
                self.layers.append(stream)

        self.layers.sort(key=lambda item: item.depth)
        self._glyph_cache: dict[Tuple[int, str, int, bool], pygame.Surface] = {}
        self._vignette = self._build_vignette()

    @staticmethod
    def _build_vignette() -> pygame.Surface:
        surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Darken corners and edges, but never create a solid top bar.
        for index in range(34):
            alpha = max(0, 42 - index)
            pygame.draw.rect(
                surface,
                (0, 0, 0, alpha),
                pygame.Rect(index, index, WIDTH - index * 2, HEIGHT - index * 2),
                1,
            )
        return surface

    def _glyph_image(
        self, stream: RainStream, glyph: str, level: int, head: bool = False
    ) -> pygame.Surface:
        key = (stream.depth, glyph, level, head)
        image = self._glyph_cache.get(key)
        if image is None:
            if head:
                if stream.depth == 2:
                    color = HEAD_GREEN
                elif stream.depth == 1:
                    color = (55, 175, 85)
                else:
                    color = (0, 62, 23)
            else:
                color = self.PALETTES[stream.depth][max(0, min(7, level))]
            image = stream.font.render(glyph, True, color)
            self._glyph_cache[key] = image
        return image

    def update(self, dt: float, energy: float = 0.0) -> None:
        for stream in self.layers:
            pulse_chance = 0.0012 + energy * 0.004
            if random.random() < pulse_chance:
                stream.pulse = random.uniform(1.15, 1.65)
            stream.pulse += (1.0 - stream.pulse) * min(1.0, dt * 3.0)
            stream.y += stream.speed * stream.pulse * (1.0 + energy * 0.12) * dt
            stream.x += stream.drift * dt

            mutation_rate = (1.4, 2.8, 5.0)[stream.depth]
            if random.random() < dt * mutation_rate:
                stream.glyphs[random.randrange(len(stream.glyphs))] = random.choice(MATRIX_CHARS)

            if stream.y - stream.length * stream.spacing > HEIGHT:
                stream.reset(HEIGHT)

    def source_points(self, count: int) -> List[Point]:
        visible: List[Point] = []
        weighted: List[Point] = []
        for stream in self.layers:
            for index in range(min(stream.length, 14)):
                y = stream.y - index * stream.spacing
                if 0 <= y <= HEIGHT:
                    point = (stream.x, y)
                    visible.append(point)
                    if stream.depth >= 1:
                        weighted.extend((point, point))
        pool = weighted or visible
        if not pool:
            pool = [
                (random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
                for _ in range(max(1, count))
            ]
        return [random.choice(pool) for _ in range(count)]

    def _draw_streams(self, surface: pygame.Surface, energy: float) -> None:
        for stream in self.layers:
            for index, glyph in enumerate(stream.glyphs):
                y = int(stream.y - index * stream.spacing)
                if y < -stream.spacing or y > HEIGHT:
                    continue

                falloff = max(0.025, 1.0 - index / max(1, stream.length - 1))
                # Steeper falloff keeps most of the scene dark like the reference.
                shaped = falloff * falloff
                value = shaped * stream.brightness

                is_head = index == 0 and stream.head_hot
                if is_head:
                    if stream.depth == 2:
                        glow = self._glyph_image(stream, glyph, 2, head=False)
                        surface.blit(glow, (int(stream.x) - 1, y))
                        surface.blit(glow, (int(stream.x) + 1, y))
                    surface.blit(self._glyph_image(stream, glyph, 7, head=True), (int(stream.x), y))
                else:
                    level = int(clamp(round(value * 7), 0, 7))
                    if energy > 0 and stream.depth > 0 and random.random() < energy * 0.025:
                        level = min(7, level + 1)
                    surface.blit(
                        self._glyph_image(stream, glyph, level),
                        (int(stream.x), y),
                    )

    def _draw_reflection(self, destination: pygame.Surface) -> None:
        self._reflection_frame += 1
        if self._reflection_frame % 3 == 1:
            self.reflection_surface.fill((0, 0, 0, 0))

            source_rect = pygame.Rect(0, 0, WIDTH, FLOOR_Y)
            reflected = pygame.transform.flip(
                self.rain_surface.subsurface(source_rect), False, True
            )
            # Compress and blur the mirrored code into a wet pavement glow.
            small = pygame.transform.smoothscale(
                reflected,
                (max(1, WIDTH // 4), max(1, (HEIGHT - FLOOR_Y) // 3)),
            )
            blurred = pygame.transform.smoothscale(small, (WIDTH, HEIGHT - FLOOR_Y))
            blurred.set_alpha(52)
            self.reflection_surface.blit(blurred, (0, 0))

            # Horizontal glints imitate wet pavement without becoming a bright band.
            for stream in self.layers:
                if stream.depth != 2 or not stream.head_hot:
                    continue
                y = stream.y
                if FLOOR_Y - 40 <= y <= HEIGHT + 20 and random.random() < 0.35:
                    reflected_y = int(
                        FLOOR_Y + abs(FLOOR_Y - min(y, HEIGHT)) * 0.30
                    )
                    width = random.randint(2, 8)
                    alpha = random.randint(35, 85)
                    pygame.draw.line(
                        self.reflection_surface,
                        (0, random.randint(80, 155), random.randint(25, 55), alpha),
                        (int(stream.x) - width, reflected_y - FLOOR_Y),
                        (int(stream.x) + width, reflected_y - FLOOR_Y),
                        1,
                    )

            # Fade reflection toward the bottom.
            fade_overlay = pygame.Surface(
                (WIDTH, HEIGHT - FLOOR_Y), pygame.SRCALPHA
            )
            reflection_h = HEIGHT - FLOOR_Y
            for row in range(reflection_h):
                alpha = int(80 + (row / max(1, reflection_h - 1)) * 140)
                pygame.draw.line(
                    fade_overlay, (0, 0, 0, alpha), (0, row), (WIDTH, row)
                )
            self.reflection_surface.blit(fade_overlay, (0, 0))

        destination.blit(self.reflection_surface, (0, FLOOR_Y))

    def draw(self, surface: pygame.Surface, energy: float = 0.0) -> None:
        self.rain_surface.fill((0, 0, 0, 0))
        self._draw_streams(self.rain_surface, energy)
        surface.blit(self.rain_surface, (0, 0))
        self._draw_reflection(surface)
        surface.blit(self._vignette, (0, 0))


@dataclass
class GlyphParticle:
    start_x: float
    start_y: float
    target_x: float
    target_y: float
    x: float
    y: float
    glyph: str
    delay: float
    phase: float
    speed: float
    color: Color
    vx: float = 0.0
    vy: float = 0.0


class RainTextTransition:
    """Rain glyphs gather into a reading, then melt downward into Matrix code."""

    def __init__(
        self,
        rain: CinematicRain,
        title: str,
        value: str,
        accent: Color,
        title_font: pygame.font.Font,
        value_font: pygame.font.Font,
        tiny_font: pygame.font.Font,
    ) -> None:
        self.title = title
        self.value = value
        self.accent = accent
        self.title_font = title_font
        self.value_font = value_font
        self.tiny_font = tiny_font
        self.mode = "form"
        self.elapsed = 0.0
        self.crisp_alpha = 0
        self._glyph_cache: dict[Tuple[str, Color], pygame.Surface] = {}

        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        title_image = title_font.render(title, True, (255, 255, 255))
        value_image = value_font.render(value, True, (255, 255, 255))
        title_rect = title_image.get_rect(center=(WIDTH // 2, 145))
        value_rect = value_image.get_rect(center=(WIDTH // 2, 228))
        mask.blit(title_image, title_rect)
        mask.blit(value_image, value_rect)

        candidates: List[Tuple[int, int]] = []
        for y in range(90, HEIGHT - 5, 5):
            for x in range(3, WIDTH - 3, 5):
                if mask.get_at((x, y)).a > 60:
                    candidates.append((x, y))

        random.shuffle(candidates)
        candidates = candidates[:650]
        starts = rain.source_points(len(candidates))
        self.particles: List[GlyphParticle] = []
        for (target_x, target_y), (start_x, start_y) in zip(candidates, starts):
            self.particles.append(
                GlyphParticle(
                    start_x=start_x,
                    start_y=start_y,
                    target_x=float(target_x),
                    target_y=float(target_y),
                    x=start_x,
                    y=start_y,
                    glyph=random.choice(MATRIX_CHARS),
                    delay=random.uniform(0.0, 0.46),
                    phase=random.uniform(0.0, math.tau),
                    speed=random.uniform(0.85, 1.15),
                    color=mix(BRIGHT_GREEN, accent, random.choice((0.40, 0.56, 0.72, 0.88))),
                )
            )

    def _glyph_image(self, glyph: str, color: Color) -> pygame.Surface:
        key = (glyph, color)
        image = self._glyph_cache.get(key)
        if image is None:
            image = self.tiny_font.render(glyph, True, color)
            self._glyph_cache[key] = image
        return image

    def start_melt(self) -> None:
        self.mode = "melt"
        self.elapsed = 0.0
        self.crisp_alpha = 0
        for particle in self.particles:
            particle.glyph = random.choice(MATRIX_CHARS)
            particle.vx = random.uniform(-20.0, 20.0)
            particle.vy = random.uniform(52.0, 132.0)
            particle.delay = random.uniform(0.0, 0.42)

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.mode == "form":
            for particle in self.particles:
                local = clamp(
                    (self.elapsed - particle.delay)
                    / max(0.2, FORM_SECONDS - particle.delay),
                    0.0,
                    1.0,
                )
                eased = ease_in_out(local)
                arc = math.sin(local * math.pi) * (8.0 + 10.0 * particle.speed)
                particle.x = particle.start_x + (particle.target_x - particle.start_x) * eased
                particle.y = particle.start_y + (particle.target_y - particle.start_y) * eased
                particle.x += math.cos(particle.phase + local * math.tau) * arc * (1.0 - local)
                if random.random() < dt * 7.0 * (1.0 - local):
                    particle.glyph = random.choice(MATRIX_CHARS)
            self.crisp_alpha = int(
                255
                * clamp(
                    (self.elapsed - FORM_SECONDS * 0.72) / (FORM_SECONDS * 0.28),
                    0.0,
                    1.0,
                )
            )
        else:
            for particle in self.particles:
                if self.elapsed < particle.delay:
                    continue
                particle.vy += 205.0 * dt
                particle.x += particle.vx * dt
                particle.y += particle.vy * dt
                if random.random() < dt * 11.0:
                    particle.glyph = random.choice(MATRIX_CHARS)

    def form_done(self) -> bool:
        return self.mode == "form" and self.elapsed >= FORM_SECONDS

    def melt_done(self) -> bool:
        return self.mode == "melt" and self.elapsed >= MELT_SECONDS

    def draw(self, surface: pygame.Surface) -> None:
        for particle in self.particles:
            if self.mode == "form":
                if self.elapsed < particle.delay:
                    continue
                local = clamp(
                    (self.elapsed - particle.delay)
                    / max(0.2, FORM_SECONDS - particle.delay),
                    0.0,
                    1.0,
                )
                level = round(local * 5) / 5.0
                color = mix((0, 90, 28), particle.color, level)
            else:
                if self.elapsed < particle.delay or particle.y > HEIGHT + 20:
                    continue
                fade = 1.0 - clamp(self.elapsed / MELT_SECONDS, 0.0, 1.0)
                level = round(fade * 5) / 5.0
                color = mix(DIM_GREEN, particle.color, level)
            surface.blit(
                self._glyph_image(particle.glyph, color),
                (int(particle.x), int(particle.y)),
            )

        if self.mode == "form" and self.crisp_alpha > 0:
            title_image = self.title_font.render(self.title, True, self.accent)
            value_image = self.value_font.render(self.value, True, self.accent)
            title_image.set_alpha(self.crisp_alpha)
            value_image.set_alpha(self.crisp_alpha)

            title_shadow = self.title_font.render(self.title, True, BLACK)
            value_shadow = self.value_font.render(self.value, True, BLACK)
            title_shadow.set_alpha(self.crisp_alpha)
            value_shadow.set_alpha(self.crisp_alpha)

            title_rect = title_image.get_rect(center=(WIDTH // 2, 145))
            value_rect = value_image.get_rect(center=(WIDTH // 2, 228))
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                surface.blit(title_shadow, title_rect.move(dx, dy))
                surface.blit(value_shadow, value_rect.move(dx, dy))
            surface.blit(title_image, title_rect)
            surface.blit(value_image, value_rect)


class MatrixOS:
    PAGES: Sequence[Tuple[str, str]] = (
        ("outside", "OUTSIDE"),
        ("inside", "INSIDE"),
    )

    def __init__(self) -> None:
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Matrix OS - Dark Cinematic City Rain")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.clock_font = choose_font(56, bold=True)
        self.title_font = choose_font(29, bold=True)
        self.value_font = choose_font(78, bold=True)
        self.tiny_font = choose_matrix_font(9, bold=True)

        self.rain = CinematicRain()
        self.data = LiveData()
        self.data.refresh(force=True)

        self.page_index = 0
        self.phase = "idle"
        self.phase_started = time.monotonic()
        self.transition: Optional[RainTextTransition] = None

    def page_data(self) -> Tuple[str, str, Color]:
        key, title = self.PAGES[self.page_index]
        value = self.data.outside_f if key == "outside" else self.data.inside_f
        return title, format_temp(value), temp_color(value)

    def begin_form(self) -> None:
        title, value, accent = self.page_data()
        self.transition = RainTextTransition(
            self.rain,
            title,
            value,
            accent,
            self.title_font,
            self.value_font,
            self.tiny_font,
        )
        self.phase = "form"
        self.phase_started = time.monotonic()

    def begin_melt(self) -> None:
        if self.transition is None:
            return
        self.transition.start_melt()
        self.phase = "melt"
        self.phase_started = time.monotonic()

    def update(self, dt: float) -> None:
        self.data.refresh()
        energy = 0.26 if self.phase in ("form", "melt") else 0.0
        self.rain.update(dt, energy)

        elapsed = time.monotonic() - self.phase_started
        if self.phase == "idle":
            if elapsed >= IDLE_SECONDS:
                self.begin_form()
        elif self.phase == "form" and self.transition is not None:
            self.transition.update(dt)
            if self.transition.form_done():
                self.phase = "hold"
                self.phase_started = time.monotonic()
        elif self.phase == "hold":
            if elapsed >= HOLD_SECONDS:
                self.begin_melt()
        elif self.phase == "melt" and self.transition is not None:
            self.transition.update(dt)
            if self.transition.melt_done():
                self.page_index = (self.page_index + 1) % len(self.PAGES)
                self.transition = None
                self.phase = "idle"
                self.phase_started = time.monotonic()

    def draw_clock(self) -> None:
        text = datetime.now().strftime("%I:%M %p").lstrip("0")
        image = self.clock_font.render(text, True, HEAD_GREEN)
        rect = image.get_rect(center=(WIDTH // 2, 38))

        shadow = self.clock_font.render(text, True, BLACK)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)):
            self.screen.blit(shadow, rect.move(dx, dy))

        glow = self.clock_font.render(text, True, (0, 72, 23))
        self.screen.blit(glow, rect.move(-1, 0))
        self.screen.blit(glow, rect.move(1, 0))
        self.screen.blit(image, rect)

    def draw(self) -> None:
        self.screen.fill(BLACK)
        energy = 0.22 if self.phase in ("form", "melt") else 0.0
        self.rain.draw(self.screen, energy)
        if self.transition is not None and self.phase in ("form", "hold", "melt"):
            self.transition.draw(self.screen)
        self.draw_clock()
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
                        if self.phase == "hold":
                            self.begin_melt()
                        elif self.phase == "idle":
                            self.begin_form()

            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now
            self.update(dt)
            self.draw()
            self.clock.tick(FPS)


def main() -> int:
    try:
        MatrixOS().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix OS failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
