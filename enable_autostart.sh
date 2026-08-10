#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/matrix-os-v8.desktop"
LOG_FILE="$HOME/matrix-autostart.log"

mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Matrix OS V8
Comment=Start Matrix OS automatically after the desktop session loads
Exec=/bin/bash -lc 'sleep 4; cd "$REPO_DIR" && rm -f /tmp/matrix-os-v8.lock && ./start_matrix.sh >> "$LOG_FILE" 2>&1'
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF

chmod 644 "$AUTOSTART_FILE"
chmod +x "$REPO_DIR/start_matrix.sh"

echo "Matrix OS autostart enabled: $AUTOSTART_FILE"
echo "It will start automatically after the graphical desktop loads."
