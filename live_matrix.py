#!/usr/bin/env python3
"""Matrix Live V10.1 — visible world/field renderer for Pi 4 480x320.

Four scenes cycle every 4 seconds (16 seconds total):
FIELD -> CITY -> PORTAL -> OPERATOR

Design goals:
- Always-visible Matrix code field (never a mostly black screen)
- Big readable glyphs at 480x320
- Strong RGB565-friendly greens and hard black
- No radial/tunnel streaking
- Scene structures are large enough to read on the physical 3.5" LCD
"""
import math
import os
import random
import time

os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame
from pygame.locals import DOUBLEBUF, FULLSCREEN, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_q
from OpenGL.GL import (
    GL_ALPHA_TEST, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST,
    GL_GREATER, GL_LINES, GL_LINE_LOOP, GL_MODELVIEW, GL_NEAREST, GL_ONE_MINUS_SRC_ALPHA,
    GL_PROJECTION, GL_QUADS, GL_RGBA, GL_SRC_ALPHA, GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER, GL_UNSIGNED_BYTE,
    glAlphaFunc, glBegin, glBindTexture, glBlendFunc, glClear, glClearColor,
    glColor4f, glDeleteTextures, glDisable, glEnable, glEnd, glGenTextures,
    glLineWidth, glLoadIdentity, glMatrixMode, glPopMatrix, glPushMatrix, glRotatef,
    glTexCoord2f, glTexImage2D, glTexParameteri, glTranslatef, glVertex3f, glViewport,
)
from OpenGL.GLU import gluPerspective

W, H = 480, 320
GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<>+-*/{}[]:;=#$%@!?|"
ATLAS_COLS = 8
ATLAS_ROWS = math.ceil(len(GLYPHS) / ATLAS_COLS)

# Hard, widely separated shades that survive the physical RGB565 LCD.
G0 = (0.00, 0.34, 0.00)
G1 = (0.00, 0.58, 0.02)
G2 = (0.02, 0.82, 0.05)
G3 = (0.10, 1.00, 0.18)
HEAD = (0.78, 1.00, 0.80)
PORTAL = (0.15, 1.00, 0.55)
DARK = (0.00, 0.16, 0.00)
RED = (1.00, 0.04, 0.02)

SCENES = ("FIELD", "CITY", "PORTAL", "OPERATOR")
SCENE_SECONDS = 4.0


