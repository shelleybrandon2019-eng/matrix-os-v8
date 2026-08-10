#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y python3-pygame python3-requests python3-bleak python3-dbus bluez git
sudo systemctl enable --now bluetooth.service || true

chmod +x start_matrix.sh

echo "Matrix OS V10 installed with Bluetooth/Govee support. Run ./start_matrix.sh"
