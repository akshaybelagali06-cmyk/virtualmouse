"""Logging, FPS, geometry, and small runtime helpers."""
from __future__ import annotations

import logging
import math
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "virtual_mouse.log"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("virtual_mouse")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"))
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
        logger.addHandler(console)
    return logger


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a numeric value to an inclusive range."""
    return max(low, min(high, value))


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    """Return Euclidean distance between two points."""
    ax, ay = a
    bx, by = b
    return math.hypot(ax - bx, ay - by)


class FpsCounter:
    """Maintain a rolling frames-per-second estimate."""

    def __init__(self, window: int = 60) -> None:
        """Initialize the sample window."""
        self._times: deque[float] = deque(maxlen=window)

    def tick(self, timestamp: float | None = None) -> float:
        """Record a frame and return the current FPS."""
        now = timestamp if timestamp is not None else perf_counter()
        self._times.append(now)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0
