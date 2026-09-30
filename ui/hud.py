"""Lightweight OpenCV HUD."""
from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np

from config import AppConfig
from core.gesture_engine import GestureState
from core.profiler import Profiler


class Hud:
    """Render hand, active region, state, FPS, and latency information."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize HUD configuration."""
        self.config = config
        self.last_render = 0.0
        self.window_name = "VirtualMouse"

    def draw(self, frame: np.ndarray, landmarks: Optional[np.ndarray], state: GestureState, fps: float, profiler: Profiler, voice_status: str) -> np.ndarray:
        """Render an overlay and return the same frame buffer."""
        now = time.perf_counter()
        if now - self.last_render < 1.0 / max(1, self.config.preview_max_fps):
            return frame
        self.last_render = now
        height, width = frame.shape[:2]
        left = int(width * self.config.active_margin_left)
        right = int(width * (1 - self.config.active_margin_right))
        top = int(height * self.config.active_margin_top)
        bottom = int(height * (1 - self.config.active_margin_bottom))
        cv2.rectangle(frame, (left, top), (right, bottom), (80, 200, 255), 1)
        if landmarks is not None:
            points = [(int(p[0] * width), int(p[1] * height)) for p in landmarks]
            for start, end in ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)):
                cv2.line(frame, points[start], points[end], (120, 220, 120), 2)
            for point in points:
                cv2.circle(frame, point, 3, (240, 240, 240), -1)
        lines = [f"State: {state.value}", f"FPS: {fps:.1f}", f"Voice: {voice_status}"]
        for name in ("capture_age", "inference", "gesture", "filter", "os_call"):
            stats = profiler.stats(name)
            lines.append(f"{name}: {stats.average_ms:.1f} / {stats.p95_ms:.1f} ms")
        for index, line in enumerate(lines):
            cv2.putText(frame, line, (12, 24 + index * 21), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1, cv2.LINE_AA)
        return frame
