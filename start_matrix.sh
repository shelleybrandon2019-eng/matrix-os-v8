#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f config.env ]]; then
  set -a
  source config.env
  set +a
fi

exec /usr/bin/python3 v8_matrix.py
