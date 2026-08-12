#!/usr/bin/env python3
"""Matrix OS tunnel reveal: continuous large rain and two-stage live temperature reveals."""
from __future__ import annotations

import random
import sys
from typing import Dict, List, Optional, Tuple

import pygame

from live_data import BEDROOM_MAC, FRONT_ROOM_MAC
from temp_scene_director import (
    FORM_SECONDS,
    GREEN,
    HEIGHT,
    MATRIX_CHARS,
    MELT_SECONDS,
    RAIN_SECONDS,
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


class PairTempReveal(DualNeoReveal):
    """Two large temperatures collect from code, hold cleanly, then melt into rain."""

    def __init__(
        self,
        left_label: str,
        left_value: Optional[float],
        right_label: str,
        right_value: Optional[float],
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
        label_y = 172
        value_y = 220

        self.layout = [
            (left_label, label_font, GREEN, left_x, label_y),
            (format_temp(left_value), value_font, temp_color(left_value), left_x, value_y),
            (right_label, label_font, GREEN, right_x, label_y),
            (format_temp(right_value), value_font, temp_color(right_value), right_x, value_y),
        ]
        self.build_particles()

    def build_particles(self) -> None:
        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        for text, font, _color, x, y in self.layout:
            image = font.render(text, True, (255, 255, 255))
            mask.blit(image, image.get_rect(center=(x, y)))

        targets: List[Tuple[int, int]] = []
        for y in range(138, 272, 5):
            for x in range(8, WIDTH - 8, 5):
                if mask.get_at((x, y)).a > 35:
                    targets.append((x, y))

        if len(targets) > 430:
            targets = random.sample(targets, 430)

        for tx, ty in targets:
            if random.random() < 0.90:
                sx = tx + random.uniform(-28, 28)
                sy = random.uniform(-100, 118)
            elif random.random() < 0.5:
                sx = random.uniform(-42, -5)
                sy = random.uniform(105, HEIGHT)
            else:
                sx = random.uniform(WIDTH + 5, WIDTH + 42)
                sy = random.uniform(105, HEIGHT)

            self.particles.append(
                RevealGlyph(
                    sx=sx,
                    sy=sy,
                    tx=float(tx),
                    ty=float(ty),
                    glyph=random.choice(MATRIX_CHARS),
                    delay=random.uniform(0.0, 0.26),
                    fall=random.uniform(155, 290),
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
    """Dozer-style sparse rain with an arched tunnel and two separate temp scenes."""

    def __init__(self) -> None:
        super().__init__()
        self.tunnel_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.reveal_rain_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.label_font = choose_cyber_font(21, bold=True)
        self.room_label_font = choose_cyber_font(18, bold=True)
        self.value_font = choose_cyber_font(39, bold=True)

        # 0 = normal rain, 1 = outside/inside, 2 = front room/bedroom.
        self.reveal_stage = 0

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

    def _weather_reveal(self) -> PairTempReveal:
        return PairTempReveal(
            "OUTSIDE",
            self.data.outside_f,
            "INSIDE",
            self.data.inside_f,
            self.label_font,
            self.value_font,
            self.glyph_font,
        )

    def _room_reveal(self) -> PairTempReveal:
        # The BLE worker stores fresh readings immediately in _ble_values. Pull those
        # cached values here so the second scene does not have to wait for the slower
        # 30-second general refresh cycle.
        try:
            with self.data._ble_lock:
                front = self.data._ble_values.get(FRONT_ROOM_MAC)
                bedroom = self.data._ble_values.get(BEDROOM_MAC)

            if front is not None:
                self.data.front_room_f = front
            if bedroom is not None:
                self.data.bedroom_f = bedroom
        except Exception:
            pass

        return PairTempReveal(
            "FRONT ROOM",
            self.data.front_room_f,
            "BEDROOM",
            self.data.bedroom_f,
            self.room_label_font,
            self.value_font,
            self.glyph_font,
        )

    def start_reveal(self) -> None:
        self.data.refresh()
        self.reveal_stage = 1
        self.reveal = self._weather_reveal()
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        self.data.refresh()

        # Rain is always alive, including both temperature scenes.
        energy = 0.48 if self.reveal else 0.54
        self.rain.update(dt, energy)
        self.elapsed += dt

        if self.reveal:
            self.reveal.update(dt)

            if self.reveal.finished:
                if self.reveal_stage == 1:
                    # The second temperature screen is explicit and unavoidable:
                    # FRONT ROOM + BEDROOM follows OUTSIDE + INSIDE every cycle.
                    self.reveal_stage = 2
                    self.reveal = self._room_reveal()
                    self.elapsed = 0.0
                else:
                    self.reveal = None
                    self.reveal_stage = 0
                    self.elapsed = 0.0

        elif self.elapsed >= RAIN_SECONDS:
            self.start_reveal()

    def _tunnel_strength(self) -> float:
        reveal = self.reveal
        if reveal is None:
            return 0.0

        if reveal.phase == "form":
            return smoothstep(
                clamp(reveal.elapsed / (FORM_SECONDS * 0.72), 0.0, 1.0)
            )

        if reveal.phase == "hold":
            return 1.0

        t = clamp(reveal.elapsed / MELT_SECONDS, 0.0, 1.0)
        return 1.0 - smoothstep(clamp((t - 0.22) / 0.78, 0.0, 1.0))

    def _draw_tunnel(self) -> None:
        strength = self._tunnel_strength()
        if strength <= 0.001:
            return

        base_alpha = int(150 * strength)
        self.tunnel_overlay.fill((0, 5, 2, base_alpha))

        outer_alpha = int(base_alpha * 0.52)
        middle_alpha = int(base_alpha * 0.22)

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
            # Same moving rain, only lighter while the temp text forms.
            self.reveal_rain_layer.fill((0, 0, 0, 0))
            self.rain.draw(self.reveal_rain_layer, 0.34)
            self.reveal_rain_layer.set_alpha(132)
            self.screen.blit(self.reveal_rain_layer, (0, 0))
            self.reveal_rain_layer.set_alpha(255)

            self._draw_tunnel()
            self.reveal.draw(self.screen)
        else:
            self.rain.draw(self.screen, 0.50)

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
