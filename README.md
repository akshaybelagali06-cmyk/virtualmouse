# VirtualMouse

VirtualMouse is a Windows-first desktop application that combines webcam hand gestures with fully offline voice commands to control the mouse.

## Tested Python target

**CPython 3.12.x, Windows 10/11 x86-64.** The dependency set is pinned for that target. MediaPipe 0.10.13 provides a CPython 3.12 Windows wheel and retains the `mp.solutions.hands` API used here. citeturn0search7

## Features

- Newest-frame-only camera capture with automatic reconnect.
- 640x480 MJPG / 60 FPS camera request on Windows.
- MediaPipe Hands at a small processing resolution.
- Time-based One Euro pointer smoothing.
- Asynchronous cursor output; the vision loop does not wait for mouse I/O.
- Gesture FSM with pinch hysteresis, click/drag/double-click, right-click, scroll, pause/resume and volume gestures.
- Offline Vosk command recognition with a restricted grammar.
- Windows/macOS/Linux platform actions isolated in `core/platform_actions.py`.
- OpenCV HUD with FPS and rolling average/p95 stage timings.
- Hot-reloadable `config.json` and a separate Tkinter settings process.
- Pytest regression tests for smoothing, gesture logic and voice grammar.

## Installation on Windows

1. Install Python 3.12 x64.
2. Extract this project.
3. Open Command Prompt in the `VirtualMouse` folder.
4. Create a virtual environment:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

5. Download and extract the Vosk model `vosk-model-small-en-us-0.15` into:

```text
VirtualMouse\models\vosk-model-small-en-us-0.15
```

6. Run tests:

```bat
python -m pytest -q
```

7. Start VirtualMouse:

```bat
python main.py
```

## Controls

- `Ctrl+Alt+M`: toggle gesture mouse control.
- `Esc` or `q`: quit the preview window.
- `python main.py --settings`: open the live settings editor.
- `python main.py --headless`: run without the OpenCV preview.

## Gesture map

| Gesture | Action |
|---|---|
| Index only | Move cursor |
| Thumb + index pinch, release quickly | Left click |
| Thumb + index pinch held | Drag |
| Two quick left pinches | Double click |
| Thumb + middle pinch | Right click |
| Index + middle up | Scroll |
| Fist | Pause and release drag |
| Open palm | Resume |
| Thumb up/down | Volume up/down while held |

## Voice commands

In the default wake-word mode, prefix commands with `computer`:

- `computer click`
- `computer right click`
- `computer double click`
- `computer scroll up`
- `computer scroll down`
- `computer open chrome`
- `computer open notepad`
- `computer open calculator`
- `computer search <query>`
- `computer type <text>`
- `computer take screenshot`
- `computer close window`
- `computer minimize all`
- `computer volume up`
- `computer volume down`
- `computer mute`
- `computer enable mouse`
- `computer disable mouse`
- `computer stop listening`
- `computer start listening`

The application never executes arbitrary shell text from voice input.

## Performance tuning

The target is 30+ sustained vision FPS and a 60 ms software frame-read-to-cursor budget. The HUD reports rolling average and p95 timings for capture age, inference, gesture processing, smoothing, and OS output.

`config.json` is checked for changes about once per second. Lower `smoothing_min_cutoff` for a steadier pointer at rest. Increase `smoothing_beta` to reduce lag during fast movement. Keep smoothing modest because heavy smoothing adds latency.

## Troubleshooting

### Camera does not open

Check Windows camera permissions and change `camera_index` in `config.json`. The log is `logs/virtual_mouse.log`.

### Vosk says model missing

Extract the model folder exactly under `models/vosk-model-small-en-us-0.15`, or change `voice_model_path` in `config.json`.

### Cursor coordinates are wrong on a scaled display

The Windows DPI-awareness setup runs during mouse-controller initialization. Restart the app after changing Windows display scaling.

### Microphone is unavailable

Check Windows microphone permissions and the PortAudio device list. Voice failure is logged and does not crash the vision pipeline.

### MediaPipe import/API problem

Use the pinned environment from `requirements.txt` with Python 3.12. The project intentionally uses MediaPipe 0.10.13 because that release has a CPython 3.12 Windows wheel and the legacy Hands API. citeturn0search7

## Project structure

```text
VirtualMouse/
  main.py
  config.py
  config.json
  requirements.txt
  README.md
  core/
    __init__.py
    camera.py
    hand_tracker.py
    gesture_engine.py
    smoothing.py
    mouse_controller.py
    voice_controller.py
    platform_actions.py
    profiler.py
    utils.py
  ui/
    __init__.py
    hud.py
    settings_window.py
  tests/
    test_smoothing.py
    test_gesture_engine.py
    test_voice_grammar.py
  logs/.gitkeep
  screenshots/.gitkeep
```

## Safety

VirtualMouse can move the real cursor and send clicks/keyboard shortcuts. Test gestures with non-destructive applications first. The global `Ctrl+Alt+M` toggle is the primary emergency pause for gesture control; `Esc`/`q` closes the preview application.
