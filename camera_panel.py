#!/usr/bin/env python3
"""Low-overhead Tapo RTSP camera panel for the Matrix display."""

from __future__ import annotations

import os
import threading
import time
from urllib.parse import quote

try:
    import cv2
except ImportError:
    cv2 = None

import pygame


class CameraPanel:
    """Continuously decode the Tapo substream without blocking Matrix animation."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.enabled = os.getenv("TAPO_CAMERA_ENABLED", "0") == "1"
        self.host = os.getenv("TAPO_CAMERA_HOST", "").strip()
        self.user = os.getenv("TAPO_CAMERA_USER", "").strip()
        self.password = os.getenv("TAPO_CAMERA_PASSWORD", "")
        self.stream = os.getenv("TAPO_CAMERA_STREAM", "stream2").strip() or "stream2"
        self.frame: bytes | None = None
        self.lock = threading.Lock()
        self.font = pygame.font.Font(None, 20)

        if self.enabled and cv2 is not None and self.host and self.user and self.password:
            threading.Thread(target=self._capture_loop, daemon=True).start()

    def _url(self) -> str:
        user = quote(self.user, safe="")
        password = quote(self.password, safe="")
        return f"rtsp://{user}:{password}@{self.host}:554/{self.stream}"

    def _fit_frame(self, frame):
        source_h, source_w = frame.shape[:2]
        target_ratio = self.width / self.height
        source_ratio = source_w / source_h

        if source_ratio > target_ratio:
            crop_w = max(1, int(source_h * target_ratio))
            left = max(0, (source_w - crop_w) // 2)
            frame = frame[:, left:left + crop_w]
        else:
            crop_h = max(1, int(source_w / target_ratio))
            top = max(0, (source_h - crop_h) // 2)
            frame = frame[top:top + crop_h, :]

        frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame.tobytes()

    def _capture_loop(self) -> None:
        while True:
            capture = cv2.VideoCapture(self._url(), cv2.CAP_FFMPEG)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            while capture.isOpened():
                ok, frame = capture.read()
                if not ok:
                    break
                packed = self._fit_frame(frame)
                with self.lock:
                    self.frame = packed

            capture.release()
            time.sleep(2.0)

    def draw(self, surface: pygame.Surface, x: int, y: int) -> None:
        with self.lock:
            packed = self.frame

        if packed is not None:
            image = pygame.image.frombuffer(packed, (self.width, self.height), "RGB")
            surface.blit(image, (x, y))
            return

        pygame.draw.rect(surface, (0, 8, 3), (x, y, self.width, self.height))
        message = "INSTALL CAMERA" if cv2 is None else ("CAMERA" if self.host else "SET CAMERA")
        image = self.font.render(message, True, (0, 255, 90))
        surface.blit(image, image.get_rect(center=(x + self.width // 2, y + self.height // 2)))
