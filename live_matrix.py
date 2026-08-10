#!/usr/bin/env python3
"""Matrix Live — WORLD/FIELD renderer for Raspberry Pi.

V10 direction:
- open Matrix field instead of a tunnel
- wide glyph floor / rain field with distant depth
- rotating scene language: FIELD, CITY, PORTAL, OPERATOR
- code buildings, floating curtains, doorway light, silhouettes, monitor wall
- readable glyphs, dark negative space, slow cinematic camera
- short corruption/glitch hits
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
    GL_DEPTH_TEST, GL_GREATER, GL_LINES, GL_LINE_STRIP, GL_MODELVIEW, GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS, GL_RGBA,
    GL_SRC_ALPHA, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_UNSIGNED_BYTE, glAlphaFunc, glBegin, glBindTexture, glBlendFunc,
    glClear, glClearColor, glColor4f, glDeleteTextures, glDisable, glEnable,
    glEnd, glGenTextures, glLineWidth, glLoadIdentity, glMatrixMode,
    glPopMatrix, glPushMatrix, glRotatef, glTexCoord2f, glTexImage2D,
    glTexParameteri, glTranslatef, glVertex3f, glViewport,
)
from OpenGL.GLU import gluPerspective

GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<>+-*/{}[]:;=#$%@!?|"
ATLAS_COLS = 8
ATLAS_ROWS = math.ceil(len(GLYPHS) / ATLAS_COLS)

# Large, separated RGB565-safe steps.
GREEN = [
    (0.00, 0.12, 0.00),
    (0.00, 0.28, 0.00),
    (0.00, 0.48, 0.02),
    (0.00, 0.72, 0.04),
    (0.04, 1.00, 0.10),
]
HEAD = (0.72, 1.00, 0.74)
CYAN = (0.25, 1.00, 0.76)
RED = [
    (0.18, 0.00, 0.00),
    (0.36, 0.00, 0.00),
    (0.60, 0.01, 0.01),
    (0.84, 0.02, 0.02),
    (1.00, 0.06, 0.03),
]
RED_HEAD = (1.00, 0.78, 0.68)

SCENES = ("FIELD", "CITY", "PORTAL", "OPERATOR")
SCENE_SECONDS = 14.0

@dataclass
class RainColumn:
    x: float
    z: float
    phase: float
    speed: float
    length: int
    size: float
    seed: int
    lane: int = 0

@dataclass
class Building:
    x: float
    z: float
    w: float
    h: float
    seed: int

@dataclass
class Panel:
    x: float
    y: float
    z: float
    w: float
    h: float
    yaw: float
    seed: int


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


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


def draw_glyph(ch, x, y, z, size, color, alpha=1.0, yaw=0.0, pitch=0.0):
    u0, v0, u1, v1 = glyph_uv(ch)
    w = size * 0.52
    h = size
    glPushMatrix()
    glTranslatef(x, y, z)
    if yaw:
        glRotatef(yaw, 0, 1, 0)
    if pitch:
        glRotatef(pitch, 1, 0, 0)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(u0, v0); glVertex3f(-w, -h, 0)
    glTexCoord2f(u1, v0); glVertex3f( w, -h, 0)
    glTexCoord2f(u1, v1); glVertex3f( w,  h, 0)
    glTexCoord2f(u0, v1); glVertex3f(-w,  h, 0)
    glEnd()
    glPopMatrix()


def solid_quad(x0, y0, x1, y1, z, color, alpha=1.0):
    glDisable(GL_TEXTURE_2D)
    glColor4f(*color, alpha)
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z); glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z); glVertex3f(x0, y1, z)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def frame_rect(x0, y0, x1, y1, z, color, alpha=1.0, width=1.0):
    glDisable(GL_TEXTURE_2D)
    glLineWidth(width)
    glColor4f(*color, alpha)
    glBegin(GL_LINE_STRIP)
    glVertex3f(x0, y0, z); glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z); glVertex3f(x0, y1, z)
    glVertex3f(x0, y0, z)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def hash_char(seed, i, tick):
    n = (seed * 1103515245 + i * 12345 + tick * 2654435761) & 0xFFFFFFFF
    return GLYPHS[n % len(GLYPHS)]


def make_world():
    rng = random.Random(81179)
    rain = []
    seed = 1000

    # Wide open rain field: most columns are not centered.
    for z in (-7, -10, -13, -17, -22, -28, -35, -43):
        count = 10 if z > -20 else 14
        for i in range(count):
            x = -11.0 + (22.0 * i / max(1, count - 1)) + rng.uniform(-0.45, 0.45)
            if rng.random() < 0.20:
                continue
            rain.append(RainColumn(
                x=x, z=z + rng.uniform(-1.1, 1.1),
                phase=rng.uniform(0, 10), speed=rng.uniform(0.55, 1.25),
                length=rng.randint(6, 14), size=rng.uniform(0.17, 0.28),
                seed=seed, lane=0
            ))
            seed += 1

    # Side/far curtains make a "field" that surrounds rather than a tube.
    for side in (-1, 1):
        for j in range(18):
            rain.append(RainColumn(
                x=side * rng.uniform(6.0, 13.5),
                z=-6.0 - j * 2.1 + rng.uniform(-0.5, 0.5),
                phase=rng.uniform(0, 10), speed=rng.uniform(0.45, 1.0),
                length=rng.randint(6, 12), size=rng.uniform(0.16, 0.24),
                seed=seed, lane=side
            ))
            seed += 1

    buildings = []
    bseed = 3000
    for side in (-1, 1):
        z = -8.0
        while z > -44.0:
            w = rng.uniform(2.0, 4.2)
            h = rng.uniform(3.3, 8.0)
            x = side * rng.uniform(5.0, 9.0)
            buildings.append(Building(x, z, w, h, bseed))
            bseed += 1
            z -= rng.uniform(4.0, 7.0)

    panels = []
    pseed = 5000
    specs = [
        (-4.6, 2.1, -10.0, 3.1, 1.7, 14),
        (-1.6, 2.6, -11.5, 2.7, 1.5, 4),
        ( 1.6, 2.6, -11.5, 2.7, 1.5, -4),
        ( 4.6, 2.1, -10.0, 3.1, 1.7, -14),
        (-4.0,-0.4, -8.5, 2.4, 1.4, 18),
        ( 4.0,-0.4, -8.5, 2.4, 1.4,-18),
        (-1.8,-1.0, -9.8, 2.4, 1.3, 5),
        ( 1.8,-1.0, -9.8, 2.4, 1.3,-5),
    ]
    for spec in specs:
        panels.append(Panel(*spec, pseed))
        pseed += 1

    return rain, buildings, panels


def level_for(i, red=False, bias=0):
    levels = RED if red else GREEN
    if i == 0:
        return RED_HEAD if red else HEAD
    idx = clamp(4 - i // 2 + bias, 0, 4)
    return levels[idx]


def draw_rain_column(col, t, red=False, strength=1.0):
    fall = (t * col.speed + col.phase) % 8.2
    top = 3.9 - fall
    tick = int(t * 6.0)
    for i in range(col.length):
        y = top + i * 0.55
        while y < -4.4:
            y += 8.8
        while y > 4.4:
            y -= 8.8
        # Large dark gaps by skipping tail elements.
        if i > 5 and ((col.seed + i) % 4 == 0):
            continue
        color = level_for(i, red, 0)
        alpha = clamp(strength * (1.0 if i < 5 else 0.82), 0.0, 1.0)
        ch = hash_char(col.seed, i, tick + i // 3)
        draw_glyph(ch, col.x, y, col.z, col.size, color, alpha)


def draw_floor_field(t, red=False, density=1.0):
    """Wide perspective field of glyphs. No ceiling/tunnel."""
    tick = int(t * 4.0)
    rows = 19
    cols = 17
    for rz in range(rows):
        z = -4.5 - rz * 2.15
        # Slide field toward camera very slowly; wrap by row distance.
        z += (t * 0.55) % 2.15
        for cx in range(cols):
            if ((cx * 7 + rz * 11 + tick // 5) % 9) > int(5.5 * density):
                continue
            x = (cx - (cols - 1)/2) * 1.35
            seed = 7000 + rz * 97 + cx * 17
            ch = hash_char(seed, rz + cx, tick // 2)
            near = clamp((45.0 + z) / 40.0, 0.12, 1.0)
            idx = clamp(int(near * 4), 0, 4)
            color = (RED if red else GREEN)[idx]
            size = 0.12 + near * 0.08
            draw_glyph(ch, x, -3.0, z, size, color, 0.78, pitch=-90)


def draw_horizon_curtain(t, red=False):
    tick = int(t * 5.0)
    for cx in range(31):
        x = -13.5 + cx * 0.9
        if cx % 5 == 0:
            continue
        base = 9000 + cx * 19
        length = 5 + (cx * 7) % 8
        fall = (t * (0.35 + (cx % 4)*0.06) + cx * 0.41) % 7.5
        for i in range(length):
            y = 3.5 - ((fall + i * 0.52) % 7.2)
            col = level_for(i, red, -1)
            draw_glyph(hash_char(base, i, tick), x, y, -44.0, 0.17, col, 0.62)


def draw_building(b, t, red=False):
    left, right = b.x - b.w/2, b.x + b.w/2
    bottom, top = -3.0, -3.0 + b.h
    body = (0.0, 0.035, 0.0) if not red else (0.035, 0.0, 0.0)
    solid_quad(left, bottom, right, top, b.z, body, 0.90)
    frame_rect(left, bottom, right, top, b.z + 0.01, GREEN[2] if not red else RED[2], 0.55, 1.0)

    # facade code
    tick = int(t * 5)
    cols = max(2, int(b.w / 0.55))
    rows = max(4, int(b.h / 0.60))
    for c in range(cols):
        if (b.seed + c) % 4 == 0:
            continue
        x = left + 0.32 + c * ((b.w - 0.64) / max(1, cols - 1))
        phase = (t * (0.35 + (c % 3)*0.08) + c * 0.7) % max(1.0, b.h - 0.6)
        for r in range(rows):
            y = top - 0.35 - ((phase + r * 0.56) % max(0.7, b.h - 0.7))
            i = r % 7
            color = level_for(i, red, -1)
            draw_glyph(hash_char(b.seed+c, r, tick), x, y, b.z + 0.03, 0.11, color, 0.72)


def draw_city(t, buildings, red=False):
    # Wet "street" center line and ground code create urban depth.
    glDisable(GL_TEXTURE_2D)
    glColor4f(*(RED[1] if red else GREEN[1]), 0.45)
    glLineWidth(1.0)
    glBegin(GL_LINES)
    for x in (-3.2, 3.2):
        glVertex3f(x, -2.95, -4.0); glVertex3f(x, -2.95, -45.0)
    for z in range(6, 46, 4):
        zz = -float(z)
        glVertex3f(-3.2, -2.95, zz); glVertex3f(3.2, -2.95, zz)
    glEnd()
    glEnable(GL_TEXTURE_2D)

    for b in buildings:
        draw_building(b, t, red)

    # Lone silhouette in the street.
    draw_silhouette(0.2 + math.sin(t*0.18)*0.25, -2.95, -16.0, 1.0)


def draw_silhouette(x, floor_y, z, scale=1.0):
    """Simple black human silhouette against Matrix light."""
    glDisable(GL_TEXTURE_2D)
    glColor4f(0.0, 0.0, 0.0, 1.0)
    # body
    glBegin(GL_QUADS)
    glVertex3f(x-0.20*scale, floor_y, z)
    glVertex3f(x+0.20*scale, floor_y, z)
    glVertex3f(x+0.14*scale, floor_y+1.15*scale, z)
    glVertex3f(x-0.14*scale, floor_y+1.15*scale, z)
    # shoulders/head block
    glVertex3f(x-0.30*scale, floor_y+0.75*scale, z)
    glVertex3f(x+0.30*scale, floor_y+0.75*scale, z)
    glVertex3f(x+0.22*scale, floor_y+1.35*scale, z)
    glVertex3f(x-0.22*scale, floor_y+1.35*scale, z)
    glEnd()
    # head as small square—at 480x320 it reads cleaner than a polygon circle.
    solid_quad(x-0.16*scale, floor_y+1.25*scale,
               x+0.16*scale, floor_y+1.58*scale, z, (0.0,0.0,0.0), 1.0)
    glEnable(GL_TEXTURE_2D)


def draw_portal(t, red=False):
    z = -22.0
    pulse = 0.70 + 0.30 * (0.5 + 0.5*math.sin(t*3.0))
    green = RED_HEAD if red else CYAN

    # Massive luminous doorway without a texture/gradient.
    glDisable(GL_TEXTURE_2D)
    glColor4f(*green, 0.18*pulse)
    glBegin(GL_QUADS)
    glVertex3f(-3.5,-2.9,z); glVertex3f(3.5,-2.9,z)
    glVertex3f(3.5, 3.2,z); glVertex3f(-3.5,3.2,z)
    glEnd()
    glColor4f(*green, 0.95*pulse)
    glBegin(GL_QUADS)
    # left/right light pillars
    glVertex3f(-3.0,-2.9,z+0.02); glVertex3f(-2.55,-2.9,z+0.02)
    glVertex3f(-2.55,3.2,z+0.02); glVertex3f(-3.0,3.2,z+0.02)
    glVertex3f(2.55,-2.9,z+0.02); glVertex3f(3.0,-2.9,z+0.02)
    glVertex3f(3.0,3.2,z+0.02); glVertex3f(2.55,3.2,z+0.02)
    # top bar
    glVertex3f(-3.0,2.75,z+0.02); glVertex3f(3.0,2.75,z+0.02)
    glVertex3f(3.0,3.2,z+0.02); glVertex3f(-3.0,3.2,z+0.02)
    glEnd()
    glEnable(GL_TEXTURE_2D)

    # Two figures inside the light.
    draw_silhouette(-0.48, -2.9, z+0.06, 0.82)
    draw_silhouette( 0.52, -2.9, z+0.06, 0.82)

    # Dense code field around portal edges.
    tick = int(t*6)
    for side in (-1,1):
        for c in range(7):
            x = side * (3.7 + c*0.48)
            for r in range(9):
                if (c+r) % 5 == 0:
                    continue
                y = -2.7 + r*0.70
                ch = hash_char(11000+side*31+c, r, tick)
                draw_glyph(ch, x, y, z+0.10, 0.15,
                           level_for(r%7, red, -1), 0.75)


def panel_local_quad(panel, color, alpha):
    glPushMatrix()
    glTranslatef(panel.x, panel.y, panel.z)
    glRotatef(panel.yaw, 0, 1, 0)
    glDisable(GL_TEXTURE_2D)
    glColor4f(*color, alpha)
    glBegin(GL_QUADS)
    glVertex3f(-panel.w/2,-panel.h/2,0)
    glVertex3f( panel.w/2,-panel.h/2,0)
    glVertex3f( panel.w/2, panel.h/2,0)
    glVertex3f(-panel.w/2, panel.h/2,0)
    glEnd()
    glColor4f(*(0.02,0.62,0.12), 0.78)
    glLineWidth(1.0)
    glBegin(GL_LINE_STRIP)
    glVertex3f(-panel.w/2,-panel.h/2,0.01)
    glVertex3f( panel.w/2,-panel.h/2,0.01)
    glVertex3f( panel.w/2, panel.h/2,0.01)
    glVertex3f(-panel.w/2, panel.h/2,0.01)
    glVertex3f(-panel.w/2,-panel.h/2,0.01)
    glEnd()
    glEnable(GL_TEXTURE_2D)
    glPopMatrix()


def draw_operator(t, panels, red=False):
    # Operator silhouette in foreground center.
    draw_silhouette(0.0, -3.0, -6.2, 1.35)

    tick = int(t*6)
    for p in panels:
        panel_local_quad(p, (0.0, 0.025, 0.01), 0.96)
        # Populate screen with readable matrix code. Keep glyphs front-facing;
        # at small resolution this looks better than forcing exact screen rotation.
        cols = max(3, int(p.w / 0.38))
        rows = max(3, int(p.h / 0.38))
        for c in range(cols):
            if (p.seed+c) % 5 == 0:
                continue
            for r in range(rows):
                if (c*3+r*5+tick//3) % 4 != 0:
                    continue
                x = p.x - p.w*0.40 + c*(p.w*0.80/max(1,cols-1))
                y = p.y - p.h*0.36 + r*(p.h*0.72/max(1,rows-1))
                color = level_for((r+c)%7, red, -1)
                draw_glyph(hash_char(p.seed+c, r, tick), x, y, p.z+0.05,
                           0.08, color, 0.88)


def draw_scan_glitches(t, red=False):
    cycle = t % 19.0
    if not (15.7 < cycle < 16.3):
        return
    glDisable(GL_TEXTURE_2D)
    col = RED_HEAD if red else HEAD
    for i in range(4):
        y = -0.85 + i*0.45 + math.sin(t*120+i)*0.05
        glColor4f(*col, 0.20 + i*0.06)
        glBegin(GL_QUADS)
        glVertex3f(-1.0, y, 0); glVertex3f(1.0, y, 0)
        glVertex3f(1.0, y+0.035, 0); glVertex3f(-1.0, y+0.035, 0)
        glEnd()
    glEnable(GL_TEXTURE_2D)


def scene_weights(t):
    """Crossfade neighboring scene concepts, but always keep the field underneath."""
    pos = (t / SCENE_SECONDS) % len(SCENES)
    idx = int(pos)
    frac = pos - idx
    # smooth blend near final 2.8s
    blend_start = 0.80
    if frac < blend_start:
        return idx, None, 1.0, 0.0
    u = (frac - blend_start) / (1.0 - blend_start)
    u = u*u*(3.0 - 2.0*u)
    return idx, (idx+1)%len(SCENES), 1.0-u, u


def main():
    pygame.init()
    pygame.font.init()

    info = pygame.display.Info()
    w = info.current_w if 0 < info.current_w <= 800 else 480
    h = info.current_h if 0 < info.current_h <= 600 else 320

    pygame.display.set_caption("Matrix World Field")
    pygame.display.set_mode((w, h), FULLSCREEN | OPENGL | DOUBLEBUF)
    pygame.mouse.set_visible(False)

    glViewport(0, 0, w, h)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_ALPHA_TEST)
    glAlphaFunc(GL_GREATER, 0.14)

    tex = make_atlas()
    rain, buildings, panels = make_world()
    clock = pygame.time.Clock()
    start = time.monotonic()
    next_corrupt = random.uniform(18.0, 27.0)
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
                corrupt_until = t + random.uniform(0.65, 1.15)
                flash_until = t + 0.055
                next_corrupt = t + random.uniform(21.0, 34.0)
            red = t < corrupt_until

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(64.0, w / max(1.0, float(h)), 0.1, 90.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            # Wide cinematic camera. It drifts across the world; it does NOT fly into a vanishing-point tube.
            cam_x = math.sin(t * 0.105) * 1.05 + math.sin(t*0.041)*0.55
            cam_y = math.sin(t * 0.083 + 0.9) * 0.20
            yaw = math.sin(t * 0.067) * 5.2
            roll = math.sin(t * 0.043) * 1.1
            glRotatef(roll, 0, 0, 1)
            glRotatef(yaw, 0, 1, 0)
            glTranslatef(-cam_x, -cam_y, 0.0)

            glBindTexture(GL_TEXTURE_2D, tex)

            # Persistent world foundation.
            draw_floor_field(t, red, 1.0)
            draw_horizon_curtain(t, red)

            # Sparse rain columns are always around you.
            for col in rain:
                # Leave central negative space in city/portal scenes.
                draw_rain_column(col, t, red, 0.74)

            idx, nxt, wa, wb = scene_weights(t)

            def draw_scene(which, alpha):
                # We use alpha primarily to control density/intensity, not as a whole-scene blend.
                name = SCENES[which]
                if name == "FIELD":
                    # More floating depth—no geometry cage.
                    for col in rain[::2]:
                        draw_rain_column(col, t+1.7, red, 0.45*alpha)
                elif name == "CITY":
                    draw_city(t, buildings, red)
                elif name == "PORTAL":
                    draw_portal(t, red)
                elif name == "OPERATOR":
                    draw_operator(t, panels, red)

            draw_scene(idx, wa)
            if nxt is not None and wb > 0.25:
                draw_scene(nxt, wb)

            # Fast corruption scan pass in screen space.
            glDisable(GL_DEPTH_TEST)
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            draw_scan_glitches(t, red)

            if t < flash_until:
                glDisable(GL_TEXTURE_2D)
                c = RED_HEAD if red else HEAD
                glColor4f(*c, 0.78)
                glBegin(GL_QUADS)
                glVertex3f(-1,-1,0); glVertex3f(1,-1,0)
                glVertex3f(1,1,0); glVertex3f(-1,1,0)
                glEnd()
                glEnable(GL_TEXTURE_2D)

            glPopMatrix()
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
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
