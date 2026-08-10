#!/usr/bin/env python3
"""Matrix live channel.

Initial bridge: run the newest locally-installed Matrix prototype.
Future ChatGPT updates replace this file directly; the Pi auto-updater
pulls the commit and restarts the display service.
"""
from pathlib import Path
import os
import runpy
import sys

candidates = [
    Path.home() / "matrix_v81.py",
    Path.home() / "matrix_v8.py",
]

for target in candidates:
    if target.exists():
        os.environ.setdefault("DISPLAY", ":0")
        os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        runpy.run_path(str(target), run_name="__main__")
        sys.exit(0)

raise SystemExit("No local Matrix prototype found yet (expected ~/matrix_v81.py or ~/matrix_v8.py).")
