#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
SERVICE_PATH="/etc/systemd/system/matrix-os.service"

chmod +x "$ROOT/start_matrix.sh" "$ROOT/scripts/diagnostics.sh" "$ROOT/scripts/service_install.sh"

sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=Matrix OS Raspberry Pi Display
After=network-online.target bluetooth.target graphical.target
Wants=network-online.target bluetooth.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$ROOT
ExecStart=$ROOT/start_matrix.sh
Restart=always
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$USER_NAME/.Xauthority
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable matrix-os
sudo systemctl restart matrix-os

printf 'Matrix OS service installed and started.\n'
systemctl --no-pager --full status matrix-os | head -n 15
