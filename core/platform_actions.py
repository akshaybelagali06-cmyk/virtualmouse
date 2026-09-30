"""Operating-system-specific actions used by voice commands."""
from __future__ import annotations

import os
import platform
import subprocess
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path


from core.utils import PROJECT_ROOT, setup_logging


class PlatformActions:
    """Provide safe, small OS action wrappers for the voice controller."""

    def __init__(self) -> None:
        """Initialize logging."""
        self.logger = setup_logging()
        self.screenshot_dir = PROJECT_ROOT / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def open_app(self, name: str) -> bool:
        """Open a supported application by friendly name."""
        try:
            system = platform.system()
            if system == "Windows":
                commands = {
                    "chrome": ["cmd", "/c", "start", "", "chrome"],
                    "notepad": ["notepad.exe"],
                    "calculator": ["calc.exe"],
                }
            elif system == "Darwin":
                commands = {key: ["open", "-a", value] for key, value in {"chrome": "Google Chrome", "notepad": "TextEdit", "calculator": "Calculator"}.items()}
            else:
                commands = {"chrome": ["google-chrome"], "notepad": ["gedit"], "calculator": ["gnome-calculator"]}
            command = commands.get(name.lower())
            if command is None:
                return False
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            self.logger.exception("Could not open app %s", name)
            return False

    def search(self, query: str) -> None:
        """Open a Google search URL."""
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        webbrowser.open(url)

    def screenshot(self) -> Path | None:
        """Save a timestamped desktop screenshot."""
        try:
            import pyautogui
            path = self.screenshot_dir / f"screenshot_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
            pyautogui.screenshot().save(path)
            return path
        except Exception:
            self.logger.exception("Screenshot failed")
            return None

    def close_window(self) -> None:
        """Close the foreground window using the platform shortcut."""
        import pyautogui
        if platform.system() == "Windows":
            pyautogui.hotkey("alt", "f4")
        elif platform.system() == "Darwin":
            pyautogui.hotkey("command", "w")
        else:
            pyautogui.hotkey("alt", "f4")

    def minimize_all(self) -> None:
        """Minimize or show the desktop."""
        import pyautogui
        if platform.system() == "Windows":
            pyautogui.hotkey("win", "d")
        else:
            pyautogui.hotkey("alt", "f10")

    def volume(self, direction: str) -> None:
        """Change or mute system volume using platform shortcuts."""
        key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}.get(direction)
        if key:
            import pyautogui
            pyautogui.press(key)

    def type_text(self, text: str) -> None:
        """Type text into the focused application."""
        import pyautogui
        pyautogui.write(text, interval=0)
