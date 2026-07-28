#!/usr/bin/env bash
set -euo pipefail

PORT="${MATRIX_SIDECAR_SERIAL_PORT:-/dev/ttyACM0}"
BASE="/home/b/matrix-sidecar-usb"
VENV="/home/b/.venvs/matrix-sidecar"
FIRMWARE="$BASE/firmware"
SERVICE="matrix-sidecar-bridge.service"

echo
echo "=================================================="
echo " MATRIX OS V10 - USB ESP32 SIDECAR INSTALLER"
echo "=================================================="

if [[ ! -e "$PORT" ]]; then
  echo "ERROR: $PORT is not present. Plug the ESP32 into the Pi and retry."
  exit 1
fi

echo "ESP32 found at $PORT"
sudo systemctl stop "$SERVICE" 2>/dev/null || true

sudo apt-get update
sudo apt-get install -y python3-venv git acl

mkdir -p "$BASE" "$FIRMWARE/src" "$(dirname "$VENV")"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "platformio>=6.1,<7" pyserial

cat > "$FIRMWARE/platformio.ini" <<'PIO'
[env:matrix_sidecar]
platform = espressif32@7.0.1
board = esp32-s3-devkitc-1
framework = arduino

upload_port = /dev/ttyACM0
monitor_port = /dev/ttyACM0
monitor_speed = 115200
upload_speed = 460800

build_flags =
    -DARDUINO_USB_MODE=1
    -DARDUINO_USB_CDC_ON_BOOT=1

lib_deps =
    moononournation/GFX Library for Arduino@1.6.0
PIO

cat > "$FIRMWARE/src/main.cpp" <<'CPP'
#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <math.h>

// Waveshare ESP32-S3-LCD-1.47: physical panel 172x320.
// The board is used clockwise in landscape, giving a logical 320x172 canvas.
#define LCD_MOSI 45
#define LCD_SCLK 40
#define LCD_CS   42
#define LCD_DC   41
#define LCD_RST  39
#define LCD_BL   48

#define PANEL_W 172
#define PANEL_H 320
#define SCREEN_W 320
#define SCREEN_H 172

Arduino_DataBus *bus = new Arduino_ESP32SPI(
    LCD_DC, LCD_CS, LCD_SCLK, LCD_MOSI, GFX_NOT_DEFINED
);

Arduino_GFX *gfx = new Arduino_ST7789(
    bus, LCD_RST, 0, true, PANEL_W, PANEL_H, 34, 0, 34, 0
);

enum DisplayMode { MODE_RAIN, MODE_TEMP };
DisplayMode mode = MODE_RAIN;

// Do not call this type Stream: Arduino already owns that class name.
struct RainColumn {
  int16_t x;
  float y;
  float speed;
  uint8_t length;
};

constexpr int COLUMN_COUNT = 40;
RainColumn columns[COLUMN_COUNT];
int shownTemp = 0;
unsigned long autoRainAt = 0;
unsigned long lastFrame = 0;
String serialLine;

const char MATRIX_CHARS[] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+-<>[]{}";

uint16_t matrixGreen(int brightness) {
  brightness = constrain(brightness, 0, 255);
  return gfx->color565(0, brightness, brightness / 10);
}

void resetColumn(int i, bool anywhere = false) {
  columns[i].x = random(1, SCREEN_W - 7);
  columns[i].y = anywhere ? random(-SCREEN_H, SCREEN_H) : random(-100, -8);
  columns[i].speed = random(12, 38) / 10.0f;
  columns[i].length = random(4, 11);
}

void initRain() {
  randomSeed(esp_random());
  for (int i = 0; i < COLUMN_COUNT; ++i) resetColumn(i, true);
}

