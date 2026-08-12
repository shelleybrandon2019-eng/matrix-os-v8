#!/usr/bin/env python3
"""Matrix OS tunnel reveal: continuous rain, arched tunnel, four live temps, 24-hour clock."""
from __future__ import annotations

import random
import sys
from typing import Dict, List, Optional, Tuple

import pygame

from temp_scene_director import (
    FORM_SECONDS,
    GREEN,
    HEIGHT,
    MATRIX_CHARS,
    MELT_SECONDS,
    SHADOW,
    WIDTH,
    DualNeoReveal,
    MatrixDashboard as BaseMatrixDashboard,
    RevealGlyph,
    choose_cyber_font,
    clamp,
    format_temp,
    smoothstep,
    temp_color,
)


class FourTempReveal(DualNeoReveal):
    """Four sensor readings collect from code, hold cleanly, then melt into rain."""

    def __init__(
        self,
        outside: Optional[float],
        inside: Optional[float],
        front_room: Optional[float],
        bedroom: Optional[float],
        label_font: pygame.font.Font,
        value_font: pygame.font.Font,
        glyph_font: pygame.font.Font,
    ) -> None:
        self.label_font = label_font
        self.value_font = value_font
        self.glyph_font = glyph_font
        self.phase = "form"
        self.elapsed = 0.0
        self.finished = False
        self.cache: Dict[Tuple[str, Tuple[int, int, int]], pygame.Surface] = {}
        self.particles: List[RevealGlyph] = []

        left_x = 126
        right_x = 354
        self.layout = [
            ("OUTSIDE", label_font, GREEN, left_x, 145),
            (format_temp(outside), value_font, temp_color(outside), left_x, 178),
            ("INSIDE", label_font, GREEN, right_x, 145),
            (format_temp(inside), value_font, temp_color(inside), right_x, 178),
            ("FRONT ROOM", label_font, GREEN, left_x, 224),
            (format_temp(front_room), value_font, temp_color(front_room), left_x, 258),
            ("BEDROOM", label_font, GREEN, right_x, 224),
            (format_temp(bedroom), value_font, temp_color(bedroom), right_x, 258),
        ]
        self.build_particles()

    def build_particles(self) -> None:
        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for text, font, _color, x, y in self.layout:
            image = font.render(text, True, (255, 255, 255))
            mask.blit(image, image.get_rect(center=(x, y)))

        targets: List[Tuple[int, int]] = []
        for y in range(118, 298, 5):
            for x in range(8, WIDTH - 8, 5):
                if mask.get_at((x, y)).a > 35:
                    targets.append((x, y))

        if len(targets) > 600:
            targets = random.sample(targets, 600)

        for tx, ty in targets:
            if random.random() < 0.90:
                sx = tx + random.uniform(-26, 26)
                sy = random.uniform(-100, 112)
            elif random.random() < 0.5:
                sx = random.uniform(-40, -5)
                sy = random.uniform(105, HEIGHT)
            else:
                sx = random.uniform(WIDTH + 5, WIDTH + 40)
                sy = random.uniform(105, HEIGHT)

            self.particles.append(
                RevealGlyph(
                    sx=sx,
                    sy=sy,
                    tx=float(tx),
                    ty=float(ty),
                    glyph=random.choice(MATRIX_CHARS),
                    delay=random.uniform(0.0, 0.26),
                    fall=random.uniform(150, 285),
                    wobble=random.uniform(-12, 12),
                )
            )

    def draw_text(self, screen: pygame.Surface, alpha: int = 255) -> None:
        for text, font, color, x, y in self.layout:
            shadow = font.render(text, True, SHADOW)
            image = font.render(text, True, color)

            if alpha < 255:
                shadow.set_alpha(alpha)
                image.set_alpha(alpha)

            rect = image.get_rect(center=(x, y))
            screen.blit(shadow, rect.move(2, 2))
            screen.blit(image, rect)


class TunnelMatrixDashboard(BaseMatrixDashboard):
    """Continuous lighter rain while an arched tunnel frames all four temperatures."""

    def __init__(self) -> None:
        super().__init__()
        self.tunnel_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.reveal_rain_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.label_font = choose_cyber_font(17, bold=True)
        self.value_font = choose_cyber_font(31, bold=True)

    @staticmethod
    def _paint_arch(
        surface: pygame.Surface,
        left: int,
        top: int,
        width: int,
        arch_height: int,
        color: tuple[int, int, int, int],
    ) -> None:
        rect = pygame.Rect(left, top, width, arch_height)
        pygame.draw.ellipse(surface, color, rect)
        shoulder_y = top + arch_height // 2
        pygame.draw.rect(
            surface,
            color,
            pygame.Rect(left, shoulder_y, width, HEIGHT - shoulder_y),
        )

    def start_reveal(self) -> None:
        self.data.refresh()
        self.reveal = FourTempReveal(
            self.data.outside_f,
            self.data.inside_f,
            self.data.front_room_f,
            self.data.bedroom_f,
            self.label_font,
            self.value_font,
            self.glyph_font,
        )
        self.elapsed = 0.0

    def _tunnel_strength(self) -> float:
        reveal = self.reveal
        if reveal is None:
            return 0.0

        if reveal.phase == "form":
            return smoothstep(clamp(reveal.elapsed / (FORM_SECONDS * 0.72), 0.0, 1.0))

        if reveal.phase == "hold":
            return 1.0

        t = clamp(reveal.elapsed / MELT_SECONDS, 0.0, 1.0)
        return 1.0 - smoothstep(clamp((t - 0.22) / 0.78, 0.0, 1.0))

    def _draw_tunnel(self) -> None:
        strength = self._tunnel_strength()
        if strength <= 0.001:
            return

        base_alpha = int(160 * strength)
        self.tunnel_overlay.fill((0, 5, 2, base_alpha))

        outer_alpha = int(base_alpha * 0.54)
        middle_alpha = int(base_alpha * 0.24)

        self._paint_arch(
            self.tunnel_overlay,
            18,
            84,
            WIDTH - 36,
            196,
            (0, 12, 5, outer_alpha),
        )
        self._paint_arch(
            self.tunnel_overlay,
            25,
            91,
            WIDTH - 50,
            184,
            (0, 10, 4, middle_alpha),
        )
        self._paint_arch(
            self.tunnel_overlay,
            33,
            99,
            WIDTH - 66,
            170,
            (0, 0, 0, 0),
        )

        self.screen.blit(self.tunnel_overlay, (0, 0))

    def draw(self) -> None:
        self.screen.fill((0, 0, 0))

        if self.reveal:
            self.reveal_rain_layer.fill((0, 0, 0, 0))
            self.rain.draw(self.reveal_rain_layer, 0.40)
            self.reveal_rain_layer.set_alpha(142)
            self.screen.blit(self.reveal_rain_layer, (0, 0))
            self.reveal_rain_layer.set_alpha(255)

            self._draw_tunnel()
            self.reveal.draw(self.screen)
        else:
            self.rain.draw(self.screen, 0.56)

        self.clock.draw(self.screen)
        pygame.display.flip()


def main() -> int:
    try:
        TunnelMatrixDashboard().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Matrix tunnel dashboard failed: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
