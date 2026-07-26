#!/usr/bin/env bash
set -u

cd "$(dirname "$0")" || exit 1

CHECK_SECONDS="${MATRIX_UPDATE_SECONDS:-20}"
BRANCH="${MATRIX_UPDATE_BRANCH:-main}"

if [[ -f config.env ]]; then
  set -a
  source config.env
  set +a
fi

force_sync() {
  git fetch origin "$BRANCH" || return 1

  local remote_sha
  remote_sha="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"
  [[ -n "$remote_sha" ]] || return 1

  # Force the Pi checkout to exactly match GitHub. This fixes dirty, detached,
  # stale, or diverged local copies that caused old screens to stay running.
  git checkout -B "$BRANCH" "origin/$BRANCH" || return 1
  git reset --hard "origin/$BRANCH" || return 1
  return 0
}

kill_legacy_matrix() {
  # Remove the old standalone Matrix versions so only this repo's main.py owns
  # the display. Do not match this start_matrix.sh process.
  pkill -f '^/usr/bin/python3 /home/b/v2_matrix.py$' 2>/dev/null || true
  pkill -f '^python3 /home/b/v2_matrix.py$' 2>/dev/null || true
  pkill -f '^/usr/bin/python3 /home/b/matrix_time_glitch.py$' 2>/dev/null || true
  pkill -f '^python3 /home/b/matrix_time_glitch.py$' 2>/dev/null || true
  pkill -f '^/usr/bin/python3 /home/b/matrix-os-v8/v2_matrix.py$' 2>/dev/null || true
  pkill -f '^python3 /home/b/matrix-os-v8/v2_matrix.py$' 2>/dev/null || true
}

force_sync || true
kill_legacy_matrix

while true; do
  echo "[Matrix OS] starting commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  /usr/bin/python3 main.py &
  APP_PID=$!

  while kill -0 "$APP_PID" 2>/dev/null; do
    sleep "$CHECK_SECONDS"
    git fetch --quiet origin "$BRANCH" 2>/dev/null || continue

    LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
    REMOTE_SHA="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"

    if [[ -n "$REMOTE_SHA" && "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
      echo "[Matrix OS] update detected: ${LOCAL_SHA:0:7} -> ${REMOTE_SHA:0:7}"
      kill "$APP_PID" 2>/dev/null || true
      wait "$APP_PID" 2>/dev/null || true
      force_sync || true
      kill_legacy_matrix
      sleep 1
      break
    fi
  done

  if kill -0 "$APP_PID" 2>/dev/null; then
    continue
  fi

  wait "$APP_PID" 2>/dev/null || true
  echo "[Matrix OS] main.py stopped; restarting in 2 seconds"
  sleep 2
done
