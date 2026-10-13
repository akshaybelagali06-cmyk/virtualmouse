from __future__ import annotations

import math
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


def test_higher_beta_tracks_fast_motion_more_responsively() -> None:
    slow = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    adaptive = OneEuroFilter(min_cutoff=1.0, beta=0.2)
    slow_values = []
    adaptive_values = []
    for index in range(40):
        timestamp = index / 60.0
        sample = 0.2 if index < 5 else min(0.2 + (index - 5) * 0.02, 0.9)
        slow_values.append(slow.filter(sample, timestamp))
        adaptive_values.append(adaptive.filter(sample, timestamp))
    assert adaptive_values[-1] > slow_values[-1]


def test_reset_reinitializes_filter_without_old_position_tail() -> None:
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.1)
    filt.filter(0.1, 0.0)
    filt.filter(0.9, 0.1)
    filt.reset()
    assert filt.filter(0.37, 5.0) == 0.37


def test_duplicate_timestamp_does_not_return_non_finite_value() -> None:
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.1)
    filt.filter(0.5, 1.0)
    result = filt.filter(0.51, 1.0)
    assert math.isfinite(result)
