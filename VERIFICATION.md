# Verification record

Target: CPython 3.12.x / Windows 10-11 x86-64.

## Completed in the build environment

- Python bytecode compilation: passed for the project tree.
- Pytest: **7 passed**.
- Smoothing: step response and jitter reduction tests passed.
- Gesture engine: move, pinch click, drag threshold, and tracking-loss release tests passed.
- Voice grammar: all command phrases and special `[unk]` grammar entries passed.

## Dependency installation limitation

A clean Windows CPython 3.12 installation could not be executed in the build environment because that environment does not provide Python 3.12 and outbound package-index access was unavailable. Therefore the pinned dependency file is a reviewed target environment, not a claim that a physical Windows installation was executed here.

MediaPipe 0.10.13 has a CPython 3.12 Windows x86-64 wheel according to its PyPI release metadata. The project uses that release because the application is written against `mp.solutions.hands`.

## Hardware-dependent verification to perform on the laptop

1. `py -3.12 -m venv .venv`
2. `.venv\Scripts\activate`
3. `python -m pip install -r requirements.txt`
4. `python -m pytest -q`
5. Download/extract the Vosk model under `models\vosk-model-small-en-us-0.15`.
6. `python main.py`
7. Check `logs\virtual_mouse.log` for negotiated camera resolution/FPS.
8. Check HUD average/p95 latency values while moving the index finger.
