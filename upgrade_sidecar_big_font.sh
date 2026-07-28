#!/usr/bin/env bash
set -euo pipefail

PORT="${MATRIX_SIDECAR_SERIAL_PORT:-/dev/ttyACM0}"
BASE="/home/b/matrix-sidecar-usb"
FIRMWARE="$BASE/firmware"
VENV="/home/b/.venvs/matrix-sidecar"
SERVICE="matrix-sidecar-bridge.service"
SOURCE="$FIRMWARE/src/main.cpp"

if [[ ! -f "$SOURCE" ]]; then
  echo "ESP32 firmware source was not found at $SOURCE"
  echo "Run ./install_usb_sidecar.sh first."
  exit 1
fi

if [[ ! -e "$PORT" ]]; then
  echo "ESP32 is not present at $PORT"
  exit 1
fi

sudo systemctl stop "$SERVICE" 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path

path = Path('/home/b/matrix-sidecar-usb/firmware/src/main.cpp')
text = path.read_text(encoding='utf-8')

replacements = {
    'uint8_t size = value.length() >= 3 ? 8 : 10;':
        'uint8_t size = value.length() >= 3 ? 12 : 16;',
    'const int degreeSpace = 24;':
        'const int degreeSpace = 38;',
    'int degreeX = x + (int)w + 11;':
        'int degreeX = x + (int)w + 17;',
    'int degreeY = y + 10;':
        'int degreeY = y + 15;',
    'gfx->drawCircle(degreeX, degreeY, 8, matrixGreen(pulse));':
        'gfx->drawCircle(degreeX, degreeY, 13, matrixGreen(pulse));',
    'gfx->drawCircle(degreeX, degreeY, 7, gfx->color565(190, 255, 205));':
        'gfx->drawCircle(degreeX, degreeY, 11, gfx->color565(190, 255, 205));',
}

for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)

path.write_text(text, encoding='utf-8')
print('ESP32 temperature changed to full-screen cinematic size.')
PY

cd "$FIRMWARE"
"$VENV/bin/pio" run -t clean || true
"$VENV/bin/pio" run

if ! "$VENV/bin/pio" run -t upload; then
  sudo chmod 666 "$PORT" 2>/dev/null || true
  "$VENV/bin/pio" run -t upload
fi

for _ in $(seq 1 20); do
  [[ -e "$PORT" ]] && break
  sleep 1
done

sudo systemctl start "$SERVICE"
sleep 2

echo
echo "=================================================="
echo " BIG CINEMATIC ESP32 TEMPERATURE INSTALLED"
echo " Bridge status: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
echo "=================================================="
