#!/usr/bin/env bash
set -u

cd "$(dirname "$0")"

install_v2_shortcut() {
  local repo_dir desktop_dir launcher helper
  repo_dir="$(pwd)"
  desktop_dir="$HOME/Desktop"
  launcher="$desktop_dir/Copy Matrix V2 to ChatGPT.desktop"
  helper="$repo_dir/copy_matrix_v2_to_chat.sh"

  [[ -f "$helper" ]] || return 0
  mkdir -p "$desktop_dir"
  chmod +x "$helper"

  cat > "$launcher" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Copy Matrix V2 to ChatGPT
Comment=Copy v2_matrix.py and open ChatGPT ready to paste
Exec=/bin/bash $helper
Icon=accessories-text-editor
Terminal=false
Categories=Utility;
EOF

  chmod +x "$launcher"
  if command -v gio >/dev/null 2>&1; then
    gio set "$launcher" metadata::trusted true >/dev/null 2>&1 || true
  fi
}

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

  install_v2_shortcut

  /usr/bin/python3 main.py &
  APP_PID=$!
  UPDATED=0

  while kill -0 "$APP_PID" 2>/dev/null; do
    sleep "$CHECK_SECONDS"
    git fetch --quiet origin "$BRANCH" 2>/dev/null || continue

    LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
    REMOTE_SHA="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"

    if [[ -n "$REMOTE_SHA" && "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
      git pull --ff-only origin "$BRANCH" || continue
      install_v2_shortcut
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
