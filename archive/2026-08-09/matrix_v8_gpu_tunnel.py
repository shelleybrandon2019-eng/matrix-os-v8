#!/usr/bin/env python3
import os
import sys
import time

# Help apps launched from SSH find the logged-in desktop.
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")

import pygame
from pygame.locals import OPENGL, DOUBLEBUF, FULLSCREEN, QUIT, KEYDOWN, K_ESCAPE, K_q, K_SPACE
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

VERTEX_SHADER = r"""
#version 120
void main()
{
    gl_Position = gl_Vertex;
}
"""

FRAGMENT_SHADER = r"""
#version 120

uniform vec2 uResolution;
uniform float uTime;
uniform float uBoost;

float hash11(float p)
{
    return fract(sin(p * 127.1) * 43758.5453123);
}

float hash21(vec2 p)
{
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

// Fake 5x7 "Matrix glyph". Every character cell gets a repeatable
// little digital symbol without needing a font texture.
float glyph(vec2 uv, vec2 cellId, float mutate)
{
    vec2 f = fract(uv);
    float margin =
        step(0.10, f.x) * (1.0 - step(0.90, f.x)) *
        step(0.08, f.y) * (1.0 - step(0.92, f.y));

    vec2 px = floor(f * vec2(5.0, 7.0));
    float n = hash11(
        cellId.x * 19.13 +
        cellId.y * 73.71 +
        px.x * 11.31 +
        px.y * 37.17 +
        mutate * 101.0
    );

    // A few extra strokes make the random cells read more like symbols.
    float core = step(0.64, n);
    float spine = step(abs(px.x - 2.0), 0.15) * step(0.50, hash11(cellId.y + mutate * 7.0));
    float cap = step(abs(px.y - 1.0), 0.15) * step(0.55, hash11(cellId.x * 3.0 + mutate));

    return margin * max(core, max(spine, cap));
}

void main()
{
    vec2 frag = gl_FragCoord.xy;
    vec2 uv = (frag * 2.0 - uResolution.xy) / uResolution.y;

    float t = uTime;
    float eventCycle = mod(t, 12.0);

    // Slow camera wander.
    uv += vec2(
        sin(t * 0.31) * 0.018,
        cos(t * 0.27) * 0.014
    );

    // Brief distortion every 12 seconds.
    float glitchWindow =
        step(7.15, eventCycle) *
        (1.0 - step(7.65, eventCycle));

    float slice = floor((frag.y + sin(t * 13.0) * 20.0) / 10.0);
    float sliceNoise = hash11(slice + floor(t * 18.0));
    uv.x += glitchWindow * (sliceNoise - 0.5) * 0.12;

    // Square tunnel: whichever axis dominates tells us which wall we hit.
    float ax = abs(uv.x);
    float ay = abs(uv.y);
    float radius = max(ax, ay);
    float safeRadius = max(radius, 0.026);

    float depth = 1.0 / safeRadius;

    float across;
    float wallId;
    if (ax > ay) {
        across = uv.y / safeRadius;
        wallId = (uv.x > 0.0) ? 1.0 : 3.0;
    } else {
        across = uv.x / safeRadius;
        wallId = (uv.y > 0.0) ? 0.0 : 2.0;
    }

    // Forward motion. SPACE gives a temporary speed boost.
    float baseSpeed = 1.18 + uBoost * 2.8;
    float wallX = across * 7.4;
    float column = floor(wallX);

    float colRand = hash11(column * 9.17 + wallId * 41.0);
    float streamSpeed = baseSpeed * (0.85 + colRand * 1.35);

    // Perspective makes "rows" race toward the viewer from the center.
    float wallY = depth * 1.35 + t * streamSpeed;

    // Character grid.
    vec2 charUV = vec2(wallX, wallY * 1.23);
    vec2 charId = floor(charUV);

    // Slowly mutate the symbol set.
    float mutate = floor(t * 0.55 + hash21(charId) * 4.0);
    float g = glyph(charUV, charId, mutate);

    // Break up columns so they look like individual Matrix streams.
    float alive = step(0.22, hash11(column * 23.7 + floor(charId.y / 13.0) * 5.2 + wallId));
    g *= alive;

    // Traveling bright head and fading tail.
    float streamPhase = fract(
        wallY * 0.070 +
        colRand +
        wallId * 0.17
    );
    float head = 1.0 - smoothstep(0.00, 0.080, streamPhase);
    float tail = pow(1.0 - streamPhase, 2.1);
    float intensity = g * (0.22 + tail * 1.35 + head * 2.7);

    // Subtle perspective ribs reinforce the corridor geometry.
    float ribPhase = abs(fract(depth * 0.42 + t * baseSpeed * 0.31) - 0.5);
    float ribs = smoothstep(0.455, 0.495, ribPhase) * 0.055;

    // Darken the far center enough to preserve depth.
    float nearFade = smoothstep(0.035, 0.16, radius);
    intensity *= nearFade;

    // Slightly different luminance on each wall.
    float wallShade = 0.80 + 0.12 * sin(wallId * 1.7 + 0.6);
    intensity *= wallShade;

    // Green vanishing point / "portal" glow.
    float centerGlow = exp(-length(uv) * 15.0);
    float halo = exp(-length(uv) * 5.5) * 0.10;

    // Event flash immediately after the glitch.
    float flashDelta = eventCycle - 7.72;
    float flash = exp(-(flashDelta * flashDelta) * 165.0) * 0.72;

    // A few tiny scanline variations keep the LCD image alive.
    float scan = 0.94 + 0.06 * sin(frag.y * 1.65 + t * 7.0);

    vec3 deepGreen = vec3(0.0, 0.72, 0.17);
    vec3 headGreen = vec3(0.52, 1.0, 0.68);

    vec3 color = deepGreen * intensity;
    color += headGreen * (g * head * 0.95);
    color += vec3(0.0, 0.30, 0.05) * ribs * nearFade;
    color += vec3(0.0, 0.72, 0.20) * centerGlow * 1.35;
    color += vec3(0.0, 0.35, 0.08) * halo;
    color += vec3(0.62, 1.0, 0.74) * flash;

    // Soft edge vignette.
    float vignette = 1.0 - smoothstep(0.78, 1.65, length(uv));
    color *= (0.58 + 0.42 * vignette) * scan;

    // Small glitch color split.
    color.r += glitchWindow * g * 0.10;
    color.b += glitchWindow * g * 0.08;

    // Tone map instead of clipping all the bright heads.
    color = 1.0 - exp(-color * 1.18);

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
        # Older SDL/Pygame build without the vsync keyword.
        pygame.display.set_mode((width, height), flags)

    pygame.display.set_caption("Matrix V8 GPU Tunnel")

    version = glGetString(GL_VERSION)
    renderer = glGetString(GL_RENDERER)
    print("Matrix V8")
    print(f"Display: {width}x{height}")
    print("OpenGL:", version.decode(errors="ignore") if version else "unknown")
    print("Renderer:", renderer.decode(errors="ignore") if renderer else "unknown")
    print("ESC or Q = quit | hold SPACE = hyperspeed")

    program = compileProgram(
        compileShader(VERTEX_SHADER, GL_VERTEX_SHADER),
        compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
    )
    glUseProgram(program)

    res_loc = glGetUniformLocation(program, "uResolution")
    time_loc = glGetUniformLocation(program, "uTime")
    boost_loc = glGetUniformLocation(program, "uBoost")

    glUniform2f(res_loc, float(width), float(height))

    clock = pygame.time.Clock()
    start = time.perf_counter()
    boost = 0.0
    fps_timer = start
    frame_count = 0

    running = True
    while running:
        boost_target = 0.0

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key in (K_ESCAPE, K_q):
                running = False

        keys = pygame.key.get_pressed()
        if keys[K_SPACE]:
            boost_target = 1.0

        # Smooth acceleration/deceleration.
        boost += (boost_target - boost) * 0.09

        now = time.perf_counter()
        elapsed = now - start

        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(program)
        glUniform1f(time_loc, elapsed)
        glUniform1f(boost_loc, boost)

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
        print("\nMATRIX V8 FAILED:")
        print(exc)
        print("\nCopy/paste this error back to ChatGPT.")
        pygame.quit()
        sys.exit(1)