def pick_font(size=32):
    for name in ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "monospace"):
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def make_atlas():
    font = pick_font(32)
    cw, ch = 34, 42
    surf = pygame.Surface((ATLAS_COLS * cw, ATLAS_ROWS * ch), pygame.SRCALPHA, 32)
    surf.fill((0, 0, 0, 0))
    for i, glyph in enumerate(GLYPHS):
        img = font.render(glyph, True, (255, 255, 255, 255))
        r = img.get_rect(center=((i % ATLAS_COLS) * cw + cw // 2,
                                 (i // ATLAS_COLS) * ch + ch // 2))
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
    i = GLYPHS.find(ch)
    if i < 0:
        i = 0
    cx, cy = i % ATLAS_COLS, i // ATLAS_COLS
    return (
        cx / ATLAS_COLS,
        1.0 - ((cy + 1) / ATLAS_ROWS),
        (cx + 1) / ATLAS_COLS,
        1.0 - (cy / ATLAS_ROWS),
    )


def hash_char(seed, idx, tick):
    n = (seed * 1103515245 + idx * 12345 + tick * 2654435761) & 0xFFFFFFFF
    return GLYPHS[n % len(GLYPHS)]


def billboard(ch, x, y, z, size, color=G3, alpha=1.0, rot_y=0.0, rot_x=0.0):
    u0, v0, u1, v1 = glyph_uv(ch)
    hw = size * 0.52
    hh = size
    glPushMatrix()
    glTranslatef(x, y, z)
    if rot_y:
        glRotatef(rot_y, 0, 1, 0)
    if rot_x:
        glRotatef(rot_x, 1, 0, 0)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(u0, v0); glVertex3f(-hw, -hh, 0)
    glTexCoord2f(u1, v0); glVertex3f( hw, -hh, 0)
    glTexCoord2f(u1, v1); glVertex3f( hw,  hh, 0)
    glTexCoord2f(u0, v1); glVertex3f(-hw,  hh, 0)
    glEnd()
    glPopMatrix()


def solid_quad(x0, y0, x1, y1, z, color, alpha=1.0):
    glDisable(GL_TEXTURE_2D)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z); glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z); glVertex3f(x0, y1, z)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def line_box(x0, y0, x1, y1, z, color=G2, width=2.0):
    glDisable(GL_TEXTURE_2D)
    glLineWidth(width)
    glColor4f(color[0], color[1], color[2], 1.0)
    glBegin(GL_LINE_LOOP)
    glVertex3f(x0, y0, z); glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z); glVertex3f(x0, y1, z)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def draw_background_rain(t, density=32, bright=True):
    """Persistent front-facing rain so every scene has visible Matrix texture."""
    tick = int(t * 7)
    cols = density
    for c in range(cols):
        x = -6.4 + c * (12.8 / max(1, cols - 1))
        z = -8.0 - ((c * 3.7) % 25.0)
        speed = 0.70 + ((c * 11) % 9) * 0.06
        phase = (c * 1.37) % 7.4
        head_y = 4.0 - ((t * speed + phase) % 7.8)
        length = 7 + (c % 5)
        for i in range(length):
            y = head_y + i * 0.58
            if y > 4.0:
                y -= 8.2
            color = HEAD if i == 0 else (G3 if i < 3 else G2 if i < 6 else G1)
            if not bright and i > 3:
                color = G0
            billboard(hash_char(1000 + c, i, tick + i // 2), x, y, z, 0.19, color)


def draw_floor_field(t):
    """Perspective floor made from moving glyph rows, not radial streaks."""
    tick = int(t * 5)
    for row in range(12):
        z = -4.8 - row * 2.1
        y = -3.18
        for c in range(13):
            x = -5.8 + c * 0.96
            if (c + row) % 4 == 0:
                continue
            ch = hash_char(3000 + row * 20 + c, c, tick + row)
            color = G3 if row < 3 else G2 if row < 7 else G1
            billboard(ch, x, y, z, 0.16 if row < 5 else 0.14, color, rot_x=-90)


def draw_field_scene(t):
    draw_background_rain(t, 38, True)
    draw_floor_field(t)
    # Big drifting curtains left/right to make it feel like a FIELD instead of wallpaper.
    tick = int(t * 6)
    for side in (-1, 1):
        x = side * 4.8
        for col in range(4):
            z = -7.0 - col * 5.2
            for i in range(9):
                y = 3.4 - ((i * 0.76 + t * (0.45 + col * 0.05)) % 7.0)
                ch = hash_char(4100 + side * 10 + col, i, tick)
                billboard(ch, x, y, z, 0.22, HEAD if i == 0 else G3, rot_y=(-90 if side > 0 else 90))


def draw_building(x, z, w, h, seed, t):
    """Large wireframe building facade with code windows."""
    y0 = -3.0
    y1 = y0 + h
    line_box(x - w/2, y0, x + w/2, y1, z, G2, 2.2)
    tick = int(t * 4)
    cols = max(2, int(w / 0.65))
    rows = max(3, int(h / 0.75))
    for r in range(rows):
        for c in range(cols):
            if (r + c + seed) % 3 == 0:
                continue
            gx = x - w/2 + 0.35 + c * (w / cols)
            gy = y0 + 0.38 + r * (h / rows)
            col = G3 if (r + c + tick) % 7 == 0 else G1
            billboard(hash_char(seed, r * 13 + c, tick), gx, gy, z + 0.02, 0.11, col)


def draw_city_scene(t):
    draw_background_rain(t, 26, False)
    draw_floor_field(t)
    buildings = [
        (-5.1,-8.0,2.0,5.3,10), (-3.4,-10.0,1.8,3.8,20),
        (-1.9,-13.0,1.6,3.0,30), (1.8,-13.0,1.7,3.1,40),
        (3.5,-10.5,1.9,4.3,50), (5.2,-8.3,2.2,5.5,60),
        (-4.8,-18.0,2.8,6.0,70), (4.8,-18.0,2.8,6.2,80),
    ]
    for b in buildings:
        draw_building(*b, t=t)
    # Lone figure in the street, made much larger than before.
    solid_quad(-0.20, -3.0, 0.20, -1.45, -7.0, (0.00, 0.05, 0.00))
    solid_quad(-0.34, -1.45, 0.34, -0.90, -7.0, (0.00, 0.05, 0.00))


def draw_person(x, z, scale=1.0):
    solid_quad(x - 0.12*scale, -3.0, x + 0.12*scale, -1.75, z, (0.0, 0.04, 0.0))
    solid_quad(x - 0.20*scale, -1.75, x + 0.20*scale, -1.35, z, (0.0, 0.04, 0.0))


def draw_portal_scene(t):
    draw_background_rain(t, 36, True)
    # Wide bright doorway, closer and bigger.
    z = -8.0
    glow = 0.78 + 0.22 * math.sin(t * 5.0)
    c = (0.10, glow, 0.38)
    # halo
    solid_quad(-2.25, -3.05, 2.25, 2.75, z + 0.18, (0.00, 0.28, 0.08), 0.85)
    # doorway body
    solid_quad(-2.0, -3.0, -1.58, 2.45, z, c)
    solid_quad( 1.58, -3.0,  2.0, 2.45, z, c)
    solid_quad(-2.0, 2.05, 2.0, 2.45, z, c)
    # interior code rain
    tick = int(t * 8)
    for col in range(9):
        x = -1.45 + col * 0.36
        for i in range(8):
            y = 1.8 - ((i * 0.62 + t * (0.65 + col*0.03)) % 4.8)
            billboard(hash_char(5000 + col, i, tick), x, y, z + 0.05, 0.16,
                      HEAD if i == 0 else G3)
    draw_person(-0.42, z + 0.30, 1.25)
    draw_person(0.46, z + 0.30, 1.25)


def draw_monitor(cx, cy, z, w, h, seed, t, rot=0):
    glPushMatrix()
    glTranslatef(cx, cy, z)
    if rot:
        glRotatef(rot, 0, 1, 0)
    line_box(-w/2, -h/2, w/2, h/2, 0, G3, 2.2)
    tick = int(t * 8)
    cols = max(3, int(w / 0.42))
    rows = max(3, int(h / 0.52))
    for c in range(cols):
        for r in range(rows):
            if (c + r + seed) % 4 == 0:
                continue
            x = -w/2 + 0.22 + c * (w / cols)
            y = h/2 - 0.25 - r * (h / rows)
            billboard(hash_char(seed + c, r, tick), x, y, 0.01, 0.10,
                      HEAD if r == 0 and c % 2 == 0 else G2)
    glPopMatrix()


def draw_operator_scene(t):
    # Dense backdrop so operator room is immediately obvious.
    draw_background_rain(t, 30, True)
    monitors = [
        (-3.8, 1.55, -7.5, 2.4, 1.55, 610, 18),
        (-1.25, 1.80, -6.7, 2.4, 1.55, 620, 7),
        ( 1.25, 1.80, -6.7, 2.4, 1.55, 630, -7),
        ( 3.8, 1.55, -7.5, 2.4, 1.55, 640, -18),
        (-3.0,-0.55, -6.5, 2.2, 1.45, 650, 13),
        ( 0.0,-0.45, -6.2, 2.4, 1.55, 660, 0),
        ( 3.0,-0.55, -6.5, 2.2, 1.45, 670, -13),
    ]
    for m in monitors:
        draw_monitor(*m, t=t)
    # operator silhouette in foreground
    solid_quad(-0.42, -3.15, 0.42, -1.20, -4.5, (0.0, 0.03, 0.0))
    solid_quad(-0.58, -1.20, 0.58, -0.45, -4.5, (0.0, 0.03, 0.0))


def draw_scene_label(scene):
    # tiny debug label can be useful on the physical panel; intentionally subtle
    # Rendered as glyphs along upper-left in world space.
    for i, ch in enumerate(scene):
        if ch in GLYPHS:
            billboard(ch, -5.6 + i * 0.33, 3.35, -5.2, 0.14, G1)


def flash_overlay(red=False):
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    c = (1.0, 0.12, 0.08) if red else (0.72, 1.0, 0.76)
    glColor4f(c[0], c[1], c[2], 0.70)
    glBegin(GL_QUADS)
    glVertex3f(-1,-1,0); glVertex3f(1,-1,0); glVertex3f(1,1,0); glVertex3f(-1,1,0)
    glEnd()
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)


def main():
    pygame.init()
    pygame.font.init()
    pygame.display.set_caption("Matrix World Live")
    pygame.display.set_mode((W, H), FULLSCREEN | OPENGL | DOUBLEBUF)
    pygame.mouse.set_visible(False)

    glViewport(0, 0, W, H)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_ALPHA_TEST)
    glAlphaFunc(GL_GREATER, 0.12)

    tex = make_atlas()
    clock = pygame.time.Clock()
    start = time.monotonic()
    last_scene = -1
    flash_until = -1.0
    red_flash = False
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

            scene_idx = int(t / SCENE_SECONDS) % len(SCENES)
            scene = SCENES[scene_idx]
            if scene_idx != last_scene:
                # short scene-transition flash so changes are obvious.
                flash_until = t + 0.055
                red_flash = False
                last_scene = scene_idx

            # one short corruption hit per full cycle
            cycle_t = t % (SCENE_SECONDS * len(SCENES))
            if 14.8 < cycle_t < 14.86:
                flash_until = t + 0.06
                red_flash = True

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(66.0, W / float(H), 0.1, 80.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            # Camera moves sideways and slightly vertically; it never rushes toward a center point.
            camx = math.sin(t * 0.31) * 0.36
            camy = math.sin(t * 0.23 + 1.1) * 0.14
            glRotatef(math.sin(t * 0.16) * 1.6, 0, 0, 1)
            glRotatef(math.sin(t * 0.12) * 2.0, 0, 1, 0)
            glTranslatef(-camx, -camy, 0.0)

            glBindTexture(GL_TEXTURE_2D, tex)

            if scene == "FIELD":
                draw_field_scene(t)
            elif scene == "CITY":
                draw_city_scene(t)
            elif scene == "PORTAL":
                draw_portal_scene(t)
            else:
                draw_operator_scene(t)

            draw_scene_label(scene)

            if t < flash_until:
                flash_overlay(red_flash)

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
