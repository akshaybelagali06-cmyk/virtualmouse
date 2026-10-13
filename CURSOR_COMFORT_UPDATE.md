# Cursor comfort update

Changes in this update:

- Corrected One Euro derivative estimation to use consecutive raw input samples rather than the previous filtered position.
- Kept filtering time-based and made duplicate/out-of-order timestamps safe.
- Tuned the default comfort profile to cutoff 1.0, beta 0.12, and a 2.5 px dead zone.
- Used each camera frame's capture timestamp for pointer filtering.
- Set `config.json` camera index to `1`, matching the working virtual webcam found by the user's diagnostic.
- Added regression tests for fast-motion response, reset behavior, and duplicate timestamps.

## Apply to an existing checkout

Extract the update ZIP separately first, then copy `core/smoothing.py`, `config.py`, `config.json`, `main.py`, `tests/test_smoothing.py`, and `README.md` into your existing `VirtualMouse` folder, allowing overwrite. Keep a backup of your current `config.json` if it has custom settings.

## Verify

```powershell
python -m pytest -q
python main.py
```

Move your hand slowly around a small target, hold it still, then move quickly across the frame. Compare the perceived jitter and lag. Change only one smoothing value between tests.
