# Matrix OS V8

A cinematic Raspberry Pi Matrix display for a 480×320 screen.

## What it does

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

Because this repository is private, GitHub may ask you to sign in or use a personal access token when cloning it onto the Pi.

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

This is the first GitHub version of Matrix OS V8. XRP uses a public live-price endpoint. Weather and room temperatures fall back to demo values until their live feeds are configured.
