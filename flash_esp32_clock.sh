#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PORT="${MATRIX_ESP32_PORT:-/dev/ttyACM0}"
TOOLS_DIR="${MATRIX_TOOLS_DIR:-$HOME/.local/share/matrix-os-v10}"
PIO_VENV="$TOOLS_DIR/platformio"

if [[ "${MATRIX_SKIP_BRIDGE_KILL:-0}" != "1" ]]; then
  pkill -f 'esp32_clock_bridge.py' 2>/dev/null || true
  sleep 1
fi

if command -v pio >/dev/null 2>&1; then
  PIO=pio
elif [[ -x "$HOME/.local/bin/pio" ]]; then
  PIO="$HOME/.local/bin/pio"
elif [[ -x "$PIO_VENV/bin/pio" ]]; then
  PIO="$PIO_VENV/bin/pio"
else
  mkdir -p "$TOOLS_DIR"
  if ! python3 -m venv "$PIO_VENV"; then
    echo "Python venv support is missing. Install it once with:"
    echo "  sudo apt install -y python3-venv"
    exit 1
  fi
  "$PIO_VENV/bin/python" -m pip install --upgrade pip platformio
  PIO="$PIO_VENV/bin/pio"
fi

"$PIO" run --project-dir esp32_clock -t upload --upload-port "$PORT"
echo "ESP32 Hub Clock flashed on $PORT"
echo "Restart Matrix OS so the USB clock bridge reconnects."
