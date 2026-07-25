# Matrix OS V9.1 — Drop Collect/Melt Test

A cinematic Raspberry Pi Matrix display built for a 480×320 screen.

## V9.1 transition test

The Matrix rain never pauses. For every page change:

1. Falling Matrix glyphs pull together and form the next page.
2. The page locks into clean readable text.
3. The text breaks back into glyphs and melts downward off the screen.

The large clock stays fixed and readable above the effect.

## Display rotation

1. **ECOWITT** — Inside and Outside temperatures
2. **GOVEE** — Front Room and Bedroom temperatures
3. **XRP LIVE** — Live XRP/USD price

Only two temperatures are shown at once. The complete collect, hold, and melt cycle lasts about 8 seconds by default.

## Controls

- `Space` or `Right Arrow`: melt the current page and move forward
- `Left Arrow`: melt the current page and move backward
- `Esc`: exit

## Version history

The previous versions are preserved as repository branches:

```text
archive/matrix-os-v8
archive/matrix-os-v9-static
```

The `main` branch is the V9.1 animation test.

## Install on the Pi

```bash
git clone https://github.com/shelleybrandon2019-eng/matrix-os-v8.git
cd matrix-os-v8
chmod +x install.sh start_matrix.sh
./install.sh
./start_matrix.sh
```

## Live data configuration

Copy the example configuration:

```bash
cp config.example.env config.env
nano config.env
```

Add the Ecowitt application key, API key, and device MAC. The two Govee sensors are read over Bluetooth using their configured MAC addresses.

XRP uses Coinbase first, then CoinGecko and Kraken as automatic fallbacks.

## Page timing

Change the complete page-cycle time in `config.env`:

```bash
MATRIX_PAGE_SECONDS=8
```

## Automatic updates

`start_matrix.sh` checks GitHub for changes. When the Pi sees a newer commit on `main`, it pulls the update and restarts Matrix OS.
