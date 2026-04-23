"""Interactive ST-Link probe selection with LED-cycling identification."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import List, Optional

from .programmer import EXPECTED_DEVICE_ID, EXPECTED_DEVICE_NAME, PROG_CMD, is_expected_device
from .usb import STLinkProbe


def flash_led_cycle(probes: List[STLinkProbe], stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        for i, probe in enumerate(probes, 1):
            if stop_event.is_set():
                break
            try:
                subprocess.Popen(
                    [*PROG_CMD, "-c", "port=SWD", "freq=4000", f"sn={probe.serial}", "reset=HWrst", "-q"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                sys.stderr.write(f"\r💡 Device {i} (...{probe.last_3}) LED flashing...  ")
                sys.stderr.flush()
                stop_event.wait(2)
            except Exception:
                pass


def select_probe(probes: List[STLinkProbe], operation: str = "program") -> Optional[STLinkProbe]:
    if len(probes) == 1:
        probe = probes[0]
        if probe.device_id and not is_expected_device(probe):
            print(f"⚠️  WARNING: Device ID {probe.device_id} (expected {EXPECTED_DEVICE_ID} for {EXPECTED_DEVICE_NAME})")
        print(f"Auto-selected probe: {probe.serial}")
        return probe

    print("\nMultiple ST-LINK probes detected:\n")
    for i, probe in enumerate(probes, 1):
        print(f"  {i}) {probe}")

    print("\n💡 LEDs will cycle every 2 seconds — watch your devices to identify them!")
    print(f"    Type 'all' or 'a' to {operation} all devices\n")

    stop_event = threading.Event()
    led_thread = threading.Thread(target=flash_led_cycle, args=(probes, stop_event), daemon=True)
    led_thread.start()
    time.sleep(0.2)

    try:
        if not sys.stdin.isatty():
            stop_event.set()
            print("Multiple probes detected but stdin is not a tty — use --sn to select a probe.", file=sys.stderr)
            sys.exit(2)
        choice = input(f"Select probe (1-{len(probes)}, full SN, last 3 chars, 'all', or 'a'): ").strip()
    finally:
        stop_event.set()
        sys.stderr.write("\r" + " " * 60 + "\r")
        sys.stderr.flush()
        time.sleep(0.3)
        try:
            subprocess.run(["pkill", "-f", "cube programmer.*sn="], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    print()

    if choice.lower() in ("all", "a"):
        return None
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(probes):
            return probes[idx - 1]
    if len(choice) == 3:
        for probe in probes:
            if probe.last_3 == choice:
                return probe
    if len(choice) == 24:
        for probe in probes:
            if probe.serial == choice:
                return probe

    print(f"Invalid selection: {choice}", file=sys.stderr)
    sys.exit(2)
