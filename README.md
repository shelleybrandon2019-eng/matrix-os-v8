# Matrix OS V9.4 — Cinematic Build

A cinematic Raspberry Pi Matrix display built for a 480×320 screen.

## V9.4 movie-quality pass

The `main` branch now includes:

- Three visual depths of Matrix rain: distant, middle, and foreground
- Cached glyph rendering for smoother performance on the Pi
- Bright foreground heads, bloom, and persistent motion trails
- Subtle green atmospheric haze, scanlines, edge vignette, and film flicker
- A light sweep and bloom pulse while temperatures or XRP form
- Hero drops that burn brighter and fall with longer tails
- A slower liquid melt back into the rain
- Lower, brighter temperature readings

The large clock remains fixed and readable above every effect.

## Display rotation

1. **ECOWITT** — Inside and Outside temperatures
2. **GOVEE** — Front Room and Bedroom temperatures
3. **XRP LIVE** — Live XRP/USD price

Only two temperatures appear at once. The complete collect, hold, and melt cycle lasts about 9 seconds by default.

## Controls

- `Space` or `Right Arrow`: melt the current page and move forward
- `Left Arrow`: melt the current page and move backward
- `Esc`: exit

## Version history

Previous builds are preserved as repository branches, including:

```text
archive/matrix-os-v8
archive/matrix-os-v9-static
archive/matrix-os-v9.1-first-test
archive/matrix-os-v9.2-drop-test
archive/matrix-os-v9.3
```

The `main` branch is Matrix OS V9.4 Cinematic.

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

Add the Ecowitt application key, API key, and device MAC. The two Govee sensors are read over Bluetooth using their configured MAC addresses.

XRP uses Coinbase first, then CoinGecko and Kraken as automatic fallbacks.

## Page timing

Change the complete page-cycle time in `config.env`:

```bash
MATRIX_PAGE_SECONDS=9
```

## Automatic updates

`start_matrix.sh` checks GitHub for changes. When the Pi sees a newer commit on `main`, it pulls the update and restarts Matrix OS.
