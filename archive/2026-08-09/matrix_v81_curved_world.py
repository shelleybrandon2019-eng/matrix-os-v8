#!/usr/bin/env python3
import os
import sys
import time

os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")

import pygame
from pygame.locals import OPENGL, DOUBLEBUF, FULLSCREEN, QUIT, KEYDOWN, K_ESCAPE, K_q, K_SPACE, K_r
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

VERTEX_SHADER = r"""
#version 120
void main() { gl_Position = gl_Vertex; }
"""

FRAGMENT_SHADER = r"""
#version 120

uniform vec2 uResolution;
uniform float uTime;
uniform float uBoost;
uniform float uRedHold;

#define PI 3.14159265359

float hash11(float p) {
    return fract(sin(p * 127.1) * 43758.5453123);
}

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float glyph(vec2 uv, vec2 id, float mutate) {
    vec2 f = fract(uv);
    vec2 px = floor(f * vec2(5.0, 7.0));
    float box = step(0.10, f.x) * (1.0-step(0.90, f.x)) *
                step(0.07, f.y) * (1.0-step(0.93, f.y));

    float n = hash11(id.x*31.7 + id.y*71.3 + px.x*13.1 + px.y*41.9 + mutate*109.0);
    float core = step(0.66, n);
    float spine = (1.0-step(0.17, abs(px.x-2.0))) * step(0.57, hash11(id.y + mutate*5.0));
    float bar = (1.0-step(0.17, abs(px.y-3.0))) * step(0.62, hash11(id.x*4.0 + mutate));
    return box * max(core, max(spine, bar));
}

float matrixLayer(vec2 p, float layer, float t, float speed, out float headMask) {
    float col = floor(p.x);
    float rnd = hash11(col*17.31 + layer*91.7);

    // Each column falls at its own speed.
    p.y += t * speed * (0.72 + rnd*1.45);
    vec2 id = floor(p);
    float mutate = floor(t*0.62 + hash21(id + layer)*4.0);
    float g = glyph(p, id, mutate);

    // Break streams into chunks so the wall has gaps and darkness.
    float group = floor(id.y / (10.0 + floor(rnd*8.0)));
    float alive = step(0.30, hash11(col*9.5 + group*4.3 + layer*17.0));

    float phase = fract((id.y + rnd*31.0) / (16.0 + rnd*18.0));
    float head = 1.0 - smoothstep(0.00, 0.10, phase);
    float tail = pow(max(0.0, 1.0-phase), 2.0);

    headMask = g * head * alive;
    return g * alive * (0.16 + tail*1.15 + head*2.25);
}

void main() {
    vec2 frag = gl_FragCoord.xy;
    vec2 uv = (frag*2.0 - uResolution.xy) / uResolution.y;
    float t = uTime;

    // Camera sway and slight roll. This keeps the view from feeling like a fixed pipe.
    float roll = sin(t*0.17)*0.055 + sin(t*0.071)*0.035;
    mat2 rot = mat2(cos(roll), -sin(roll), sin(roll), cos(roll));
    uv = rot * uv;
    uv.x += sin(t*0.23)*0.055 + sin(t*0.071)*0.035;
    uv.y += cos(t*0.19)*0.035;

    // Horizontal glitch slices.
    float cycle = mod(t, 18.0);
    float glitch = step(10.8, cycle) * (1.0-step(11.38, cycle));
    float band = floor((frag.y + sin(t*19.0)*16.0)/9.0);
    float bandRnd = hash11(band + floor(t*24.0));
    uv.x += glitch * (bandRnd-0.5) * 0.17;

    // Warp space to make the corridor breathe and buckle.
    float r0 = length(uv);
    float bend = sin(t*0.31 + r0*7.0)*0.018 + sin(t*0.11 + uv.y*5.0)*0.012;
    uv += normalize(uv + vec2(0.0001)) * bend;

    float r = max(length(uv), 0.028);
    float ang = atan(uv.y, uv.x);

    // Circular/curved environment mapping.
    float depth = 1.0 / r;
    float forwardSpeed = 1.08 + uBoost*3.2;
    float z = depth*1.15 + t*forwardSpeed;

    // Wrap code around the curved chamber. The slight z-dependent twist makes walls bend.
    float twist = sin(z*0.16 + t*0.14)*0.23 + sin(z*0.055)*0.17;
    float around = (ang + twist) / (2.0*PI);

    // Main curved shell.
    vec2 p1 = vec2(around*48.0, z*1.26);
    float h1;
    float m1 = matrixLayer(p1, 1.0, t, 1.00 + uBoost*0.38, h1);

    // Secondary offset shell adds depth and makes code overlap instead of reading as a single wall.
    vec2 p2 = vec2(around*31.0 + sin(z*0.11)*2.2, z*0.83 + 4.0);
    float h2;
    float m2 = matrixLayer(p2, 2.0, t, 0.58 + uBoost*0.22, h2);

    // Large dark broken panels/voids. These destroy the perfect continuous tunnel look.
    vec2 sectorId = floor(vec2(around*10.0, z*0.075));
    float sectorNoise = hash21(sectorId);
    float voidMask = mix(0.30, 1.0, step(0.34, sectorNoise));
    float edgeBreak = 0.74 + 0.26*sin(ang*6.0 + z*0.09 + sin(t*0.2));
    float shell = (m1*0.92 + m2*0.38) * voidMask * edgeBreak;

    // Bright perspective bands / structural seams.
    float seamA = 1.0-smoothstep(0.465, 0.5, abs(fract(around*12.0)-0.5));
    float seamZ = 1.0-smoothstep(0.465, 0.5, abs(fract(z*0.115)-0.5));
    float seams = (seamA*0.018 + seamZ*0.025) * voidMask;

    // Near-camera free-floating code curtains. Makes the world feel larger than one surface.
    vec2 drift = uv;
    drift.x += sin(t*0.16)*0.4;
    drift *= vec2(7.0, 8.5);
    drift.y += t*0.75;
    float curtainId = floor(drift.x);
    float curtainRnd = hash11(curtainId*23.0);
    float curtainHead;
    float curtain = matrixLayer(drift + vec2(curtainRnd*2.0, 0.0), 5.0, t, 0.55, curtainHead);
    curtain *= smoothstep(0.58, 1.35, length(uv));
    curtain *= step(0.77, curtainRnd) * 0.28;

    // Vanishing void: mostly black center with a restrained green core.
    float center = exp(-r*13.0);
    float centerCore = exp(-r*31.0);
    float centerDark = smoothstep(0.032, 0.18, r);
    shell *= centerDark;

    // Random white/green electrical flash after glitch.
    float fd = cycle - 11.48;
    float flash = exp(-(fd*fd)*190.0);
    float lightning = flash * (0.55 + 0.45*sin(frag.x*0.11 + frag.y*0.07 + t*50.0));

    // Automatic red corruption event near the end of every 18s cycle, plus hold-R manual mode.
    float autoRed = smoothstep(13.8, 14.35, cycle) * (1.0-smoothstep(16.3, 17.2, cycle));
    float redMode = clamp(max(autoRed, uRedHold), 0.0, 1.0);
    float redPulse = 0.68 + 0.32*sin(t*8.0 + r*18.0);

    float brightness = shell + curtain;
    vec3 green = vec3(0.0, 0.82, 0.19);
    vec3 greenHead = vec3(0.55, 1.0, 0.69);
    vec3 red = vec3(0.95, 0.035, 0.018);
    vec3 redHead = vec3(1.0, 0.55, 0.32);

    vec3 baseCol = mix(green, red*redPulse, redMode);
    vec3 headCol = mix(greenHead, redHead, redMode);

    vec3 color = baseCol * brightness;
    color += headCol * (h1*0.88 + h2*0.26 + curtainHead*0.20);
    color += baseCol * seams;
    color += mix(vec3(0.0,0.34,0.07), vec3(0.38,0.0,0.0), redMode) * center * 0.38;
    color += mix(vec3(0.0,0.78,0.17), vec3(0.95,0.08,0.02), redMode) * centerCore * 0.85;

    // Brief radial shockwave during the red event.
    float shockPhase = cycle - 14.2;
    float shockRadius = shockPhase*0.72;
    float shock = exp(-pow((r-shockRadius)*26.0, 2.0)) * step(0.0, shockPhase) * (1.0-step(1.25, shockPhase));
    color += mix(vec3(0.1,1.0,0.35), vec3(1.0,0.16,0.03), redMode) * shock*0.40;

    color += vec3(0.72, 1.0, 0.80) * lightning * 0.72;

    // LCD-friendly vignette and scanline texture.
    float vignette = 1.0-smoothstep(0.75, 1.62, length(uv));
    float scan = 0.945 + 0.055*sin(frag.y*1.58 + t*6.0);
    color *= (0.55 + 0.45*vignette) * scan;

    // Chromatic split during glitches.
    color.r += glitch * brightness * 0.12;
    color.b += glitch * brightness * 0.09;

    // Tone map bright stream heads instead of hard clipping them.
    color = 1.0-exp(-color*1.17);
    gl_FragColor = vec4(color, 1.0);
}
"""


