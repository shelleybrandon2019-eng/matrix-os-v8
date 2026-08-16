"""Matrix OS runtime bootstrap for optional BLE support.

Python imports sitecustomize automatically at interpreter startup.  The Pi's
GitHub updater does not rerun install.sh when a dependency changes, so this
keeps the Govee BLE reader self-healing after a normal GitHub pull.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys


def _bleak_available() -> bool:
    try:
        importlib.import_module("bleak")
        return True
    except Exception:
        return False


ROOT = Path(__file__).resolve().parent
LOCAL_DEPS = ROOT / ".matrix_deps"

# Always make a previously bootstrapped local dependency directory importable.
if LOCAL_DEPS.is_dir():
    local_path = str(LOCAL_DEPS)
    if local_path not in sys.path:
        sys.path.insert(0, local_path)

# Prevent recursion when this file launches `python -m pip` below.
if os.environ.get("MATRIX_BLE_BOOTSTRAP_RUNNING") != "1" and not _bleak_available():
    print("[Matrix OS] BLE support missing; bootstrapping Govee support...")

    # First prefer Raspberry Pi OS's packaged version.  This succeeds silently
    # on systems where the matrix service account has passwordless sudo.
    try:
        subprocess.run(
            ["sudo", "-n", "apt-get", "install", "-y", "python3-bleak", "python3-dbus", "bluez"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
        )
        importlib.invalidate_caches()
    except Exception:
        pass

    # If sudo is unavailable, install Bleak into an untracked repo-local folder.
    # --target avoids changing the system Python environment.
    if not _bleak_available():
        try:
            LOCAL_DEPS.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["MATRIX_BLE_BOOTSTRAP_RUNNING"] = "1"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-input",
                    "--target",
                    str(LOCAL_DEPS),
                    "--break-system-packages",
                    "bleak>=0.20",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=75,
                env=env,
            )
            local_path = str(LOCAL_DEPS)
            if local_path not in sys.path:
                sys.path.insert(0, local_path)
            importlib.invalidate_caches()
        except Exception:
            pass

    if _bleak_available():
        print("[Matrix OS] BLE/Govee support ready.")
    else:
        print("[Matrix OS] BLE bootstrap could not install Bleak; room temps will remain --°F.")
