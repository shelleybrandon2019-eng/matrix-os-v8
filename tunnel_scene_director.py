#!/usr/bin/env python3
"""Matrix OS tunnel reveal: continuous rain, arched tunnel, 24-hour clock, Neo temp melt."""
from __future__ import annotations

import sys

import pygame

from temp_scene_director import (
    FORM_SECONDS,
    HEIGHT,
    MELT_SECONDS,
    WIDTH,
    MatrixDashboard as BaseMatrixDashboard,
    clamp,
    smoothstep,
)


class TunnelMatrixDashboard(BaseMatrixDashboard):
    """Keep the Matrix rain alive while a dark arched tunnel frames the temp reveal."""

    def __init__(self) -> None:
        super().__init__()
        self.tunnel_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    @staticmethod
    def _paint_arch(
        surface: pygame.Surface,
        left: int,
        top: int,
        width: int,
        arch_height: int,
        color: tuple[int, int, int, int],
    ) -> None:
        """Paint a wide movie-style arched opening: curved roof with straight sides."""
        rect = pygame.Rect(left, top, width, arch_height)
        pygame.draw.ellipse(surface, color, rect)
        shoulder_y = top + arch_height // 2
        pygame.draw.rect(
            surface,
            color,
            pygame.Rect(left, shoulder_y, width, HEIGHT - shoulder_y),
        )

    def _tunnel_strength(self) -> float:
        reveal = self.reveal
        if reveal is None:
            return 0.0

        if reveal.phase == "form":
            # The walls fade in quickly while the temperature is assembling.
            return smoothstep(clamp(reveal.elapsed / (FORM_SECONDS * 0.72), 0.0, 1.0))

        if reveal.phase == "hold":
            return 1.0

        # Keep the tunnel around the first part of the melt, then dissolve it
        # back into full-screen rain as the falling temp glyphs become rain.
        t = clamp(reveal.elapsed / MELT_SECONDS, 0.0, 1.0)
        return 1.0 - smoothstep(clamp((t - 0.22) / 0.78, 0.0, 1.0))

    def _draw_tunnel(self) -> None:
        strength = self._tunnel_strength()
        if strength <= 0.001:
            return

        # Inspired by the wide tunnel opening in the reference: a low, broad arch,
        # dark ceiling/sides, and bright moving Matrix rain visible through the mouth.
        # The outer rain is only DIMMED, never stopped.
        base_alpha = int(178 * strength)
        self.tunnel_overlay.fill((0, 5, 2, base_alpha))

        # Three nested openings create a soft tunnel lip instead of a hard oval/box.
        # The innermost opening is fully clear so the rain keeps falling behind temps.
        outer_alpha = int(base_alpha * 0.58)
        middle_alpha = int(base_alpha * 0.28)

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
        # Full rain is always rendered first and always keeps moving.
        self.screen.fill((0, 0, 0))
        self.rain.draw(self.screen, 0.64 if self.reveal else 0.58)

        if self.reveal:
            # Dark tunnel walls frame a bright rain curtain. No flat panel and no
            # permanent background geometry when the temperatures are gone.
            self._draw_tunnel()
            self.reveal.draw(self.screen)

        # Keep the oversized 24-hour cyber clock above the scene at all times.
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
