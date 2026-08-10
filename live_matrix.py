#!/usr/bin/env python3
"""Matrix Live — Pi 4 / Osoyoo 3.5in RGB565 tuned renderer.

Designed for the physical 480x320 SPI LCD rather than a VNC screenshot:
- discrete RGB565-friendly green levels
- crisp nearest-neighbour glyph atlas
- hard black background, bright white/green stream heads
- slow 3D code curtains on walls/floor/ceiling plus floating sheets
- no radial/starburst stretching
- short red-corruption events and white flashes
"""
import math
import os
import random
import time
from dataclasses import dataclass

os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame
from pygame.locals import DOUBLEBUF, FULLSCREEN, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_q
from OpenGL.GL import (
    GL_ALPHA_TEST, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_GREATER, GL_MODELVIEW, GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS, GL_RGBA,
    GL_SRC_ALPHA, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_UNSIGNED_BYTE, glAlphaFunc, glBegin, glBindTexture, glBlendFunc,
    glClear, glClearColor, glColor4f, glDeleteTextures, glDisable, glEnable,
    glEnd, glGenTextures, glLoadIdentity, glMatrixMode, glPopMatrix,
    glPushMatrix, glRotatef, glTexCoord2f, glTexImage2D, glTexParameteri,
    glTranslatef, glVertex3f, glViewport,
)
from OpenGL.GLU import gluPerspective

GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<>+-*/{}[]:;=#$%@!?|"
ATLAS_COLS = 8
ATLAS_ROWS = math.ceil(len(GLYPHS) / ATLAS_COLS)

# RGB565-friendly palette. Deliberately avoids subtle gradients that look good in VNC
# but collapse on the Osoyoo TFT. Green has 6 hardware bits, so these are spaced hard.
GREEN_LEVELS = [
    (0.00, 0.16, 0.00),
    (0.00, 0.32, 0.01),
    (0.00, 0.55, 0.03),
    (0.02, 0.78, 0.06),
    (0.08, 1.00, 0.16),
]
GREEN_HEAD = (0.76, 1.00, 0.76)
RED_LEVELS = [
    (0.18, 0.00, 0.00),
    (0.35, 0.00, 0.00),
    (0.58, 0.01, 0.01),
    (0.82, 0.02, 0.02),
    (1.00, 0.06, 0.04),
]
RED_HEAD = (1.00, 0.72, 0.65)

@dataclass
class Stream:
    surface: str
    a: float
    b: float
    phase: float
    speed: float
    length: int
    seed: int
    size: float
    brightness_bias: int


