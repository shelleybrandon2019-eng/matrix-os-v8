#!/usr/bin/env python3
"""Matrix OS V8 -> ESP32-S3 USB sidecar bridge.

The Raspberry Pi owns the data and sends compact JSON messages over USB serial.
The ESP32 only renders the received event on its attached screen.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any

import serial


@dataclass(slots=True)
class SidecarEvent:
    kind: str
    title: str
    value: str
    accent: str = "green"
    duration_ms: int = 8000


def send_event(port: serial.Serial, event: SidecarEvent) -> None:
    payload = json.dumps(asdict(event), separators=(",", ":")) + "\n"
    port.write(payload.encode("utf-8"))
    port.flush()


def demo_events() -> list[SidecarEvent]:
    return [
        SidecarEvent("status", "MATRIX OS V8", "PI LINK ONLINE", "green", 5000),
        SidecarEvent("weather", "OUTSIDE", "90°F", "red", 8000),
        SidecarEvent("room", "FRONT ROOM", "74°F", "cyan", 8000),
        SidecarEvent("room", "BEDROOM", "68°F", "blue", 8000),
        SidecarEvent("crypto", "XRP", "$0.00", "gold", 8000),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Matrix OS events to the ESP32 sidecar")
    parser.add_argument("--port", default="/dev/ttyACM0", help="ESP32 serial device")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--demo", action="store_true", help="Rotate built-in test events")
    parser.add_argument("--kind")
    parser.add_argument("--title")
    parser.add_argument("--value")
    parser.add_argument("--accent", default="green")
    parser.add_argument("--duration", type=int, default=8000)
    args = parser.parse_args()

    try:
        with serial.Serial(args.port, args.baud, timeout=1, write_timeout=2) as port:
            time.sleep(2.0)

            if args.demo:
                while True:
                    for event in demo_events():
                        print(f"Sending: {event.title} {event.value}")
                        send_event(port, event)
                        time.sleep(max(event.duration_ms / 1000.0, 1.0))

            if not (args.kind and args.title and args.value):
                parser.error("use --demo or provide --kind, --title, and --value")

            send_event(
                port,
                SidecarEvent(args.kind, args.title, args.value, args.accent, args.duration),
            )
            return 0
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
