"""MediaPipe Hands wrapper with a small processing image."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from config import AppConfig
from core.utils import setup_logging


@dataclass(frozen=True)
class HandResult:
    """Normalized hand landmarks and handedness confidence."""

    landmarks: np.ndarray
    handedness: str
    confidence: float


class HandTracker:
    """Run MediaPipe Hands inference on a mirrored, downscaled frame."""

    def __init__(self, config: AppConfig) -> None:
        """Create the legacy Hands solution available in MediaPipe 0.10.x."""
        self.config = config
        self.logger = setup_logging(config.log_level)
        if not hasattr(mp, "solutions"):
            raise RuntimeError("This build requires a MediaPipe release exposing mp.solutions.hands.")
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=config.max_num_hands,
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )

    def process(self, frame: np.ndarray) -> Optional[HandResult]:
        """Return one detected hand from a BGR frame, or None."""
        mirrored = cv2.flip(frame, 1)
        height, width = mirrored.shape[:2]
        target_width = min(self.config.processing_width, width)
        if target_width < width:
            scale = target_width / width
            resized = cv2.resize(mirrored, (target_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
        else:
            resized = mirrored
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        rgb.setflags(write=False)
        results = self._hands.process(rgb)
        if not results.multi_hand_landmarks:
            return None
        landmarks = np.array([(p.x, p.y, p.z) for p in results.multi_hand_landmarks[0].landmark], dtype=np.float32)
        label = "Unknown"
        confidence = 0.0
        if results.multi_handedness:
            classification = results.multi_handedness[0].classification[0]
            label = classification.label
            confidence = float(classification.score)
        return HandResult(landmarks, label, confidence)

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._hands.close()


if __name__ == "__main__":
    from core.camera import CameraCapture

    camera = CameraCapture(AppConfig())
    tracker = HandTracker(AppConfig())
    camera.start()
    try:
        while True:
            packet = camera.latest()
            if packet is not None:
                result = tracker.process(packet.frame)
                print("hand" if result else "no hand", end="\r")
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    finally:
        tracker.close()
        camera.stop()