def main():
    pygame.init()
    pygame.display.init()
    pygame.mouse.set_visible(False)

    info = pygame.display.Info()
    width = info.current_w if info.current_w > 0 else 480
    height = info.current_h if info.current_h > 0 else 320

    flags = OPENGL | DOUBLEBUF | FULLSCREEN
    try:
        pygame.display.set_mode((width, height), flags, vsync=1)
    except TypeError:
        pygame.display.set_mode((width, height), flags)

    pygame.display.set_caption("Matrix V8.1 Curved World")

    version = glGetString(GL_VERSION)
    renderer = glGetString(GL_RENDERER)
    print("Matrix V8.1")
    print(f"Display: {width}x{height}")
    print("OpenGL:", version.decode(errors="ignore") if version else "unknown")
    print("Renderer:", renderer.decode(errors="ignore") if renderer else "unknown")
    print("ESC/Q quit | SPACE speed | hold R red mode")

    program = compileProgram(
        compileShader(VERTEX_SHADER, GL_VERTEX_SHADER),
        compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER),
    )
    glUseProgram(program)

    res_loc = glGetUniformLocation(program, "uResolution")
    time_loc = glGetUniformLocation(program, "uTime")
    boost_loc = glGetUniformLocation(program, "uBoost")
    red_loc = glGetUniformLocation(program, "uRedHold")
    glUniform2f(res_loc, float(width), float(height))

    clock = pygame.time.Clock()
    start = time.perf_counter()
    fps_timer = start
    frame_count = 0
    boost = 0.0
    red_hold = 0.0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key in (K_ESCAPE, K_q):
                running = False

        keys = pygame.key.get_pressed()
        boost_target = 1.0 if keys[K_SPACE] else 0.0
        red_target = 1.0 if keys[K_r] else 0.0
        boost += (boost_target - boost) * 0.09
        red_hold += (red_target - red_hold) * 0.12

        now = time.perf_counter()
        elapsed = now - start

        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(program)
        glUniform1f(time_loc, elapsed)
        glUniform1f(boost_loc, boost)
        glUniform1f(red_loc, red_hold)

        glBegin(GL_QUADS)
        glVertex2f(-1.0, -1.0)
        glVertex2f( 1.0, -1.0)
        glVertex2f( 1.0,  1.0)
        glVertex2f(-1.0,  1.0)
        glEnd()

        pygame.display.flip()
        clock.tick(60)

        frame_count += 1
        if now - fps_timer >= 2.0:
            fps = frame_count / (now - fps_timer)
            print(f"FPS: {fps:.1f}", flush=True)
            frame_count = 0
            fps_timer = now

    glDeleteProgram(program)
    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nMATRIX V8.1 FAILED:")
        print(exc)
        print("\nCopy/paste this error back to ChatGPT.")
        pygame.quit()
        sys.exit(1)
