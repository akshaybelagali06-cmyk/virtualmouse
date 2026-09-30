"""Offline Vosk voice recognition and restricted command grammar."""
from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Optional


from config import AppConfig
from core.platform_actions import PlatformActions
from core.utils import setup_logging


COMMANDS = (
    "click", "right click", "double click", "scroll up", "scroll down",
    "open chrome", "open notepad", "open calculator", "take screenshot",
    "close window", "minimize all", "volume up", "volume down", "mute",
    "enable mouse", "disable mouse", "stop listening", "start listening",
)


def build_command_grammar(wake_word: str) -> list[str]:
    """Build the restricted recognition grammar including unknown speech."""
    prefix = wake_word.strip().lower()
    return [f"{prefix} {command}" for command in COMMANDS] + [f"{prefix} search", f"{prefix} type", "[unk]"]


class VoiceController:
    """Run offline speech recognition on a daemon thread."""

    def __init__(self, config: AppConfig, event_callback: Callable[[str], None]) -> None:
        """Initialize model, microphone state, and command callback."""
        self.config = config
        self.callback = event_callback
        self.logger = setup_logging(config.log_level)
        self.actions = PlatformActions()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._listening = True
        self._model: Optional[Model] = None
        self._dictation_until = 0.0
        self.status = "voice: starting"

    def start(self) -> None:
        """Start the voice worker if enabled and model exists."""
        if not self.config.voice_enabled:
            self.status = "voice: disabled"
            return
        model_path = Path(self.config.voice_model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[1] / model_path
        if not model_path.exists():
            self.status = f"voice: model missing ({model_path})"
            self.logger.warning(self.status)
            return
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            self._model = Model(str(model_path))
        except Exception:
            self.logger.exception("Unable to load Vosk model")
            self.status = "voice: model load failed"
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="Voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the voice worker."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        """Open the microphone and process small audio blocks."""
        if self._model is None:
            return
        grammar = json.dumps(build_command_grammar(self.config.wake_word))
        from vosk import KaldiRecognizer
        recognizer = KaldiRecognizer(self._model, self.config.voice_sample_rate, grammar)
        audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=8)

        def callback(indata: object, frames: int, callback_time: object, status: object) -> None:
            del frames, callback_time
            if status:
                self.logger.warning("Audio status: %s", status)
            try:
                audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

        try:
            import sounddevice as sd
            with sd.RawInputStream(
                samplerate=self.config.voice_sample_rate,
                blocksize=int(self.config.voice_sample_rate * self.config.voice_block_ms / 1000),
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                self.status = "voice: listening"
                while not self._stop.is_set():
                    try:
                        data = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result()).get("text", "").strip().lower()
                        if result:
                            self._handle_text(result)
        except Exception:
            self.logger.exception("Voice input failed")
            self.status = "voice: audio unavailable"

    def _handle_text(self, text: str) -> None:
        """Dispatch one recognized phrase without arbitrary shell execution."""
        wake = self.config.wake_word.strip().lower()
        if self.config.voice_mode == "wake_word" and not text.startswith(wake):
            return
        command = text[len(wake):].strip() if text.startswith(wake) else text
        if command.startswith("search "):
            self.actions.search(command[7:].strip())
            self.callback("search")
        elif command.startswith("type "):
            self._dictation_until = time.monotonic() + 5.0
            self.actions.type_text(command[5:].strip())
            self.callback("type")
        elif command in COMMANDS:
            self.callback(command)
