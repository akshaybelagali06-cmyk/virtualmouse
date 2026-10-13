"""Configuration management for VirtualMouse."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 60
    processing_width: int = 320
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.5
    max_num_hands: int = 1
    model_complexity: int = 0
    smoothing_min_cutoff: float = 1.0
    smoothing_beta: float = 0.12
    dead_zone_px: float = 2.5
    active_margin_left: float = 0.08
    active_margin_right: float = 0.08
    active_margin_top: float = 0.08
    active_margin_bottom: float = 0.08
    monitor_index: int = 0
    pinch_close_ratio: float = 0.42
    pinch_open_ratio: float = 0.58
    click_hold_seconds: float = 0.35
    double_click_window: float = 0.40
    click_cooldown: float = 0.15
    gesture_stable_frames: int = 3
    pointer_history_seconds: float = 0.15
    tracking_hold_seconds: float = 0.15
    scroll_dead_zone: float = 0.035
    scroll_gain: float = 12.0
    volume_repeat_seconds: float = 0.30
    voice_enabled: bool = True
    gestures_enabled: bool = True
    preview_enabled: bool = True
    preview_max_fps: int = 30
    headless: bool = False
    wake_word: str = "computer"
    voice_mode: str = "wake_word"
    voice_sample_rate: int = 16000
    voice_block_ms: int = 100
    voice_model_path: str = "models/vosk-model-small-en-us-0.15"
    tts_enabled: bool = False
    log_level: str = "INFO"
    latency_budget_ms: float = 60.0
    auto_reduce_resolution: bool = True


class ConfigManager:
    """Owns a hot-reloadable immutable configuration snapshot."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the manager and load the initial configuration."""
        self.path = path or Path(__file__).with_name("config.json")
        self._lock = threading.RLock()
        self._snapshot = AppConfig()
        self._mtime_ns: int | None = None
        self.reload(force=True)

    def snapshot(self) -> AppConfig:
        """Return the current immutable configuration snapshot."""
        with self._lock:
            return self._snapshot

    def reload_if_changed(self) -> bool:
        """Reload configuration if its modification time changed."""
        return self.reload(force=False)

    def reload(self, force: bool = False) -> bool:
        """Load JSON overrides and atomically replace the snapshot."""
        try:
            mtime = self.path.stat().st_mtime_ns
        except FileNotFoundError:
            if force:
                self._write_default()
            return False
        if not force and mtime == self._mtime_ns:
            return False
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            valid = {field.name for field in fields(AppConfig)}
            values = {key: value for key, value in data.items() if key in valid}
            snapshot = AppConfig(**values)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return False
        with self._lock:
            self._snapshot = snapshot
            self._mtime_ns = mtime
        return True

    def save(self, overrides: dict[str, Any]) -> None:
        """Persist valid overrides atomically."""
        valid = {field.name for field in fields(AppConfig)}
        current = asdict(self.snapshot())
        current.update({key: value for key, value in overrides.items() if key in valid})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="config-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(current, handle, indent=2)
                handle.write("\n")
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        self.reload(force=True)

    def _write_default(self) -> None:
        """Create a default config file."""
        self.path.write_text(json.dumps(asdict(AppConfig()), indent=2) + "\n", encoding="utf-8")
        self._mtime_ns = self.path.stat().st_mtime_ns

    def maybe_reload(self, interval: float = 1.0) -> float:
        """Reload at most once per interval and return the next due time."""
        now = time.monotonic()
        self.reload_if_changed()
        return now + interval
