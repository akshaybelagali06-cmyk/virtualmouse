"""Pure hand-landmark gesture state machine.

States: PAUSED, MOVE, PINCH_PENDING, DRAGGING, SCROLL, LOST.
Transitions:
PAUSED -> MOVE on open/index gesture; PAUSED -> PAUSED on fist.
MOVE -> PINCH_PENDING on thumb-index close; MOVE -> SCROLL on index+middle.
PINCH_PENDING -> DRAGGING after click_hold_seconds; -> MOVE on release.
DRAGGING -> MOVE on pinch release; -> LOST on tracking timeout.
SCROLL -> MOVE when index+middle gesture ends.
Any active state -> LOST on tracking timeout; LOST -> MOVE after a stable hand returns.
Fist enters PAUSED and releases drag; open palm resumes from PAUSED.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from config import AppConfig
from core.utils import distance


class GestureState(str, Enum):
    """Finite-state-machine states."""

    PAUSED = "PAUSED"
    MOVE = "MOVE"
    PINCH_PENDING = "PINCH_PENDING"
    DRAGGING = "DRAGGING"
    SCROLL = "SCROLL"
    LOST = "LOST"


@dataclass(frozen=True)
class GestureEvent:
    """An output event consumed by the mouse controller or HUD."""

    kind: str
    x: float = 0.0
    y: float = 0.0
    value: float = 0.0


@dataclass(frozen=True)
class FingerFlags:
    """Extended-state flags for thumb and four fingers."""

    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool


class GestureEngine:
    """Convert landmarks into stable, scale-invariant gesture events."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize state and gesture timing."""
        self.config = config
        self.state = GestureState.LOST
        self._last_seen = 0.0
        self._stable_key: str | None = None
        self._stable_count = 0
        self._pinch_started = 0.0
        self._last_click = -math.inf
        self._last_left_pinch = -math.inf
        self._scroll_origin = 0.0
        self._volume_last = -math.inf
        self._pointer_history: deque[tuple[float, float, float]] = deque(maxlen=16)

    @staticmethod
    def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """Return angle ABC in degrees."""
        ba = a - b
        bc = c - b
        denom = float(np.linalg.norm(ba) * np.linalg.norm(bc))
        if denom <= 1e-9:
            return 180.0
        cosine = float(np.dot(ba, bc) / denom)
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    def _fingers(self, lm: np.ndarray) -> FingerFlags:
        """Classify extended fingers using joint angles and scale."""
        hand_size = max(distance(lm[0, :2], lm[9, :2]), 1e-6)
        angles = [
            self._angle(lm[5], lm[6], lm[8]),
            self._angle(lm[9], lm[10], lm[12]),
            self._angle(lm[13], lm[14], lm[16]),
            self._angle(lm[17], lm[18], lm[20]),
        ]
        finger = [angle > 155.0 for angle in angles]
        thumb_ratio = distance(lm[4, :2], lm[5, :2]) / hand_size
        return FingerFlags(thumb_ratio > 0.72, *finger)

    def _pinch_ratio(self, lm: np.ndarray, tip: int) -> float:
        """Return normalized thumb-to-tip distance."""
        hand_size = max(distance(lm[0, :2], lm[9, :2]), 1e-6)
        return distance(lm[4, :2], lm[tip, :2]) / hand_size

    def _stable(self, key: str) -> bool:
        """Return true when a discrete gesture has been stable enough."""
        if key == self._stable_key:
            self._stable_count += 1
        else:
            self._stable_key = key
            self._stable_count = 1
        return self._stable_count >= self.config.gesture_stable_frames

    def _pointer_before_pinch(self, now: float, fallback: tuple[float, float]) -> tuple[float, float]:
        """Use a pointer sample from roughly 150 ms earlier to prevent click drift."""
        target = fallback
        for timestamp, x, y in reversed(self._pointer_history):
            if now - timestamp >= self.config.pointer_history_seconds:
                return x, y
        return target

    def update(self, landmarks: Optional[np.ndarray], timestamp: float) -> list[GestureEvent]:
        """Advance the FSM and return zero or more gesture events."""
        if landmarks is None:
            if self._last_seen and timestamp - self._last_seen > self.config.tracking_hold_seconds:
                self.state = GestureState.LOST
                self._stable_key = None
                self._stable_count = 0
                return [GestureEvent("release")]
            return []
        self._last_seen = timestamp
        if landmarks.shape != (21, 3):
            return []
        x, y = float(landmarks[8, 0]), float(landmarks[8, 1])
        self._pointer_history.append((timestamp, x, y))
        flags = self._fingers(landmarks)
        pinch_index = self._pinch_ratio(landmarks, 8)
        pinch_middle = self._pinch_ratio(landmarks, 12)
        fist = not any((flags.index, flags.middle, flags.ring, flags.pinky)) and not flags.thumb
        open_palm = all((flags.thumb, flags.index, flags.middle, flags.ring, flags.pinky))
        scroll_pose = flags.index and flags.middle and not flags.ring and not flags.pinky
        thumb_extended = flags.thumb and not flags.index and not flags.middle and not flags.ring and not flags.pinky
        thumb_up = thumb_extended and float(landmarks[4, 1]) < float(landmarks[0, 1]) - 0.04
        thumb_down = thumb_extended and float(landmarks[4, 1]) > float(landmarks[0, 1]) + 0.04
        now = timestamp
        events: list[GestureEvent] = []

        if fist:
            if self.state != GestureState.PAUSED:
                self.state = GestureState.PAUSED
                events.append(GestureEvent("pause"))
            return events
        if self.state == GestureState.PAUSED:
            if open_palm and self._stable("open_palm"):
                self.state = GestureState.MOVE
                events.append(GestureEvent("resume"))
            return events
        if (thumb_up or thumb_down) and now - self._volume_last >= self.config.volume_repeat_seconds:
            self._volume_last = now
            events.append(GestureEvent("volume_up" if thumb_up else "volume_down"))
            return events
        if scroll_pose:
            if self.state != GestureState.SCROLL:
                self.state = GestureState.SCROLL
                self._scroll_origin = float(landmarks[9, 1])
            offset = float(landmarks[9, 1]) - self._scroll_origin
            if abs(offset) > self.config.scroll_dead_zone:
                events.append(GestureEvent("scroll", value=-offset * self.config.scroll_gain))
            return events
        if self.state == GestureState.SCROLL:
            self.state = GestureState.MOVE

        pinch_closed = pinch_index <= self.config.pinch_close_ratio
        pinch_open = pinch_index >= self.config.pinch_open_ratio
        right_closed = pinch_middle <= self.config.pinch_close_ratio
        if right_closed and not flags.index:
            if self._stable("right_pinch") and now - self._last_click >= self.config.click_cooldown:
                self._last_click = now
                events.append(GestureEvent("right_click", x, y))
            self.state = GestureState.MOVE
            return events
        if pinch_closed:
            if self.state != GestureState.PINCH_PENDING:
                self.state = GestureState.PINCH_PENDING
                self._pinch_started = now
                fx, fy = self._pointer_before_pinch(now, (x, y))
                events.append(GestureEvent("pinch_start", fx, fy))
            elif now - self._pinch_started >= self.config.click_hold_seconds and self.state != GestureState.DRAGGING:
                self.state = GestureState.DRAGGING
                events.append(GestureEvent("drag_start", x, y))
            return events
        if self.state in (GestureState.PINCH_PENDING, GestureState.DRAGGING) and pinch_open:
            held = now - self._pinch_started
            if self.state == GestureState.PINCH_PENDING and held < self.config.click_hold_seconds:
                if now - self._last_left_pinch <= self.config.double_click_window:
                    events.append(GestureEvent("double_click", x, y))
                elif now - self._last_click >= self.config.click_cooldown:
                    events.append(GestureEvent("left_click", x, y))
                self._last_click = now
                self._last_left_pinch = now
            elif self.state == GestureState.DRAGGING:
                events.append(GestureEvent("drag_end", x, y))
            self.state = GestureState.MOVE
            return events
        if flags.index and not flags.middle and not flags.ring and not flags.pinky:
            self.state = GestureState.MOVE
            events.append(GestureEvent("move", x, y))
        elif open_palm:
            self.state = GestureState.MOVE
        return events


if __name__ == "__main__":
    print("GestureEngine standalone demo: instantiate with AppConfig and feed (21,3) landmarks.")