def pick_font(size=30):
    for name in ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "monospace"):
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def make_atlas():
    font = pick_font(30)
    cell_w, cell_h = 32, 40
    surf = pygame.Surface((ATLAS_COLS * cell_w, ATLAS_ROWS * cell_h), pygame.SRCALPHA, 32)
    surf.fill((0, 0, 0, 0))
    for i, ch in enumerate(GLYPHS):
        img = font.render(ch, True, (255, 255, 255, 255))
        r = img.get_rect(center=((i % ATLAS_COLS) * cell_w + cell_w // 2,
                                 (i // ATLAS_COLS) * cell_h + cell_h // 2))
        surf.blit(img, r)
    data = pygame.image.tostring(surf, "RGBA", True)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surf.get_width(), surf.get_height(),
                 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    return tex


def glyph_uv(ch):
    idx = GLYPHS.find(ch)
    if idx < 0:
        idx = 0
    cx, cy = idx % ATLAS_COLS, idx // ATLAS_COLS
    u0, u1 = cx / ATLAS_COLS, (cx + 1) / ATLAS_COLS
    v0 = 1.0 - ((cy + 1) / ATLAS_ROWS)
    v1 = 1.0 - (cy / ATLAS_ROWS)
    return u0, v0, u1, v1


def draw_billboard(ch, x, y, z, size, color, alpha=1.0, rot_y=0.0, rot_x=0.0):
    u0, v0, u1, v1 = glyph_uv(ch)
    w = size * 0.55
    h = size
    glPushMatrix()
    glTranslatef(x, y, z)
    if rot_y:
        glRotatef(rot_y, 0, 1, 0)
    if rot_x:
        glRotatef(rot_x, 1, 0, 0)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(u0, v0); glVertex3f(-w, -h, 0)
    glTexCoord2f(u1, v0); glVertex3f( w, -h, 0)
    glTexCoord2f(u1, v1); glVertex3f( w,  h, 0)
    glTexCoord2f(u0, v1); glVertex3f(-w,  h, 0)
    glEnd()
    glPopMatrix()


def rand_char(seed, idx, tick):
    n = (seed * 1103515245 + idx * 12345 + tick * 2654435761) & 0xFFFFFFFF
    return GLYPHS[n % len(GLYPHS)]


def make_streams():
    streams = []
    seed = 100
    # Front-facing floating curtains at different depths. Nothing gets radially stretched.
    for z in (-7.5, -11.5, -16.0, -22.0, -29.0):
        count = 8 if z > -15 else 10
        for i in range(count):
            x = -5.0 + (10.0 * i / max(1, count - 1)) + random.uniform(-0.28, 0.28)
            if random.random() < 0.22:
                continue
            streams.append(Stream("front", x, z + random.uniform(-1.0, 1.0),
                                  random.uniform(0, 20), random.uniform(0.70, 1.25),
                                  random.randint(7, 15), seed, random.uniform(0.18, 0.28),
                                  random.randint(-1, 1)))
            seed += 1

    # Side walls provide room depth while keeping glyphs readable.
    for side in ("left", "right"):
        for z in [-(5.0 + i * 2.3) for i in range(11)]:
            if random.random() < 0.18:
                continue
            streams.append(Stream(side, z + random.uniform(-0.4, 0.4), 0,
                                  random.uniform(0, 20), random.uniform(0.6, 1.1),
                                  random.randint(6, 13), seed, random.uniform(0.16, 0.24),
                                  random.randint(-1, 1)))
            seed += 1

    # Floor/ceiling ribbons sell the immersive room without turning into a starburst.
    for surface in ("floor", "ceiling"):
        for x in (-3.8, -2.6, -1.3, 0.0, 1.3, 2.6, 3.8):
            if random.random() < 0.25:
                continue
            streams.append(Stream(surface, x + random.uniform(-0.2, 0.2), random.uniform(-1, 1),
                                  random.uniform(0, 20), random.uniform(0.45, 0.9),
                                  random.randint(8, 15), seed, random.uniform(0.15, 0.22),
                                  random.randint(-1, 1)))
            seed += 1
    return streams


def shade_for(idx_from_head, stream, red=False):
    levels = RED_LEVELS if red else GREEN_LEVELS
    if idx_from_head == 0:
        return RED_HEAD if red else GREEN_HEAD
    # Ordered dither between adjacent RGB565-safe levels instead of soft alpha gradients.
    base = max(0, 4 - min(4, idx_from_head // 2) + stream.brightness_bias)
    base = max(0, min(4, base))
    if ((stream.seed + idx_from_head) & 1) and base > 0:
        base -= 1
    return levels[base]


def render_stream(s, t, red=False, glitch=0.0):
    tick = int(t * 7.0)
    fall = (t * s.speed + s.phase) % 8.0
    top = 3.8 - fall
    jx = math.sin((s.seed * 1.7) + t * 90.0) * glitch * 0.20

    for i in range(s.length):
        y = top + i * 0.54
        while y < -4.2:
            y += 8.4
        while y > 4.2:
            y -= 8.4
        color = shade_for(i, s, red)
        ch = rand_char(s.seed, i, tick + (i // 3))
        if s.surface == "front":
            draw_billboard(ch, s.a + jx, y, s.b, s.size, color)
        elif s.surface == "left":
            draw_billboard(ch, -4.7, y, s.a, s.size, color, rot_y=90)
        elif s.surface == "right":
            draw_billboard(ch, 4.7, y, s.a, s.size, color, rot_y=-90)
        elif s.surface == "floor":
            z = -5.0 - ((i * 1.25 + fall * 0.55 + s.phase) % 27.0)
            draw_billboard(ch, s.a + jx, -3.25, z, s.size, color, rot_x=-90)
        elif s.surface == "ceiling":
            z = -5.0 - ((i * 1.25 + fall * 0.55 + s.phase) % 27.0)
            draw_billboard(ch, s.a + jx, 3.25, z, s.size, color, rot_x=90)


def draw_foreground_sweep(t, red=False):
    cycle = t % 17.0
    if not (10.5 < cycle < 14.5):
        return
    p = (cycle - 10.5) / 4.0
    x = -5.8 + 11.6 * p
    palette = RED_LEVELS if red else GREEN_LEVELS
    head = RED_HEAD if red else GREEN_HEAD
    for i in range(8):
        y = 3.4 - i * 0.78
        ch = GLYPHS[(i * 7 + int(t * 5)) % len(GLYPHS)]
        color = head if i == 0 else palette[max(1, 4 - i // 2)]
        draw_billboard(ch, x, y, -3.8, 0.34, color)


def main():
    pygame.init()
    pygame.font.init()

    info = pygame.display.Info()
    w = info.current_w if info.current_w > 0 else 480
    h = info.current_h if info.current_h > 0 else 320
    # If VNC exposes a larger virtual desktop, ignore it. This renderer is for the LCD.
    if w > 800 or h > 600:
        w, h = 480, 320

    pygame.display.set_caption("Matrix Live RGB565")
    pygame.display.set_mode((w, h), FULLSCREEN | OPENGL | DOUBLEBUF)
    pygame.mouse.set_visible(False)

    glViewport(0, 0, w, h)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_ALPHA_TEST)
    glAlphaFunc(GL_GREATER, 0.18)

    tex = make_atlas()
    streams = make_streams()
    clock = pygame.time.Clock()
    start = time.monotonic()
    next_corrupt = random.uniform(14.0, 22.0)
    corrupt_until = -1.0
    flash_until = -1.0

    running = True
    try:
        while running:
            now = time.monotonic()
            t = now - start
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN and event.key in (K_ESCAPE, K_q):
                    running = False

            if t >= next_corrupt:
                corrupt_until = t + random.uniform(1.1, 1.8)
                flash_until = t + 0.08
                next_corrupt = t + random.uniform(17.0, 28.0)

            red = t < corrupt_until
            if red and corrupt_until - t < 0.12:
                flash_until = max(flash_until, t + 0.05)
            glitch = 1.0 if red and int(t * 16) % 5 == 0 else 0.0

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(67.0, w / max(1.0, float(h)), 0.1, 80.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            # Slow camera drift instead of flying directly into a center point.
            cam_x = math.sin(t * 0.23) * 0.52
            cam_y = math.sin(t * 0.17 + 1.2) * 0.22
            glRotatef(math.sin(t * 0.19) * 2.0, 0, 0, 1)
            glRotatef(math.sin(t * 0.13) * 2.8, 0, 1, 0)
            glTranslatef(-cam_x, -cam_y, 0.0)

            glBindTexture(GL_TEXTURE_2D, tex)
            for s in streams:
                render_stream(s, t, red=red, glitch=glitch)
            draw_foreground_sweep(t, red=red)

            if t < flash_until:
                glDisable(GL_DEPTH_TEST)
                glDisable(GL_TEXTURE_2D)
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                c = (1.0, 0.86, 0.80) if red else (0.82, 1.0, 0.82)
                glColor4f(c[0], c[1], c[2], 0.88)
                glBegin(GL_QUADS)
                glVertex3f(-1, -1, 0); glVertex3f(1, -1, 0)
                glVertex3f(1, 1, 0); glVertex3f(-1, 1, 0)
                glEnd()
                glEnable(GL_TEXTURE_2D)
                glEnable(GL_DEPTH_TEST)

            pygame.display.flip()
            clock.tick(60)
    finally:
        try:
            glDeleteTextures([tex])
        except Exception:
            pass
        pygame.quit()


if __name__ == "__main__":
    main()
