"""Newest-frame-only threaded camera capture."""
from __future__ import annotations

import platform
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2

from config import AppConfig
from core.utils import setup_logging


@dataclass(frozen=True)
class FramePacket:
    """A camera frame with its capture timestamp."""

    frame: object
    timestamp: float
    sequence: int


class CameraCapture:
    """Capture camera frames on a worker thread without queueing stale frames."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize camera state from configuration."""
        self.config = config
        self.logger = setup_logging(config.log_level)
        self._capture: Optional[cv2.VideoCapture] = None
        self._latest: Optional[FramePacket] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sequence = 0

    def start(self) -> None:
        """Start the capture worker."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="CameraCapture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop capture and release the camera."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._release()

    def latest(self) -> Optional[FramePacket]:
        """Return the newest packet, or None when unavailable."""
        with self._lock:
            return self._latest

    def wait_ready(self, timeout: float = 3.0) -> bool:
        """Wait until the first successful camera open."""
        return self._ready.wait(timeout)

    def _open(self) -> bool:
        """Open the camera and request the configured format."""
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.config.camera_index, backend)
        if not capture.isOpened():
            capture.release()
            return False
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
        capture.set(cv2.CAP_PROP_FPS, self.config.camera_fps)
        self._capture = capture
        self.logger.info(
            "Camera negotiated %.0fx%.0f @ %.1f FPS backend=%s",
            capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            capture.get(cv2.CAP_PROP_FPS), backend,
        )
        self._ready.set()
        return True

    def _release(self) -> None:
        """Release the camera safely."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _run(self) -> None:
        """Run capture/reconnect loop."""
        while not self._stop.is_set():
            if self._capture is None and not self._open():
                self.logger.warning("Camera unavailable; retrying")
                self._stop.wait(1.0)
                continue
            ok, frame = self._capture.read() if self._capture is not None else (False, None)
            if not ok or frame is None:
                self.logger.warning("Camera read failed; reconnecting")
                self._release()
                continue
            packet = FramePacket(frame=frame, timestamp=time.perf_counter(), sequence=self._sequence)
            self._sequence += 1
            with self._lock:
                self._latest = packet


if __name__ == "__main__":
    camera = CameraCapture(AppConfig())
    camera.start()
    try:
        while True:
            packet = camera.latest()
            if packet:
                cv2.imshow("VirtualMouse camera", packet.frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
