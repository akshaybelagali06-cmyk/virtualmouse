"""Separate-process Tkinter configuration editor."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from config import AppConfig, ConfigManager


class SettingsWindow:
    """Edit common live-reloadable VirtualMouse settings."""

    def __init__(self, manager: ConfigManager) -> None:
        """Create the settings form."""
        self.manager = manager
        self.root = tk.Tk()
        self.root.title("VirtualMouse Settings")
        self.vars: dict[str, tk.StringVar] = {}
        fields = ("smoothing_min_cutoff", "smoothing_beta", "pinch_close_ratio", "pinch_open_ratio", "active_margin_left", "active_margin_right", "active_margin_top", "active_margin_bottom", "camera_index", "wake_word", "voice_enabled", "gestures_enabled", "preview_enabled")
        values = vars(self.manager.snapshot())
        for row, name in enumerate(fields):
            tk.Label(self.root, text=name).grid(row=row, column=0, padx=8, pady=4, sticky="w")
            var = tk.StringVar(value=str(values[name]))
            self.vars[name] = var
            tk.Entry(self.root, textvariable=var, width=30).grid(row=row, column=1, padx=8, pady=4)
        tk.Button(self.root, text="Save", command=self.save).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def save(self) -> None:
        """Validate and save edited settings."""
        try:
            current = vars(self.manager.snapshot())
            overrides: dict[str, object] = {}
            float_fields = {"smoothing_min_cutoff", "smoothing_beta", "pinch_close_ratio", "pinch_open_ratio", "active_margin_left", "active_margin_right", "active_margin_top", "active_margin_bottom"}
            int_fields = {"camera_index"}
            bool_fields = {"voice_enabled", "gestures_enabled", "preview_enabled"}
            for name, var in self.vars.items():
                if name in float_fields:
                    overrides[name] = float(var.get())
                elif name in int_fields:
                    overrides[name] = int(var.get())
                elif name in bool_fields:
                    overrides[name] = var.get().lower() in {"true", "1", "yes", "on"}
                else:
                    overrides[name] = var.get()
            self.manager.save(overrides)
            messagebox.showinfo("Saved", "Settings saved. The running app will hot-reload them.")
        except (TypeError, ValueError, OSError) as exc:
            messagebox.showerror("Invalid settings", str(exc))

    def run(self) -> None:
        """Run the Tk event loop."""
        self.root.mainloop()


def run_settings() -> None:
    """Launch settings using the project config file."""
    SettingsWindow(ConfigManager(Path(__file__).resolve().parents[1] / "config.json")).run()
