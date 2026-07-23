#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ok() { printf '✓ %s\n' "$1"; }
warn() { printf '! %s\n' "$1"; }
fail() { printf '✗ %s\n' "$1"; }

printf 'Matrix OS Diagnostics\n'
printf '=====================\n'
printf 'Time: %s\n\n' "$(date)"

if command -v python3 >/dev/null 2>&1; then ok "Python: $(python3 --version 2>&1)"; else fail "Python missing"; fi
if python3 -c 'import pygame' >/dev/null 2>&1; then ok "pygame installed"; else fail "pygame missing"; fi
if python3 -c 'import requests' >/dev/null 2>&1; then ok "requests installed"; else warn "requests missing"; fi

if command -v bluetoothctl >/dev/null 2>&1; then
  ok "Bluetooth tools installed"
  bluetoothctl show 2>/dev/null | grep -q 'Powered: yes' && ok "Bluetooth powered on" || warn "Bluetooth is not powered on or unavailable"
else
  fail "bluetoothctl missing"
fi

if ping -c 1 -W 2 github.com >/dev/null 2>&1; then ok "Internet/GitHub reachable"; else warn "GitHub not reachable"; fi

if [[ -f config.env ]]; then
  ok "config.env exists"
  set -a
  # shellcheck disable=SC1091
  source config.env
  set +a
else
  warn "config.env missing"
fi

for name in ECOWITT_APPLICATION_KEY ECOWITT_API_KEY ECOWITT_MAC; do
  if [[ -n "${!name:-}" ]]; then ok "$name configured"; else warn "$name not configured"; fi
done

if systemctl is-active --quiet matrix-os 2>/dev/null; then
  ok "matrix-os service active"
else
  warn "matrix-os service is not active"
fi

if python3 -m py_compile main.py matrix_engine.py live_data.py >/dev/null 2>&1; then
  ok "Python syntax check passed"
else
  fail "Python syntax check failed"
fi

printf '\nRecent service log:\n'
systemctl --no-pager --full status matrix-os 2>/dev/null | tail -n 12 || true
