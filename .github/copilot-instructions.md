# GitHub Copilot Instructions for Matrix OS

You are assisting with a Raspberry Pi appliance that renders a Matrix-style information screen.

Before changing code, read `AGENTS.md` and follow it as the primary project contract.

## User intent translation
- “Make the clock bigger” means adjust the clock font and placement in `main.py` while preventing clipping on 480x320.
- “Make everything bigger” means proportionally enlarge labels and values while keeping four readable quadrants.
- “Fix the temps” means inspect `live_data.py`, local `config.env` expectations, Govee BLE access, and Ecowitt parsing. Do not fake values.
- “Send it to the Pi” means commit the repository change; the Pi auto-updater pulls it.
- “Keep it running after PuTTY closes” means preserve the systemd service and launcher behavior.

## Never do these
- Never add XRP or other crypto data.
- Never create a new repository as a workaround.
- Never hard-code API keys or credentials.
- Never replace live temperatures with demo values.
- Never let a failed data call crash the display loop.
- Never redesign the display into a conventional boxed dashboard unless explicitly requested.

## Validation
For Python edits, run or ensure compatibility with:

```bash
python3 -m py_compile main.py matrix_engine.py live_data.py
```

For shell edits, use safe quoting, retain executable shebangs, and avoid commands that delete user data.
