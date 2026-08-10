#!/usr/bin/env python3
"""Matrix Live V11 — continuous SIMULATION WORLD for Pi 4 / 480x320.

One persistent world, not a scene carousel:
- believable dark city/street depth
- buildings, windows, road, reflections, distant portal
- Matrix code exists inside the world at all times
- simulation phases continuously bleed/reveal/rebuild the world
- no tunnel, no starburst, no waiting for separate scenes

Cycle (~24 sec): CITY -> CODE BLEED -> FULL REVEAL -> REBUILD -> CITY
"""
import math
import os
import time

os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame
from pygame.locals import DOUBLEBUF, FULLSCREEN, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_q
from OpenGL.GL import (
    GL_ALPHA_TEST, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST,
    GL_GREATER, GL_LINES, GL_LINE_LOOP, GL_MODELVIEW, GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS, GL_RGBA, GL_SRC_ALPHA,
    GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER, GL_UNSIGNED_BYTE,
    glAlphaFunc, glBegin, glBindTexture, glBlendFunc, glClear, glClearColor,
    glColor4f, glDeleteTextures, glDisable, glEnable, glEnd, glGenTextures,
    glLineWidth, glLoadIdentity, glMatrixMode, glPopMatrix, glPushMatrix,
    glRotatef, glTexCoord2f, glTexImage2D, glTexParameteri, glTranslatef,
    glVertex3f, glViewport,
)
from OpenGL.GLU import gluPerspective

W, H = 480, 320
GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<>+-*/{}[]:;=#$%@!?|"
ATLAS_COLS = 8
ATLAS_ROWS = math.ceil(len(GLYPHS) / ATLAS_COLS)

# High-contrast palette for the physical SPI LCD.
BLACK = (0.0, 0.0, 0.0)
CITY_DARK = (0.00, 0.055, 0.025)
CITY_MID = (0.00, 0.11, 0.045)
CITY_EDGE = (0.02, 0.30, 0.10)
G0 = (0.00, 0.30, 0.00)
G1 = (0.00, 0.52, 0.02)
G2 = (0.02, 0.78, 0.05)
G3 = (0.08, 1.00, 0.16)
HEAD = (0.72, 1.00, 0.76)
PORTAL = (0.24, 1.00, 0.68)
WARM = (0.82, 0.78, 0.34)
RED = (1.0, 0.05, 0.03)

CYCLE = 24.0


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def smoothstep(a, b, x):
    if a == b:
        return 0.0
    t = clamp((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def phase_amount(t):
    """0 = mostly real city, 1 = fully exposed Matrix code."""
    p = t % CYCLE
    if p < 6.0:      # city breathing
        return 0.12 + 0.05 * math.sin(p * 0.9)
    if p < 11.0:     # code bleeds through
        return 0.12 + 0.88 * smoothstep(6.0, 11.0, p)
    if p < 16.0:     # full reveal
        return 1.0
    if p < 22.0:     # rebuild simulation
        return 1.0 - 0.88 * smoothstep(16.0, 22.0, p)
    return 0.12


def phase_name(t):
    p = t % CYCLE
    if p < 6: return "SIMULATION"
    if p < 11: return "CODE BLEED"
    if p < 16: return "REVEALED"
    if p < 22: return "REBUILD"
    return "SIMULATION"


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
    return (cx / ATLAS_COLS,
            1.0 - ((cy + 1) / ATLAS_ROWS),
            (cx + 1) / ATLAS_COLS,
            1.0 - (cy / ATLAS_ROWS))


def hchar(seed, idx, tick):
    n = (seed * 1103515245 + idx * 12345 + tick * 2654435761) & 0xFFFFFFFF
    return GLYPHS[n % len(GLYPHS)]


def billboard(ch, x, y, z, size, color=G3, alpha=1.0, rot_y=0.0, rot_x=0.0):
    u0, v0, u1, v1 = glyph_uv(ch)
    hw, hh = size * 0.52, size
    glPushMatrix()
    glTranslatef(x, y, z)
    if rot_y: glRotatef(rot_y, 0, 1, 0)
    if rot_x: glRotatef(rot_x, 1, 0, 0)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(u0, v0); glVertex3f(-hw, -hh, 0)
    glTexCoord2f(u1, v0); glVertex3f( hw, -hh, 0)
    glTexCoord2f(u1, v1); glVertex3f( hw,  hh, 0)
    glTexCoord2f(u0, v1); glVertex3f(-hw,  hh, 0)
    glEnd()
    glPopMatrix()


def quad(x0, y0, x1, y1, z, color, alpha=1.0):
    glDisable(GL_TEXTURE_2D)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z); glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z); glVertex3f(x0, y1, z)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def line(x0, y0, z0, x1, y1, z1, color, width=1.0, alpha=1.0):
    glDisable(GL_TEXTURE_2D)
    glLineWidth(width)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_LINES)
    glVertex3f(x0, y0, z0); glVertex3f(x1, y1, z1)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def box_outline(x0, y0, x1, y1, z, color, width=1.4, alpha=1.0):
    glDisable(GL_TEXTURE_2D)
    glLineWidth(width)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_LINE_LOOP)
    glVertex3f(x0, y0, z); glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z); glVertex3f(x0, y1, z)
    glEnd()
    glEnable(GL_TEXTURE_2D)


