# Matrix OS V9

A cinematic Raspberry Pi Matrix display built for a 480×320 screen.

## V9 display rotation

The clock stays large and centered at the top while the lower display rotates through three pages:

1. **ECOWITT** — Inside and Outside temperatures
2. **GOVEE** — Front Room and Bedroom temperatures
3. **XRP LIVE** — Live XRP/USD price

Only two temperatures are shown at once. Each page displays for 8 seconds by default.

## Controls

- `Space` or `Right Arrow`: next page
- `Left Arrow`: previous page
- `Esc`: exit

## Version history

The last complete Matrix OS V8 build is preserved in the repository branch:

```text
archive/matrix-os-v8
```

The `main` branch is now Matrix OS V9.

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

Change the page rotation time in `config.env`:

```bash
MATRIX_PAGE_SECONDS=8
```

## Automatic updates

`start_matrix.sh` checks GitHub for changes. When the Pi sees a newer commit on `main`, it pulls the update and restarts Matrix OS.
