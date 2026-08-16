#!/usr/bin/env python3
"""Keep the ESP32 clock synchronized to the exact same local clock as the Pi UI.

Uses only the Python standard library so the Pi does not need pyserial.
The Matrix dashboard itself uses datetime.now(); this bridge deliberately does the
same thing so there is no second timezone/DST conversion that can make the ESP32
one hour different from the main display.

On startup the bridge also verifies the ESP32 clock firmware source hash. If the
Pi has a newer clock firmware than the board, it flashes that firmware once and
then resumes the serial clock feed automatically.

Protocol sent to the ESP32:
    TIME|HH|MM|SS||YYYY-MM-DD

HH is 24-hour local Pi time. The empty field after seconds intentionally clears
AM/PM on the ESP32 display.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import select
import subprocess
import sys
import termios
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
PORT = os.getenv("MATRIX_ESP32_PORT", "/dev/ttyACM0")
BAUD = termios.B115200
STATE_FILE = Path(
    os.getenv("MATRIX_SIDECAR_STATE_FILE", "/tmp/matrix_sidecar_state.json")
)
LOCK_FILE = os.getenv("MATRIX_ESP32_LOCK", "/tmp/matrix-esp32-clock.lock")
FW_MARKER = Path.home() / ".cache" / "matrix-os-v8" / "esp32-clock-fw.sha256"
FW_FILES = (
    ROOT / "esp32_clock" / "src" / "main.cpp",
    ROOT / "esp32_clock" / "platformio.ini",
)
RECONNECT_SECONDS = 2.0
SYNC_INTERVAL = 0.20
VALID_EVENTS = {"MELT", "BULLET", "AGENT", "SCAN", "GLITCH", "BREACH", "PHONE"}


def firmware_hash() -> Optional[str]:
    digest = hashlib.sha256()
    try:
        for path in FW_FILES:
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    except OSError as exc:
        print(f"[ESP32 clock] cannot hash firmware: {exc}", file=sys.stderr, flush=True)
        return None
    return digest.hexdigest()


def ensure_current_firmware() -> None:
    """Flash the repo's ESP32 clock firmware once whenever its source changes."""
    if not Path(PORT).exists():
        return

    wanted = firmware_hash()
    if not wanted:
        return

    try:
        installed = FW_MARKER.read_text(encoding="utf-8").strip()
    except OSError:
        installed = ""

    if installed == wanted:
        return

    print("[ESP32 clock] firmware update needed; flashing current clock firmware", flush=True)
    env = os.environ.copy()
    env["MATRIX_ESP32_PORT"] = PORT
    env["MATRIX_SKIP_BRIDGE_KILL"] = "1"

    try:
        result = subprocess.run(
            ["/bin/bash", str(ROOT / "flash_esp32_clock.sh")],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=240,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[ESP32 clock] automatic firmware flash failed: {exc}", file=sys.stderr, flush=True)
        return

    if result.stdout:
        print(result.stdout.rstrip(), flush=True)

    if result.returncode != 0:
        print(
            f"[ESP32 clock] firmware flash exited {result.returncode}; continuing with serial sync",
            file=sys.stderr,
            flush=True,
        )
        return

    try:
        FW_MARKER.parent.mkdir(parents=True, exist_ok=True)
        FW_MARKER.write_text(wanted + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"[ESP32 clock] could not save firmware marker: {exc}", file=sys.stderr, flush=True)

    # Give USB CDC time to disappear/re-enumerate after the upload reset.
    time.sleep(2.0)
    print("[ESP32 clock] firmware flash complete; starting live Pi-time sync", flush=True)


class RawSerial:
    def __init__(self, port: str) -> None:
        self.port = port
        self.fd: Optional[int] = None
        self.rx = bytearray()
        self.opened_at = 0.0

    def open(self) -> bool:
        self.close()
        try:
            fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            attrs = termios.tcgetattr(fd)
            attrs[0] = 0
            attrs[1] = 0
            attrs[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
            attrs[3] = 0
            attrs[4] = BAUD
            attrs[5] = BAUD
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            termios.tcflush(fd, termios.TCIOFLUSH)
            self.fd = fd
            self.opened_at = time.monotonic()
            print(f"[ESP32 clock] connected to {self.port}", flush=True)
            return True
        except OSError as exc:
            print(f"[ESP32 clock] waiting for {self.port}: {exc}", file=sys.stderr)
            self.fd = None
            return False

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.fd = None

    def write_line(self, line: str) -> bool:
        if self.fd is None:
            return False
        try:
            payload = (line.rstrip("\r\n") + "\n").encode("ascii", "replace")
            view = memoryview(payload)
            while view:
                written = os.write(self.fd, view)
                view = view[written:]
            return True
        except OSError as exc:
            print(f"[ESP32 clock] serial write failed: {exc}", file=sys.stderr)
            self.close()
            return False

    def read_lines(self) -> list[str]:
        if self.fd is None:
            return []
        lines: list[str] = []
        try:
            ready, _, _ = select.select([self.fd], [], [], 0)
            if ready:
                chunk = os.read(self.fd, 4096)
                if chunk:
                    self.rx.extend(chunk)
            while b"\n" in self.rx:
                raw, _, rest = self.rx.partition(b"\n")
                self.rx = bytearray(rest)
                text = raw.decode("utf-8", "replace").strip()
                if text:
                    lines.append(text)
        except OSError:
            self.close()
        return lines


def local_now() -> datetime:
    """Use the exact same host-local wall clock as the Matrix dashboard."""
    return datetime.now()


def clock_line(now: datetime) -> str:
    """Send 24-hour Pi-local time; blank AM/PM keeps ESP display clean."""
    return (
        f"TIME|{now.hour:02d}|{now.minute:02d}|{now.second:02d}||"
        f"{now:%Y-%m-%d}"
    )


def read_event(last_event_id: object) -> tuple[object, Optional[str]]:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return last_event_id, None

    if payload.get("mode") != "clock_event":
        return last_event_id, None
    event_id = payload.get("event_id")
    if event_id == last_event_id:
        return last_event_id, None
    event = str(payload.get("event", "")).upper()
    if event not in VALID_EVENTS:
        return event_id, None
    return event_id, event


def acquire_single_writer() -> object:
    """Guarantee only one process can write clock data to the ESP32."""
    lock = open(LOCK_FILE, "w", encoding="utf-8")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[ESP32 clock] another clock bridge already owns the serial writer", flush=True)
        raise SystemExit(0)
    lock.write(str(os.getpid()))
    lock.flush()
    return lock


def main() -> int:
    _writer_lock = acquire_single_writer()

    # This runs before opening the serial port, so PlatformIO can own the ESP32
    # cleanly if the board is still running older clock firmware.
    ensure_current_firmware()

    serial = RawSerial(PORT)
    last_connect_attempt = -999.0
    last_sync = -999.0
    last_second = -1
    last_event_id: object = None
    hello_sent = False

    print(
        f"[ESP32 clock] Pi-local 24h current={local_now():%Y-%m-%d %H:%M:%S}",
        flush=True,
    )

    try:
        while True:
            now_mono = time.monotonic()
            if serial.fd is None:
                if now_mono - last_connect_attempt >= RECONNECT_SECONDS:
                    last_connect_attempt = now_mono
                    hello_sent = False
                    serial.open()
                time.sleep(0.10)
                continue

            # ESP32-S3 USB CDC may reboot when the port opens. Give it a moment.
            if not hello_sent and now_mono - serial.opened_at >= 1.20:
                hello_sent = serial.write_line("HELLO|MATRIX_OS_V10_HUB_CUT")
                if hello_sent:
                    # Force the real Pi time onto the screen immediately after every
                    # reconnect instead of allowing any stale clock value to remain.
                    now = local_now()
                    serial.write_line(clock_line(now))
                    last_second = now.second
                    last_sync = now_mono

            now = local_now()
            if hello_sent and (
                now.second != last_second or now_mono - last_sync >= 1.0
            ):
                if serial.write_line(clock_line(now)):
                    last_second = now.second
                    last_sync = now_mono

            last_event_id, event = read_event(last_event_id)
            if hello_sent and event:
                serial.write_line(f"EVENT|{event}")

            for line in serial.read_lines():
                print(f"[ESP32 clock] {line}", flush=True)

            time.sleep(SYNC_INTERVAL)
    except KeyboardInterrupt:
        return 0
    finally:
        serial.close()
        # Keep a reference alive until shutdown so flock remains held.
        _ = _writer_lock


if __name__ == "__main__":
    raise SystemExit(main())