def draw_sky_rain(t, reveal):
    """Distant code rain always visible; stronger when reality breaks."""
    tick = int(t * 7.0)
    cols = 34
    for c in range(cols):
        x = -7.2 + c * 14.4 / (cols - 1)
        z = -15.0 - ((c * 4.1) % 26.0)
        speed = 0.50 + (c % 7) * 0.055
        head = 4.5 - ((t * speed + c * 0.43) % 9.0)
        length = 5 + int(5 * reveal) + (c % 3)
        for i in range(length):
            y = head + i * 0.58
            if y > 4.4: y -= 9.0
            if i == 0:
                color = HEAD
            elif i < 3:
                color = G3 if reveal > 0.45 else G2
            else:
                color = G2 if reveal > 0.7 else G0
            alpha = 0.32 + 0.68 * reveal if i > 2 else 0.65 + 0.35 * reveal
            billboard(hchar(1200+c, i, tick+i//2), x, y, z, 0.17, color, alpha)


def draw_street(t, reveal):
    # road body
    quad(-6.3, -3.18, 6.3, -2.92, -6.0, CITY_DARK, 1.0)

    # road/curb perspective lines
    for side in (-1, 1):
        line(side * 2.1, -3.0, -5.0, side * 5.8, -3.0, -34.0,
             G1 if reveal > 0.5 else CITY_EDGE, 2.0, 0.75)
        line(side * 3.2, -2.98, -5.0, side * 7.5, -2.98, -34.0,
             G0 if reveal > 0.35 else CITY_MID, 1.0, 0.7)

    # center lane broken marks
    for k in range(9):
        z0 = -6.0 - k * 3.0
        z1 = z0 - 1.2
        line(0.0, -2.98, z0, 0.0, -2.98, z1,
             G2 if reveal > 0.65 else CITY_EDGE, 2.0, 0.75)

    # Matrix glyph reflections crawling across the wet street
    tick = int(t * 4.5)
    rows = 9
    for r in range(rows):
        z = -6.0 - r * 2.8
        for c in range(13):
            if (c + r + tick) % 4 == 0 and reveal < 0.55:
                continue
            x = -4.8 + c * 0.80
            color = G3 if r < 2 else G2 if r < 6 else G1
            alpha = 0.25 + 0.72 * reveal
            billboard(hchar(2400+r*17+c, c, tick+r), x, -2.94, z,
                      0.12 if r > 4 else 0.14, color, alpha, rot_x=-90)


def draw_building(x, z, w, h, seed, t, reveal, side=0):
    y0 = -2.95
    y1 = y0 + h
    # opaque city shell fades as code reveal increases
    shell_alpha = clamp(1.0 - reveal * 0.82)
    shell = CITY_DARK if seed % 2 else CITY_MID
    quad(x-w/2, y0, x+w/2, y1, z, shell, shell_alpha)

    # edge/wireframe emerges through the shell
    edge = G2 if reveal > 0.55 else CITY_EDGE
    box_outline(x-w/2, y0, x+w/2, y1, z+0.015, edge,
                1.0 + reveal * 1.5, 0.45 + 0.55*reveal)

    cols = max(2, int(w / 0.58))
    rows = max(3, int(h / 0.64))
    tick = int(t * 4.0)
    for r in range(rows):
        for c in range(cols):
            gx = x - w/2 + (c+0.5) * (w/cols)
            gy = y0 + (r+0.55) * (h/rows)
            # normal building windows
            on = ((seed + r*5 + c*7 + int(t*0.7)) % 7) < 3
            if reveal < 0.72 and on:
                wc = WARM if seed % 3 == 0 else CITY_EDGE
                quad(gx-0.08, gy-0.09, gx+0.08, gy+0.09, z+0.025, wc,
                     0.35 + 0.45*(1.0-reveal))
            # code underneath the facade
            if reveal > 0.18 or ((r+c+seed) % 6 == 0):
                alpha = clamp(0.15 + reveal*0.95)
                col = HEAD if (r+c+tick+seed) % 11 == 0 else G3 if reveal > 0.6 else G1
                billboard(hchar(seed+c*13, r, tick), gx, gy, z+0.035,
                          0.105, col, alpha)

    # vertical code stream dripping off some facades
    if reveal > 0.35:
        for c in range(0, cols, 2):
            gx = x - w/2 + (c+0.5)*(w/cols)
            head = y1 - ((t*(0.45+(c%3)*0.09)+c*0.5) % max(1.0,h))
            for i in range(5):
                gy = head - i*0.42
                if gy < y0: gy += h
                billboard(hchar(seed+500+c, i, tick), gx, gy, z+0.05,
                          0.095, HEAD if i==0 else G2, 0.45+0.5*reveal)


def draw_city(t, reveal):
    # Near facades make the street feel surrounded, distant ones add scale.
    buildings = [
        (-5.55,-7.0,2.7,5.8,101), (-4.0,-9.5,2.1,4.8,102),
        (-2.7,-12.0,1.7,3.8,103), (-1.65,-15.0,1.3,3.0,104),
        ( 1.65,-15.0,1.3,3.1,105), ( 2.75,-12.0,1.7,3.9,106),
        ( 4.05,-9.5,2.1,5.0,107), ( 5.60,-7.0,2.8,6.0,108),
        (-5.4,-18.0,3.4,6.4,109), (5.4,-18.0,3.4,6.6,110),
        (-3.0,-23.0,2.6,5.0,111), (3.1,-23.0,2.7,5.4,112),
    ]
    for b in buildings:
        draw_building(*b, t=t, reveal=reveal)

    # utility lines / elevated structure-like geometry
    for y in (-0.4, 0.25, 0.95):
        line(-6.3, y, -10.0, 6.3, y, -10.0,
             G1 if reveal > 0.5 else CITY_EDGE, 1.0, 0.40+0.45*reveal)


def draw_portal(t, reveal):
    """Persistent distant door/corridor instead of a separate portal scene."""
    z = -27.0
    pulse = 0.75 + 0.25*math.sin(t*3.2)
    visibility = 0.22 + 0.78*reveal
    c = (0.10, pulse, 0.42)
    # doorway frame
    quad(-1.65,-2.9,-1.40,2.2,z,c,visibility)
    quad( 1.40,-2.9, 1.65,2.2,z,c,visibility)
    quad(-1.65,1.95,1.65,2.2,z,c,visibility)
    # receding corridor ribs
    for k in range(5):
        zz = z - k*2.0
        s = 1.0 + k*0.16
        box_outline(-1.6*s,-2.85,1.6*s,2.15,zz,G2,1.2,0.30+0.55*reveal)
    # two silhouettes in the light
    if reveal > 0.45:
        for x in (-0.34,0.38):
            quad(x-0.10,-2.75,x+0.10,-1.5,z+0.3,BLACK,1.0)
            quad(x-0.17,-1.5,x+0.17,-1.12,z+0.3,BLACK,1.0)


def draw_foreground_code(t, reveal):
    """Close code curtains pass the camera during reveal to sell 3D depth."""
    if reveal < 0.45:
        return
    tick = int(t*8)
    for side in (-1, 1):
        base_x = side * (5.25 - 0.6*math.sin(t*0.25))
        for col in range(3):
            z = -4.7 - col*2.3
            head = 3.6 - ((t*(0.7+col*0.1)+col*1.1) % 7.2)
            for i in range(8):
                y = head + i*0.58
                if y > 3.7: y -= 7.5
                colr = HEAD if i==0 else G3 if i<3 else G1
                billboard(hchar(7000+col+(10 if side>0 else 0), i, tick),
                          base_x, y, z, 0.20, colr, 0.35+0.60*reveal,
                          rot_y=(-90 if side>0 else 90))


def draw_operator_echo(t, reveal):
    """Very brief monitor echo near peak reveal; part of the same world, not a new scene."""
    p = t % CYCLE
    if not (13.0 < p < 15.2):
        return
    strength = math.sin((p-13.0)/2.2*math.pi)
    if strength <= 0: return
    glPushMatrix()
    glTranslatef(0.0, 0.15, -4.8)
    positions = [(-3.5,1.55),(0.0,1.8),(3.5,1.55),(-2.2,-0.25),(2.2,-0.25)]
    tick = int(t*7)
    for j,(cx,cy) in enumerate(positions):
        box_outline(cx-1.05,cy-0.62,cx+1.05,cy+0.62,0,G2,1.5,0.28*strength)
        for c in range(5):
            for r in range(3):
                if (c+r+j)%3==0: continue
                billboard(hchar(8000+j*20+c,r,tick), cx-0.75+c*0.38,
                          cy+0.36-r*0.34,0.02,0.085,G2,0.30*strength)
    glPopMatrix()


def draw_phase_label(name, reveal):
    color = G2 if reveal < 0.6 else HEAD
    for i,ch in enumerate(name):
        if ch == " ":
            continue
        if ch in GLYPHS:
            billboard(ch, -5.85+i*0.30, 3.35, -5.0, 0.115, color, 0.55)


def flash_overlay(color, alpha):
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    glColor4f(color[0],color[1],color[2],alpha)
    glBegin(GL_QUADS)
    glVertex3f(-1,-1,0); glVertex3f(1,-1,0); glVertex3f(1,1,0); glVertex3f(-1,1,0)
    glEnd()
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)


def main():
    pygame.init(); pygame.font.init()
    pygame.display.set_caption("Matrix Simulation World V11")
    pygame.display.set_mode((W,H), FULLSCREEN|OPENGL|DOUBLEBUF)
    pygame.mouse.set_visible(False)

    glViewport(0,0,W,H)
    glClearColor(0,0,0,1)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_ALPHA_TEST)
    glAlphaFunc(GL_GREATER,0.08)

    tex = make_atlas()
    clock = pygame.time.Clock()
    start = time.monotonic()
    running = True
    prev_phase = ""
    flash_until = -1.0
    flash_color = HEAD

    try:
        while running:
            t = time.monotonic()-start
            for e in pygame.event.get():
                if e.type == QUIT: running=False
                elif e.type == KEYDOWN and e.key in (K_ESCAPE,K_q): running=False

            reveal = phase_amount(t)
            pname = phase_name(t)
            if pname != prev_phase:
                flash_until = t + 0.045
                flash_color = RED if pname == "REVEALED" else HEAD
                prev_phase = pname

            glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
            glMatrixMode(GL_PROJECTION); glLoadIdentity()
            gluPerspective(67.0,W/float(H),0.1,90.0)
            glMatrixMode(GL_MODELVIEW); glLoadIdentity()

            # slow shoulder-level drift like exploring a city, not flying through a tube
            camx = math.sin(t*0.19)*0.32
            camy = math.sin(t*0.13+0.8)*0.10
            yaw = math.sin(t*0.11)*2.2
            roll = math.sin(t*0.07)*0.7
            glRotatef(roll,0,0,1)
            glRotatef(yaw,0,1,0)
            glTranslatef(-camx,-camy,0)

            glBindTexture(GL_TEXTURE_2D,tex)
            draw_sky_rain(t,reveal)
            draw_street(t,reveal)
            draw_city(t,reveal)
            draw_portal(t,reveal)
            draw_foreground_code(t,reveal)
            draw_operator_echo(t,reveal)
            draw_phase_label(pname,reveal)

            # subtle reality-tear flashes at key transitions
            p = t % CYCLE
            if 10.85 < p < 10.92 or 15.90 < p < 15.97:
                flash_overlay(HEAD,0.28)
            elif t < flash_until:
                flash_overlay(flash_color,0.38)

            pygame.display.flip()
            clock.tick(60)
    finally:
        try: glDeleteTextures([tex])
        except Exception: pass
        pygame.quit()


if __name__ == "__main__":
    main()
