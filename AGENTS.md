# Matrix OS Agent Rules

This repository controls Brandon's Raspberry Pi Matrix display.

## Hardware and runtime
- Raspberry Pi running Raspberry Pi OS.
- Display resolution is exactly 480x320.
- Main program is `main.py`.
- The display runs as the `matrix-os` systemd service.
- `start_matrix.sh` watches GitHub and restarts after updates.
- The project must keep working after PuTTY/SSH closes.

## Visual requirements
- Preserve the Matrix rain background.
- Keep the clock large and centered at the top.
- Show exactly four temperature readings: FRONT ROOM, BEDROOM, INSIDE, OUTSIDE.
- Do not add XRP, crypto, stock prices, dashboards, boxes, panels, weather summaries, or unrelated widgets.
- Keep all content readable on 480x320 without clipping.
- Use Fahrenheit.

## Data sources
- FRONT ROOM Govee BLE MAC: `A4:C1:38:21:0C:F2`.
- BEDROOM Govee BLE MAC: `A4:C1:38:17:EC:09`.
- INSIDE and OUTSIDE come from Ecowitt.
- Never commit API keys, application keys, passwords, MAC secrets, or other private credentials.
- Secrets belong only in local `config.env`, which must remain ignored by git.

## Change rules
- Keep the same repository. Do not create a replacement repo.
- Make small, reversible changes.
- Run `python3 -m py_compile main.py matrix_engine.py live_data.py` before committing Python changes.
- Avoid adding new dependencies unless necessary.
- If a dependency is added, update the installer and README.
- Do not remove the automatic updater or systemd compatibility.
- Preserve graceful behavior when a sensor is offline; show `--°F` and keep the animation running.

## Preferred workflow
1. Read the existing implementation before editing.
2. Make the smallest change that satisfies the request.
3. Validate syntax.
4. Explain changed files and expected Pi behavior in the commit or pull request.
