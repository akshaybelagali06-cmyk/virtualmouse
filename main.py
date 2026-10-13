"""VirtualMouse entry point."""
from __future__ import annotations

import argparse
import multiprocessing
import threading
import time
from pathlib import Path

import cv2
import pyautogui
from pynput import keyboard

from config import ConfigManager
from core.camera import CameraCapture
from core.gesture_engine import GestureEngine, GestureEvent
from core.hand_tracker import HandTracker
from core.mouse_controller import MouseController
from core.profiler import Profiler
from core.smoothing import PointerSmoother
from core.utils import FpsCounter, setup_logging
from core.voice_controller import VoiceController
from ui.hud import Hud
from ui.settings_window import run_settings


class VirtualMouseApp:
    """Coordinate camera, tracking, gestures, voice, mouse, and HUD."""

    def __init__(self) -> None:
        """Create all runtime components."""
        self.config_manager = ConfigManager(Path(__file__).with_name("config.json"))
        config = self.config_manager.snapshot()
        self.logger = setup_logging(config.log_level)
        self.profiler = Profiler()
        self.camera = CameraCapture(config)
        self.tracker = HandTracker(config)
        self.mouse = MouseController(config)
        self.gestures = GestureEngine(config)
        self.smoother = PointerSmoother(config.smoothing_min_cutoff, config.smoothing_beta, config.dead_zone_px)
        self.hud = Hud(config)
        self.voice = VoiceController(config, self._voice_event)
        self.fps = FpsCounter()
        self.stop_event = threading.Event()
        self.control_enabled = True
        self._hotkey_listener: keyboard.GlobalHotKeys | None = None
        self._last_packet_sequence = -1

    def start(self) -> None:
        """Run the main vision loop until shutdown."""
        config = self.config_manager.snapshot()
        self.camera.start()
        self.mouse.start()
        self.voice.start()
        self._start_hotkey()
        if not self.camera.wait_ready(3.0):
            self.logger.error("No camera could be opened")
        try:
            while not self.stop_event.is_set():
                self.config_manager.reload_if_changed()
                config = self.config_manager.snapshot()
                packet = self.camera.latest()
                if packet is None or packet.sequence == self._last_packet_sequence:
                    time.sleep(0.001)
                    continue
                self._last_packet_sequence = packet.sequence
                frame_start = time.perf_counter()
                with self.profiler.timer("capture_age"):
                    capture_age = frame_start - packet.timestamp
                with self.profiler.timer("inference"):
                    result = self.tracker.process(packet.frame)
                landmarks = result.landmarks if result else None
                with self.profiler.timer("gesture"):
                    events = self.gestures.update(landmarks, frame_start)
                for event in events:
                    self._handle_event(event, frame_start)
                if self.control_enabled and config.gestures_enabled and landmarks is not None and self.gestures.state.value == "MOVE":
                    with self.profiler.timer("filter"):
                        x, y = self.smoother.filter(float(landmarks[8, 0]), float(landmarks[8, 1]), packet.timestamp, (self.mouse.monitor.width, self.mouse.monitor.height))
                    with self.profiler.timer("os_call"):
                        self.mouse.set_target(x, y)
                else:
                    self.smoother.reset()
                fps = self.fps.tick(frame_start)
                if config.preview_enabled and not config.headless:
                    display = cv2.flip(packet.frame, 1)
                    if landmarks is not None:
                        display_landmarks = landmarks.copy()
                    else:
                        display_landmarks = None
                    display = self.hud.draw(display, display_landmarks, self.gestures.state, fps, self.profiler, self.voice.status)
                    cv2.imshow(self.hud.window_name, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        self.stop_event.set()
                if fps and self.profiler.stats("inference").average_ms > config.latency_budget_ms and config.auto_reduce_resolution:
                    self.logger.warning("Inference average %.1f ms exceeds %.1f ms budget", self.profiler.stats("inference").average_ms, config.latency_budget_ms)
                del capture_age
        except KeyboardInterrupt:
            self.logger.info("Interrupted")
        finally:
            self.shutdown()

    def _handle_event(self, event: GestureEvent, timestamp: float) -> None:
        """Dispatch a gesture event without blocking the vision loop."""
        del timestamp
        if event.kind == "move":
            return
        if event.kind == "left_click":
            self.mouse.click("left")
        elif event.kind == "right_click":
            self.mouse.click("right")
        elif event.kind == "double_click":
            self.mouse.double_click()
        elif event.kind == "drag_start":
            self.mouse.press()
        elif event.kind in {"drag_end", "release", "pause"}:
            self.mouse.release()
        elif event.kind == "scroll":
            self.mouse.scroll(event.value)
        elif event.kind == "volume_up":
            self.voice.actions.volume("up")
        elif event.kind == "volume_down":
            self.voice.actions.volume("down")
        elif event.kind == "resume":
            return

    def _voice_event(self, command: str) -> None:
        """Dispatch a recognized voice command."""
        if command == "click":
            self.mouse.click("left")
        elif command == "right click":
            self.mouse.click("right")
        elif command == "double click":
            self.mouse.double_click()
        elif command == "scroll up":
            self.mouse.scroll(5)
        elif command == "scroll down":
            self.mouse.scroll(-5)
        elif command.startswith("open "):
            self.voice.actions.open_app(command[5:])
        elif command == "take screenshot":
            self.voice.actions.screenshot()
        elif command == "close window":
            self.voice.actions.close_window()
        elif command == "minimize all":
            self.voice.actions.minimize_all()
        elif command in {"volume up", "volume down", "mute"}:
            self.voice.actions.volume(command.replace("volume ", ""))
        elif command == "enable mouse":
            self.control_enabled = True
            self.mouse.set_enabled(True)
        elif command == "disable mouse":
            self.control_enabled = False
            self.mouse.set_enabled(False)
        elif command == "stop listening":
            self.voice._listening = False
        elif command == "start listening":
            self.voice._listening = True

    def _start_hotkey(self) -> None:
        """Install Ctrl+Alt+M as the global control toggle."""
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+m": self.toggle_control})
            self._hotkey_listener.start()
        except Exception:
            self.logger.exception("Global hotkey unavailable")

    def toggle_control(self) -> None:
        """Toggle gesture control and release drag state when disabled."""
        self.control_enabled = not self.control_enabled
        self.mouse.set_enabled(self.control_enabled)

    def shutdown(self) -> None:
        """Stop workers and release held input devices."""
        self.stop_event.set()
        try:
            self.mouse.release()
            self.mouse.stop()
            self.voice.stop()
            self.camera.stop()
            self.tracker.close()
            if self._hotkey_listener:
                self._hotkey_listener.stop()
            cv2.destroyAllWindows()
        except Exception:
            self.logger.exception("Shutdown encountered an error")


def main() -> None:
    """Parse command-line arguments and launch VirtualMouse."""
    parser = argparse.ArgumentParser(description="VirtualMouse gesture and offline voice controller")
    parser.add_argument("--settings", action="store_true", help="Open the separate settings window")
    parser.add_argument("--headless", action="store_true", help="Run without OpenCV preview")
    args = parser.parse_args()
    if args.settings:
        multiprocessing.freeze_support()
        run_settings()
        return
    app = VirtualMouseApp()
    if args.headless:
        app.config_manager.save({"headless": True, "preview_enabled": False})
    app.start()


if __name__ == "__main__":
    main()
