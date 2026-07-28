#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PORT="${MATRIX_ESP32_PORT:-/dev/ttyACM0}"

pkill -f 'esp32_clock_bridge.py' 2>/dev/null || true
sleep 1

if command -v pio >/dev/null 2>&1; then
  PIO=pio
elif [[ -x "$HOME/.local/bin/pio" ]]; then
  PIO="$HOME/.local/bin/pio"
else
  echo "PlatformIO is not installed. Install it once with:"
  echo "  python3 -m pip install --user platformio"
  exit 1
fi

"$PIO" run --project-dir esp32_clock -t upload --upload-port "$PORT"
echo "ESP32 Hub Clock flashed on $PORT"