void drawRain() {
  gfx->fillScreen(BLACK);
  gfx->setTextSize(1);
  gfx->setTextWrap(false);

  for (int i = 0; i < COLUMN_COUNT; ++i) {
    RainColumn &column = columns[i];

    for (int tail = 0; tail < column.length; ++tail) {
      int y = (int)column.y - tail * 9;
      if (y < -8 || y >= SCREEN_H) continue;

      int divisor = max(1, (int)column.length);
      int brightness = 235 - tail * (190 / divisor);
      gfx->setTextColor(
          tail == 0
              ? gfx->color565(190, 255, 205)
              : matrixGreen(brightness)
      );

      char c = MATRIX_CHARS[random(0, sizeof(MATRIX_CHARS) - 1)];
      gfx->setCursor(column.x, y);
      gfx->write((uint8_t)c);
    }

    column.y += column.speed;
    if (column.y - column.length * 9 > SCREEN_H + 10) resetColumn(i);
  }
}

void drawTemperature() {
  gfx->fillScreen(BLACK);

  String value = String(shownTemp);
  uint8_t size = value.length() >= 3 ? 8 : 10;
  gfx->setTextSize(size);
  gfx->setTextWrap(false);

  int16_t x1, y1;
  uint16_t w, h;
  gfx->getTextBounds(value, 0, 0, &x1, &y1, &w, &h);

  const int degreeSpace = 24;
  int x = max(0, (SCREEN_W - (int)w - degreeSpace) / 2);
  int y = max(0, (SCREEN_H - (int)h) / 2 - 4);
  int pulse = 185 + (int)(70.0f * fabsf(sinf(millis() / 280.0f)));

  // Wide glow behind the digits.
  gfx->setTextColor(matrixGreen(40));
  for (int dx = -4; dx <= 4; dx += 2) {
    for (int dy = -4; dy <= 4; dy += 2) {
      gfx->setCursor(x + dx, y + dy);
      gfx->print(value);
    }
  }

  gfx->setTextColor(gfx->color565(190, 255, 205));
  gfx->setCursor(x, y);
  gfx->print(value);

  int degreeX = x + (int)w + 11;
  int degreeY = y + 10;
  gfx->drawCircle(degreeX, degreeY, 8, matrixGreen(pulse));
  gfx->drawCircle(degreeX, degreeY, 7, gfx->color565(190, 255, 205));
}

void setRain() {
  mode = MODE_RAIN;
  autoRainAt = 0;
  initRain();
}

void handleCommand(String line) {
  line.trim();
  if (!line.length()) return;

  if (line == "RAIN") {
    setRain();
    return;
  }

  if (line.startsWith("TEMP|")) {
    int divider = line.lastIndexOf('|');
    if (divider >= 0 && divider < (int)line.length() - 1) {
      shownTemp = line.substring(divider + 1).toInt();
      mode = MODE_TEMP;
      autoRainAt = millis() + 12000UL;
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(400);

  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);

  gfx->begin(40000000);
  gfx->setRotation(1);  // clockwise landscape
  gfx->fillScreen(BLACK);
  initRain();
  serialLine.reserve(96);
  Serial.println("MATRIX_SIDECAR_READY");
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLine.length()) {
        handleCommand(serialLine);
        serialLine = "";
      }
    } else if (serialLine.length() < 90) {
      serialLine += c;
    }
  }

  if (autoRainAt && (long)(millis() - autoRainAt) >= 0) setRain();

  if (millis() - lastFrame >= 34) {
    lastFrame = millis();
    if (mode == MODE_RAIN) drawRain();
    else drawTemperature();
  }

  delay(1);
}
CPP

cat > "$BASE/bridge.py" <<'PY'
#!/usr/bin/env python3
"""Bridge Matrix OS V10 state-file events to the ESP32 over USB serial."""

import json
import os
import time
from pathlib import Path

import serial

PORT = os.getenv("MATRIX_SIDECAR_SERIAL_PORT", "/dev/ttyACM0")
BAUD = int(os.getenv("MATRIX_SIDECAR_SERIAL_BAUD", "115200"))
STATE = Path(os.getenv("MATRIX_SIDECAR_STATE_FILE", "/tmp/matrix_sidecar_state.json"))


