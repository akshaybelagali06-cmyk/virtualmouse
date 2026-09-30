"""Low-overhead rolling latency profiler and standalone benchmark."""
from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TimingStats:
    """Summary statistics for a timing series."""

    average_ms: float
    p95_ms: float
    count: int


class Profiler:
    """Collect bounded timing samples for named pipeline stages."""

    def __init__(self, max_samples: int = 600) -> None:
        """Initialize bounded stage sample storage."""
        self.samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=max_samples))

    def record(self, name: str, duration_seconds: float) -> None:
        """Record a duration in seconds."""
        self.samples[name].append(duration_seconds * 1000.0)

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        """Time a block and record its duration."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - start)

    def stats(self, name: str) -> TimingStats:
        """Return average and p95 timing statistics."""
        values = list(self.samples.get(name, ()))
        if not values:
            return TimingStats(0.0, 0.0, 0)
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
        return TimingStats(statistics.fmean(values), ordered[index], len(values))

    def report(self) -> dict[str, TimingStats]:
        """Return statistics for every recorded stage."""
        return {name: self.stats(name) for name in sorted(self.samples)}


if __name__ == "__main__":
    profiler = Profiler()
    for _ in range(100):
        with profiler.timer("demo"):
            time.sleep(0.001)
    for name, stats in profiler.report().items():
        print(f"{name}: avg={stats.average_ms:.3f} ms p95={stats.p95_ms:.3f} ms n={stats.count}")
