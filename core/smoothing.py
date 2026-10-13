"""Time-based One Euro filtering and pointer jitter suppression."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class LowPassFilter:
    """First-order low-pass filter for a scalar signal."""

    value: float | None = None

    def apply(self, value: float, alpha: float) -> float:
        """Filter a scalar using a smoothing coefficient in [0, 1]."""
        if self.value is None:
            self.value = value
        else:
            self.value = alpha * value + (1.0 - alpha) * self.value
        return self.value


class OneEuroFilter:
    """Adaptive low-pass filter that trades rest stability for motion response.

    ``min_cutoff`` controls smoothing at low speed: lower values reduce jitter
    but add lag. ``beta`` increases the cutoff as raw input speed rises, so fast
    movements respond more quickly. Timestamps must be monotonic seconds.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.12,
        derivative_cutoff: float = 1.0,
    ) -> None:
        """Initialize filter parameters and empty history."""
        if min_cutoff <= 0 or beta < 0 or derivative_cutoff <= 0:
            raise ValueError("Cutoffs must be positive and beta must be non-negative.")
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.derivative_cutoff = float(derivative_cutoff)
        self._x = LowPassFilter()
        self._dx = LowPassFilter()
        self._last_timestamp: float | None = None
        self._last_raw_value: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        """Convert cutoff frequency and elapsed seconds to a filter alpha."""
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        """Clear signal, derivative, and timestamp history."""
        self._x = LowPassFilter()
        self._dx = LowPassFilter()
        self._last_timestamp = None
        self._last_raw_value = None

    def filter(self, value: float, timestamp: float) -> float:
        """Filter one sample using its real timestamp, not a nominal FPS."""
        value = float(value)
        timestamp = float(timestamp)
        if self._last_timestamp is None:
            self._last_timestamp = timestamp
            self._last_raw_value = value
            return self._x.apply(value, 1.0)

        dt = timestamp - self._last_timestamp
        if dt <= 0.0:
            # Duplicate/out-of-order timestamps should not destabilize alpha.
            dt = 1e-4
        raw_previous = self._last_raw_value if self._last_raw_value is not None else value
        raw_derivative = (value - raw_previous) / dt
        self._last_timestamp = timestamp
        self._last_raw_value = value

        derivative_alpha = self._alpha(self.derivative_cutoff, dt)
        derivative = self._dx.apply(raw_derivative, derivative_alpha)
        cutoff = self.min_cutoff + self.beta * abs(derivative)
        return self._x.apply(value, self._alpha(cutoff, dt))


class PointerSmoother:
    """Smooth normalized pointer coordinates and suppress tiny pixel changes."""

    def __init__(self, min_cutoff: float, beta: float, dead_zone_px: float) -> None:
        """Create independent X/Y filters and a pixel-space dead zone."""
        self.x = OneEuroFilter(min_cutoff, beta)
        self.y = OneEuroFilter(min_cutoff, beta)
        self.dead_zone_px = max(0.0, float(dead_zone_px))
        self._last_xy: tuple[float, float] | None = None

    def reset(self) -> None:
        """Reset both filters and the dead-zone anchor."""
        self.x.reset()
        self.y.reset()
        self._last_xy = None

    def filter(
        self,
        x: float,
        y: float,
        timestamp: float,
        pixels_per_norm: tuple[float, float],
    ) -> tuple[float, float]:
        """Return smoothed coordinates, ignoring sub-dead-zone cursor motion.

        The dead zone is measured in screen pixels, while returned coordinates
        remain normalized. Small changes accumulate against the last accepted
        output, preventing a permanent lock while filtering camera micro-jitter.
        """
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
