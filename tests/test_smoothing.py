from __future__ import annotations

import random

from core.smoothing import OneEuroFilter


def test_step_response_converges() -> None:
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.1)
    value = 0.0
    for index in range(120):
        value = filt.filter(1.0 if index >= 5 else 0.0, index / 120.0)
    assert value > 0.95


def test_jitter_is_reduced() -> None:
    random.seed(42)
    filt = OneEuroFilter(min_cutoff=1.2, beta=0.05)
    raw = []
    filtered = []
    for index in range(240):
        sample = 0.5 + random.uniform(-0.03, 0.03)
        raw.append(sample)
        filtered.append(filt.filter(sample, index / 120.0))
    raw_mean = sum(raw) / len(raw)
    filtered_mean = sum(filtered) / len(filtered)
    raw_spread = sum(abs(value - raw_mean) for value in raw) / len(raw)
    filtered_spread = sum(abs(value - filtered_mean) for value in filtered) / len(filtered)
    assert filtered_spread < raw_spread
