"""Asynchronous mouse output with Windows cursor fast path."""
from __future__ import annotations

import ctypes
import platform
import queue
import threading
from dataclasses import dataclass
from typing import Optional

import pyautogui
from screeninfo import get_monitors

from config import AppConfig
from core.utils import clamp, setup_logging


@dataclass(frozen=True)
class MouseAction:
    """A queued discrete mouse action."""

    kind: str
    value: float = 0.0


class MouseController:
    """Serialize cursor targets and discrete actions on an output worker."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize platform cursor output and monitor geometry."""
        self.config = config
        self.logger = setup_logging(config.log_level)
        pyautogui.PAUSE = 0
        pyautogui.MINIMUM_DURATION = 0
        pyautogui.FAILSAFE = False
        self._target: Optional[tuple[int, int]] = None
        self._target_lock = threading.Lock()
        self._actions: queue.SimpleQueue[MouseAction] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._button_down = False
        self._enabled = True
        self._monitor = self._select_monitor()
        self._configure_dpi()

    def _select_monitor(self):
        """Return the configured monitor, falling back to the primary display."""
        monitors = get_monitors()
        index = max(0, min(self.config.monitor_index, len(monitors) - 1))
        return monitors[index]

    def _configure_dpi(self) -> None:
        """Enable per-process DPI awareness on Windows."""
        if platform.system() == "Windows":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except (AttributeError, OSError):
                    self.logger.exception("Unable to configure Windows DPI awareness")

    def start(self) -> None:
        """Start the mouse output worker."""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="MouseOutput", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop output and release any held mouse button."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)
        self.release()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable cursor control."""
        self._enabled = enabled
        if not enabled:
            self.release()

    def set_target(self, x_norm: float, y_norm: float) -> None:
        """Publish the newest normalized pointer target."""
        if not self._enabled:
            return
        left = self._monitor.x
        top = self._monitor.y
        width = self._monitor.width
        height = self._monitor.height
        x = clamp((x_norm - self.config.active_margin_left) / (1 - self.config.active_margin_left - self.config.active_margin_right), 0, 1)
        y = clamp((y_norm - self.config.active_margin_top) / (1 - self.config.active_margin_top - self.config.active_margin_bottom), 0, 1)
        target = (int(left + x * (width - 1)), int(top + y * (height - 1)))
        with self._target_lock:
            self._target = target

    def click(self, button: str = "left") -> None:
        """Queue a click."""
        self._actions.put(MouseAction("click", 1.0 if button == "left" else 2.0))

    def double_click(self) -> None:
        """Queue a double click."""
        self._actions.put(MouseAction("double_click"))

    def scroll(self, amount: float) -> None:
        """Queue a scroll operation."""
        self._actions.put(MouseAction("scroll", amount))

    def press(self) -> None:
        """Queue mouse-down."""
        self._actions.put(MouseAction("down"))

    def release(self) -> None:
        """Queue mouse-up or release immediately during shutdown."""
        self._actions.put(MouseAction("up"))

    def _move(self, target: tuple[int, int]) -> None:
        """Move cursor using the Windows fast path where available."""
        if platform.system() == "Windows":
            ctypes.windll.user32.SetCursorPos(target[0], target[1])
        else:
            pyautogui.moveTo(*target, _pause=False)

    def _run(self) -> None:
        """Drain the latest target and discrete action queue."""
        while not self._stop.is_set():
            with self._target_lock:
                target = self._target
                self._target = None
            if target is not None and self._enabled:
                try:
                    self._move(target)
                except Exception:
                    self.logger.exception("Cursor move failed")
            try:
                while True:
                    action = self._actions.get_nowait()
                    if action.kind == "click":
                        pyautogui.click(button="left" if action.value == 1.0 else "right")
                    elif action.kind == "double_click":
                        pyautogui.doubleClick()
                    elif action.kind == "scroll":
                        pyautogui.scroll(action.value)
                    elif action.kind == "down" and not self._button_down:
                        pyautogui.mouseDown()
                        self._button_down = True
                    elif action.kind == "up" and self._button_down:
                        pyautogui.mouseUp()
                        self._button_down = False
                    elif action.kind == "up":
                        pyautogui.mouseUp()
            except queue.Empty:
                pass

    @property
    def monitor(self):
        """Return the active monitor geometry."""
        return self._monitor

    @property
    def button_down(self) -> bool:
        """Return whether a drag button is currently held."""
        return self._button_down
