#!/usr/bin/env bash
set -u

cd "$(dirname "$0")"

if [[ -f config.env ]]; then
  set -a
  source config.env
  set +a
fi

CHECK_SECONDS="${MATRIX_UPDATE_SECONDS:-20}"
BRANCH="${MATRIX_UPDATE_BRANCH:-main}"

while true; do
  git fetch --quiet origin "$BRANCH" 2>/dev/null || true
  LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
  REMOTE_SHA="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"

  if [[ -n "$REMOTE_SHA" && "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
    git pull --ff-only origin "$BRANCH" || true
  fi

  /usr/bin/python3 v8_matrix.py &
  APP_PID=$!
  UPDATED=0

  while kill -0 "$APP_PID" 2>/dev/null; do
    sleep "$CHECK_SECONDS"
    git fetch --quiet origin "$BRANCH" 2>/dev/null || continue

    LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
    REMOTE_SHA="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"

    if [[ -n "$REMOTE_SHA" && "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
      git pull --ff-only origin "$BRANCH" || continue
      UPDATED=1
      kill "$APP_PID" 2>/dev/null || true
      wait "$APP_PID" 2>/dev/null || true
      break
    fi
  done

  if [[ "$UPDATED" -eq 1 ]]; then
    sleep 1
    continue
  fi

  wait "$APP_PID"
  exit $?
done
