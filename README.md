# Matrix OS V8

A cinematic Raspberry Pi Matrix display for a 480×320 screen, with an ESP32-S3 screen used as a Pi-controlled sidecar.

## Architecture

The Raspberry Pi is the brain:

```text
GitHub -> Raspberry Pi -> USB serial -> ESP32-S3 -> sidecar screen
```

The ESP32 does not fetch weather, crypto, or miner data on its own. The Pi collects and decides what to show, then sends one compact JSON event at a time to the ESP32 over USB.

## Main Matrix display

- Matrix rain is the main visual
- Time stays centered at the top
- One large reveal appears at a time
- Outside temperature, Front Room, Bedroom, Wind, and XRP rotate
- Temperature reveals use heat/cold accent colors
- Wind bends the Matrix sideways
- Reveals tear open and collapse back into code
- Press `Space` to force the next reveal
- Press `Esc` to exit

## Install on the Pi

```bash
git clone https://github.com/shelleybrandon2019-eng/matrix-os-v8.git
cd matrix-os-v8
chmod +x install.sh start_matrix.sh
./install.sh
./start_matrix.sh
```

## ESP32 sidecar

Current detected hardware:

- ESP32-S3
- 16 MB flash
- 8 MB PSRAM
- USB Serial/JTAG

The Pi bridge is at `pi/sidecar_bridge.py`. The ESP32 PlatformIO project is in `esp32/`.

Install the Pi serial dependency:

```bash
python3 -m pip install pyserial
```

After the ESP32 firmware is flashed and connected to the Pi, test the link:

```bash
python3 pi/sidecar_bridge.py --port /dev/ttyACM0 --demo
```

Send one event manually:

```bash
python3 pi/sidecar_bridge.py \
  --port /dev/ttyACM0 \
  --kind weather \
  --title OUTSIDE \
  --value '90°F' \
  --accent red
```

Example USB message sent by the Pi:

```json
{"kind":"weather","title":"OUTSIDE","value":"90°F","accent":"red","duration_ms":8000}
```

The ESP32 receiver is working as a serial protocol foundation. The exact screen driver and pin mapping will be added after the display board model is confirmed.

## Optional live data

Copy the example config:

```bash
cp config.example.env config.env
nano config.env
```

Then add your Weather Underground API key and optional room sensor URLs.

## Update later

```bash
cd ~/matrix-os-v8
git pull
./start_matrix.sh
```

## Current status

Matrix OS V8 runs from the Pi. The new ESP32-S3 sidecar code keeps the Pi in control and uses USB as the first reliable connection method. XRP uses a public live-price endpoint. Weather and room temperatures fall back to demo values until their live feeds are configured.
