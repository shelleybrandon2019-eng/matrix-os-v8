#!/usr/bin/env bash
set -euo pipefail

FILE=""
for candidate in \
  "$HOME/v2_matrix.py" \
  "/home/b/v2_matrix.py" \
  "$HOME/matrix-os-v8/v2_matrix.py" \
  "$(cd "$(dirname "$0")" && pwd)/v2_matrix.py"
do
  if [[ -f "$candidate" ]]; then
    FILE="$candidate"
    break
  fi
done

show_message() {
  local message="$1"
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="Matrix V2" --text="$message" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "Matrix V2" "$message" || true
  fi
}

if [[ -z "$FILE" ]]; then
  show_message "I could not find v2_matrix.py. Expected it at /home/b/v2_matrix.py or ~/v2_matrix.py."
  exit 1
fi

COPIED=0
if command -v wl-copy >/dev/null 2>&1; then
  wl-copy < "$FILE"
  COPIED=1
elif command -v xclip >/dev/null 2>&1; then
  xclip -selection clipboard < "$FILE"
  COPIED=1
elif command -v xsel >/dev/null 2>&1; then
  xsel --clipboard --input < "$FILE"
  COPIED=1
else
  # Tk must remain alive on X11 to keep ownership of the clipboard.
  python3 - "$FILE" <<'PY' >/tmp/matrix_v2_clipboard.log 2>&1 &
import pathlib
import sys
import time
import tkinter as tk

path = pathlib.Path(sys.argv[1])
root = tk.Tk()
root.withdraw()
root.clipboard_clear()
root.clipboard_append(path.read_text(encoding="utf-8"))
root.update()
end = time.time() + 600
while time.time() < end:
    root.update()
    time.sleep(0.25)
PY
  sleep 0.6
  COPIED=1
fi

if [[ "$COPIED" -eq 1 ]]; then
  show_message "Matrix V2 was copied. ChatGPT is opening—click the message box and press Ctrl+V."
fi

xdg-open "https://chatgpt.com/" >/dev/null 2>&1 &
