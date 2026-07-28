# Matrix OS V10 — Hub Cut ESP32 Clock

The Waveshare ESP32-S3 1.47-inch screen is a dedicated 320×172 landscape clock. It does not render normal Matrix rain.

## Display behavior

- Clean black background
- Giant four-digit clock with readable AM/PM and small seconds
- Random event every 20–60 seconds:
  - melt and reform
  - bullet time
  - Agent run
  - Agent scan
  - glitch/tear and relock
  - signal breach
- Every event returns immediately to the giant clock

## Hardware pins

- MOSI: GPIO45
- SCLK: GPIO40
- CS: GPIO42
- DC: GPIO41
- RST: GPIO39
- BL: GPIO48
- USB serial on the Pi: `/dev/ttyACM0`

## One-time firmware flash from the Pi

```bash
cd /home/b/matrix-os-v8
python3 -m pip install --user platformio
chmod +x flash_esp32_clock.sh
./flash_esp32_clock.sh
```

After flashing, `start_matrix.sh` launches `esp32_clock_bridge.py`. The bridge uses the Python standard library only and sends the Pi's local time to the ESP32 once per second.

## Test an effect manually

Stop Matrix OS or temporarily open the port with a serial terminal at 115200 baud, then send one of:

```text
EVENT|MELT
EVENT|BULLET
EVENT|AGENT
EVENT|SCAN
EVENT|GLITCH
EVENT|BREACH
```
