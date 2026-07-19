#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y python3-pygame python3-requests git

chmod +x start_matrix.sh

echo "Matrix OS V8 installed. Run ./start_matrix.sh"
