"""Time-based One Euro filter for low-latency pointer smoothing."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class LowPassFilter:
    """First-order low-pass filter."""

    value: float | None = None

    def apply(self, value: float, alpha: float) -> float:
        """Filter a scalar using the supplied smoothing coefficient."""
        if self.value is None:
            self.value = value
        else:
            self.value = alpha * value + (1.0 - alpha) * self.value
        return self.value


class OneEuroFilter:
    """Adaptive low-pass filter that reduces jitter without fixed-FPS lag."""

    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.08, derivative_cutoff: float = 1.0) -> None:
        """Initialize filter parameters."""
        if min_cutoff <= 0 or beta < 0 or derivative_cutoff <= 0:
            raise ValueError("Filter parameters must be positive, except beta which may be zero.")
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.derivative_cutoff = derivative_cutoff
        self._x = LowPassFilter()
        self._dx = LowPassFilter()
        self._last_timestamp: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        """Convert a cutoff frequency and dt to a smoothing coefficient."""
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        """Clear filter history."""
        self._x = LowPassFilter()
        self._dx = LowPassFilter()
        self._last_timestamp = None

    def filter(self, value: float, timestamp: float) -> float:
        """Filter a value using real elapsed time between samples."""
        if self._last_timestamp is None:
            self._last_timestamp = timestamp
            return self._x.apply(value, 1.0)
        dt = max(1e-5, timestamp - self._last_timestamp)
        self._last_timestamp = timestamp
        previous = self._x.value if self._x.value is not None else value
        derivative = (value - previous) / dt
        derivative = self._dx.apply(derivative, self._alpha(self.derivative_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(derivative)
        return self._x.apply(value, self._alpha(cutoff, dt))


class PointerSmoother:
    """Apply independent One Euro filters to normalized X/Y coordinates."""

    def __init__(self, min_cutoff: float, beta: float, dead_zone_px: float) -> None:
        """Initialize pointer filters."""
        self.x = OneEuroFilter(min_cutoff, beta)
        self.y = OneEuroFilter(min_cutoff, beta)
        self.dead_zone_px = max(0.0, dead_zone_px)
        self._last_xy: tuple[float, float] | None = None

    def reset(self) -> None:
        """Reset both axes and dead-zone state."""
        self.x.reset()
        self.y.reset()
        self._last_xy = None

    def filter(self, x: float, y: float, timestamp: float, pixels_per_norm: tuple[float, float]) -> tuple[float, float]:
        """Return smoothed coordinates with a small pixel dead zone."""
        filtered = (self.x.filter(x, timestamp), self.y.filter(y, timestamp))
        if self._last_xy is None:
            self._last_xy = filtered
            return filtered
        dx = (filtered[0] - self._last_xy[0]) * pixels_per_norm[0]
        dy = (filtered[1] - self._last_xy[1]) * pixels_per_norm[1]
        if math.hypot(dx, dy) < self.dead_zone_px:
            return self._last_xy
        self._last_xy = filtered
        return filtered
