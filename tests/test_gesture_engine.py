from __future__ import annotations

import numpy as np

from config import AppConfig
from core.gesture_engine import GestureEngine, GestureState


def landmarks(index=True, middle=False, ring=False, pinky=False, thumb=False, pinch=False, thumb_middle_pinch=False):
    lm = np.zeros((21, 3), dtype=np.float32)
    lm[0] = (0.5, 0.65, 0)
    lm[9] = (0.5, 0.45, 0)
    tips = {8: (0.5, 0.15), 12: (0.62, 0.20), 16: (0.72, 0.45), 20: (0.80, 0.45)}
    pips = {6: (0.5, 0.25), 10: (0.62, 0.30), 14: (0.72, 0.40), 18: (0.80, 0.40)}
    for tip, pos in tips.items():
        lm[tip] = (*pos, 0)
    for pip, pos in pips.items():
        lm[pip] = (*pos, 0)
    lm[5] = (0.44, 0.45, 0)
    lm[13] = (0.66, 0.45, 0)
    lm[17] = (0.75, 0.48, 0)
    lm[4] = (0.38, 0.45, 0) if thumb else (0.48, 0.55, 0)
    if not index:
        lm[8] = (0.47, 0.40, 0)
        lm[6] = (0.47, 0.39, 0)
    if not middle:
        lm[12] = (0.62, 0.42, 0)
        lm[10] = (0.62, 0.41, 0)
    if not ring:
        lm[16] = (0.72, 0.42, 0)
        lm[14] = (0.72, 0.41, 0)
    if not pinky:
        lm[20] = (0.80, 0.42, 0)
        lm[18] = (0.80, 0.41, 0)
    if pinch:
        lm[4] = lm[8] + np.array([0.01, 0.0, 0.0])
    if thumb_middle_pinch:
        lm[4] = lm[12] + np.array([0.01, 0.0, 0.0])
    return lm


def test_index_only_emits_move() -> None:
    engine = GestureEngine(AppConfig(gesture_stable_frames=1))
    events = engine.update(landmarks(index=True), 1.0)
    assert any(event.kind == "move" for event in events)


def test_pinch_release_clicks_without_cursor_move_event() -> None:
    engine = GestureEngine(AppConfig(gesture_stable_frames=1))
    engine.update(landmarks(index=True), 1.0)
    start = engine.update(landmarks(index=True, pinch=True), 1.1)
    end = engine.update(landmarks(index=True), 1.2)
    assert any(event.kind == "pinch_start" for event in start)
    assert any(event.kind == "left_click" for event in end)
    assert not any(event.kind == "move" for event in end)


def test_held_pinch_enters_dragging() -> None:
    engine = GestureEngine(AppConfig(gesture_stable_frames=1, click_hold_seconds=0.35))
    engine.update(landmarks(index=True, pinch=True), 1.0)
    events = engine.update(landmarks(index=True, pinch=True), 1.36)
    assert any(event.kind == "drag_start" for event in events)
    assert engine.state == GestureState.DRAGGING


def test_tracking_loss_releases_after_timeout() -> None:
    engine = GestureEngine(AppConfig(gesture_stable_frames=1, tracking_hold_seconds=0.15))
    engine.update(landmarks(index=True), 1.0)
    events = engine.update(None, 1.20)
    assert any(event.kind == "release" for event in events)
    assert engine.state == GestureState.LOST
