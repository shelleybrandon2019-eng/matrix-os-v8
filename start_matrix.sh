#!/usr/bin/env bash
set -u

cd "$(dirname "$0")" || exit 1

CHECK_SECONDS="${MATRIX_UPDATE_SECONDS:-20}"
BRANCH="${MATRIX_UPDATE_BRANCH:-main}"
ESP32_PORT="${MATRIX_ESP32_PORT:-/dev/ttyACM0}"
BRIDGE_PID=""
APP_PID=""
LOCK_FILE="/tmp/matrix-os-v8.lock"

if [[ -f config.env ]]; then
  set -a
  source config.env
  set +a
  ESP32_PORT="${MATRIX_ESP32_PORT:-$ESP32_PORT}"
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[Matrix OS] another launcher is already running; exiting"
  exit 0
fi

force_sync() {
  git fetch origin "$BRANCH" || return 1
  local remote_sha
  remote_sha="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"
  [[ -n "$remote_sha" ]] || return 1

  # Local tracked edits must never wedge the kiosk in an update/restart loop.
  # Preserve them in a stash for recovery, but keep GitHub as the live source.
  if ! git diff --quiet || ! git diff --cached --quiet; then
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    echo "[Matrix OS] local tracked edits found; stashing as matrix-autoupdate-$stamp"
    git stash push -m "matrix-autoupdate-$stamp" -- . || return 1
  fi

  git checkout -f -B "$BRANCH" "origin/$BRANCH" || return 1
  git reset --hard "origin/$BRANCH" || return 1
}

kill_old_displays() {
  # SIGKILL is intentional: a process suspended with Ctrl+Z will not handle SIGTERM.
  pkill -KILL -f '/home/b/v2_matrix.py' 2>/dev/null || true
  pkill -KILL -f '/home/b/matrix_time_glitch.py' 2>/dev/null || true
  pkill -KILL -f 'cinematic_director.py' 2>/dev/null || true
  pkill -KILL -f 'temp_scene_director.py' 2>/dev/null || true
  pkill -KILL -f 'esp32_clock_bridge.py' 2>/dev/null || true
  pkill -KILL -f '/home/b/matrix-os-v8/main.py' 2>/dev/null || true
}

stop_children() {
  if [[ -n "$APP_PID" ]]; then
    kill -KILL "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
    APP_PID=""
  fi
  if [[ -n "$BRIDGE_PID" ]]; then
    kill -KILL "$BRIDGE_PID" 2>/dev/null || true
    wait "$BRIDGE_PID" 2>/dev/null || true
    BRIDGE_PID=""
  fi
}

trap 'stop_children' EXIT INT TERM

start_bridge_if_present() {
  if [[ -e "$ESP32_PORT" ]]; then
    /usr/bin/python3 esp32_clock_bridge.py &
    BRIDGE_PID=$!
    echo "[Matrix OS] ESP32 bridge PID $BRIDGE_PID on $ESP32_PORT"
  else
    BRIDGE_PID=""
    echo "[Matrix OS] ESP32 not found on $ESP32_PORT; continuing without bridge"
  fi
}

if ! force_sync; then
  echo "[Matrix OS] initial GitHub sync failed; starting installed version"
fi
kill_old_displays

while true; do
  echo "[Matrix OS] dashboard, commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  start_bridge_if_present
  /usr/bin/python3 temp_scene_director.py &
  APP_PID=$!
  UPDATED=0

  while kill -0 "$APP_PID" 2>/dev/null; do
    sleep "$CHECK_SECONDS"

    if [[ -n "$BRIDGE_PID" ]] && ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
      wait "$BRIDGE_PID" 2>/dev/null || true
      start_bridge_if_present
    elif [[ -z "$BRIDGE_PID" && -e "$ESP32_PORT" ]]; then
      start_bridge_if_present
    fi

    git fetch --quiet origin "$BRANCH" 2>/dev/null || continue
    LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
    REMOTE_SHA="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"

    if [[ -n "$REMOTE_SHA" && "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
      echo "[Matrix OS] update detected: ${LOCAL_SHA:0:7} -> ${REMOTE_SHA:0:7}"

      # Sync first while the current dashboard remains visible. Only restart the
      # display after a successful sync, so a Git problem cannot cause blackouts.
      if force_sync; then
        UPDATED=1
        stop_children
        kill_old_displays
        sleep 1
        break
      else
        echo "[Matrix OS] update sync failed; keeping current dashboard running"
      fi
    fi
  done

  if [[ "$UPDATED" -eq 1 ]]; then
    continue
  fi

  stop_children
  echo "[Matrix OS] dashboard stopped; restarting in 2 seconds"
  sleep 2
done