def open_serial():
    while True:
        try:
            link = serial.Serial()
            link.port = PORT
            link.baudrate = BAUD
            link.timeout = 0.2
            link.write_timeout = 1
            link.dtr = False
            link.rts = False
            link.open()
            time.sleep(2.0)
            link.reset_input_buffer()
            print(f"USB sidecar connected: {PORT} @ {BAUD}", flush=True)
            return link
        except (OSError, serial.SerialException) as exc:
            print(f"Waiting for {PORT}: {exc}", flush=True)
            time.sleep(1.5)


def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"mode": "rain", "event_id": -1}


def command_for(data):
    mode = str(data.get("mode", "rain")).lower()
    if mode == "temperature":
        value = data.get("temperature_f")
        if value is not None:
            source = str(data.get("source", "TEMP")).upper()
            return f"TEMP|{source}|{int(round(float(value)))}\n".encode()
    return b"RAIN\n"


def signature(data):
    return (
        data.get("event_id"),
        data.get("mode"),
        data.get("source"),
        data.get("temperature_f"),
    )


def main():
    link = None
    last_signature = None
    last_send = 0.0

    while True:
        try:
            if link is None or not link.is_open:
                link = open_serial()
                last_signature = None
                last_send = 0.0

            data = read_state()
            sig = signature(data)
            mode = str(data.get("mode", "rain")).lower()
            resend_after = 0.75 if mode == "temperature" else 3.0
            now = time.monotonic()

            if sig != last_signature or now - last_send >= resend_after:
                packet = command_for(data)
                link.write(packet)
                link.flush()
                last_signature = sig
                last_send = now
                print(packet.decode().strip(), flush=True)

            time.sleep(0.12)

        except (OSError, serial.SerialException) as exc:
            print(f"USB sidecar disconnected: {exc}", flush=True)
            try:
                if link is not None:
                    link.close()
            except Exception:
                pass
            link = None
            time.sleep(1.0)
        except Exception as exc:
            print(f"Bridge warning: {exc}", flush=True)
            time.sleep(0.5)


if __name__ == "__main__":
    main()
PY
chmod +x "$BASE/bridge.py"

cat > "/tmp/$SERVICE" <<'UNIT'
[Unit]
Description=Matrix OS USB ESP32 Sidecar Bridge
After=multi-user.target

[Service]
Type=simple
User=b
SupplementaryGroups=plugdev
Environment=PYTHONUNBUFFERED=1
Environment=MATRIX_SIDECAR_SERIAL_PORT=/dev/ttyACM0
Environment=MATRIX_SIDECAR_STATE_FILE=/tmp/matrix_sidecar_state.json
ExecStart=/home/b/.venvs/matrix-sidecar/bin/python /home/b/matrix-sidecar-usb/bridge.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
sudo install -m 0644 "/tmp/$SERVICE" "/etc/systemd/system/$SERVICE"

cat > /tmp/99-matrix-esp32.rules <<'RULE'
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", MODE="0660", GROUP="plugdev"
RULE
sudo install -m 0644 /tmp/99-matrix-esp32.rules /etc/udev/rules.d/99-matrix-esp32.rules
sudo usermod -aG plugdev b
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo setfacl -m u:b:rw "$PORT" 2>/dev/null || true

cd "$FIRMWARE"
echo
echo "Building corrected ESP32 firmware..."
"$VENV/bin/pio" run -t clean || true
"$VENV/bin/pio" run

echo
echo "Uploading ESP32 firmware to $PORT..."
if ! "$VENV/bin/pio" run -t upload; then
  echo "Normal upload could not open the port; retrying with elevated port access..."
  sudo chmod 666 "$PORT" 2>/dev/null || true
  "$VENV/bin/pio" run -t upload
fi

for _ in $(seq 1 25); do
  [[ -e "$PORT" ]] && break
  sleep 1
done

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE"
sleep 2

echo
echo "=================================================="
echo " USB SIDECAR INSTALLED"
echo " Pi state file : /tmp/matrix_sidecar_state.json"
echo " ESP32 port    : $PORT"
echo " Bridge status : $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
echo "=================================================="
echo
echo "The ESP32 now runs landscape Matrix rain. During an OUTSIDE or INSIDE"
echo "Pi reveal, it shows only the matching temperature, then returns to rain."
