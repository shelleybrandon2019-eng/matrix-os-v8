# Matrix OS V10 — Hub Cut

A two-screen cinematic Raspberry Pi + ESP32 installation.

## The V10 direction

### Raspberry Pi: the main movie screen

The Pi remains the large 480×320 Matrix world and handles the major cinematic sequences:

- layered Matrix rain and atmospheric motion
- large readable clock
- rain collection and liquid transitions
- giant OUTSIDE and INSIDE reveals
- robot, Agent, lightning, scan, portal, bullet-time, and other short cutscenes
- live Ecowitt, Govee, weather, and XRP data

The Pi is the story screen. It should feel like a scene from the project’s Matrix-style video rather than a normal dashboard.

### ESP32-S3 1.47-inch: the giant side clock

The ESP32 is rotated clockwise in landscape and becomes a dedicated cinematic clock:

- the time is extremely large and fills the display
- no Matrix-rain background during the normal clock state
- clean black background with bright movie-style green/white digits
- AM/PM remains readable without shrinking the main numbers
- every 20–60 seconds, a random short interruption replaces the clock
- the clock reforms immediately after the interruption

Planned ESP32 interruptions:

1. **Melt** — digits liquefy, drip away, and reform
2. **Bullet time** — the clock freezes, stretches, slows, and snaps back
3. **Agent pass** — an Agent silhouette crosses or scans the display
4. **Glitch cut** — horizontal tearing, frame jump, and hard relock
5. **Signal breach** — a warning pulse or code intrusion briefly takes over

The ESP32 should not look like a tiny copy of the Pi. It is a large-glance clock with its own miniature movie moments.

## Screen roles

```text
Raspberry Pi = main cinematic Matrix world
ESP32        = giant clock + random movie interruptions
USB serial   = synchronization and future triggered events
GitHub       = source of truth and automatic deployment
```

## Current hardware

- Raspberry Pi main display: 480×320
- Waveshare ESP32-S3-LCD-1.47
- ESP32 physical panel: 172×320 ST7789
- ESP32 logical landscape canvas: 320×172
- ESP32 USB device on the Pi: `/dev/ttyACM0`

## Controls

- `Space` or `Right Arrow`: advance or trigger the next Pi scene
- `Left Arrow`: move backward
- `Esc`: exit

## Install on the Pi

```bash
git clone https://github.com/shelleybrandon2019-eng/matrix-os-v8.git
cd matrix-os-v8
chmod +x install.sh start_matrix.sh
./install.sh
./start_matrix.sh
```

## Live data configuration

```bash
cp config.example.env config.env
nano config.env
```

Add the Ecowitt application key, API key, and device MAC. Govee sensors are read over Bluetooth. XRP uses Coinbase first, then CoinGecko and Kraken as fallbacks.

## Automatic updates

`start_matrix.sh` checks GitHub for changes. When the Pi sees a newer commit on `main`, it pulls the update and restarts Matrix OS.

## Version history

Previous builds remain available through archive branches. The `main` branch is now the **Matrix OS V10 Hub Cut** direction.
