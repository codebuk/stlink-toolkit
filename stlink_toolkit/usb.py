import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from .registry import _load_registry, _save_probe_usb_ids, lookup_probe

STLINK_VID = 0x0483
STLINK_PIDS = (
    0x3744,
    0x3748,
    0x374B,
    0x374A,
    0x374E,
    0x3753,
    0x3754,
)


def _require_usb_core():
    try:
        import usb.core  # type: ignore
        return usb.core
    except ImportError as exc:
        raise RuntimeError(
            "Missing required support package: pyusb. "
            "Install with Fedora dnf: sudo dnf install -y python3-pyusb "
            "or with pip: python3 -m pip install pyusb"
        ) from exc


class STLinkProbe:
    def __init__(self, serial: str, description: str = ""):
        self.serial = serial
        self.description = description
        self.last_3 = serial[-3:] if len(serial) >= 3 else serial

    def __str__(self) -> str:
        return f"SN: {self.serial} (...{self.last_3}) {self.description}"


def _find_stlink_by_serial(serial: Optional[str], preferred_pid: Optional[int] = None):
    usb_core = _require_usb_core()

    pids_to_try: List[int] = []
    if preferred_pid is not None:
        pids_to_try.append(preferred_pid)
    for pid in STLINK_PIDS:
        if pid not in pids_to_try:
            pids_to_try.append(pid)

    for pid in pids_to_try:
        for dev in usb_core.find(find_all=True, idVendor=STLINK_VID, idProduct=pid) or []:
            if serial is None:
                return dev
            try:
                if (dev.serial_number or "") == serial:
                    return dev
            except (ValueError, usb_core.USBError):
                continue
    return None


def _find_all_stlink_usb_devices() -> List[dict]:
    devices: List[dict] = []
    seen: set = set()

    try:
        usb_core = _require_usb_core()

        for pid in STLINK_PIDS:
            for dev in usb_core.find(find_all=True, idVendor=STLINK_VID, idProduct=pid) or []:
                key = (int(dev.bus), int(dev.address))
                if key in seen:
                    continue
                seen.add(key)
                serial: Optional[str] = None
                try:
                    serial = dev.serial_number or None
                except (ValueError, usb_core.USBError):
                    serial = None
                devices.append({
                    "dev": dev,
                    "serial": serial,
                    "vid": int(dev.idVendor),
                    "pid": int(dev.idProduct),
                    "bus": int(dev.bus),
                    "address": int(dev.address),
                })
        if devices:
            return devices
    except RuntimeError:
        raise
    except Exception:
        pass

    for entry in Path("/sys/bus/usb/devices").glob("*"):
        try:
            vid = int((entry / "idVendor").read_text().strip(), 16)
            pid = int((entry / "idProduct").read_text().strip(), 16)
            if vid != STLINK_VID or pid not in STLINK_PIDS:
                continue
            bus = int((entry / "busnum").read_text().strip())
            address = int((entry / "devnum").read_text().strip())
            key = (bus, address)
            if key in seen:
                continue
            seen.add(key)
            serial_path = entry / "serial"
            serial = serial_path.read_text().strip() if serial_path.exists() else None
            devices.append({
                "dev": None,
                "serial": serial or None,
                "vid": vid,
                "pid": pid,
                "bus": bus,
                "address": address,
            })
        except (OSError, ValueError):
            continue

    return devices


def find_probes(reset_usb: bool = False, list_command: Optional[List[str]] = None) -> List[STLinkProbe]:
    reg = _load_registry()
    reg_probes = {p.get("serial"): p for p in reg.get("probes", []) if p.get("serial")}

    try:
        if reset_usb:
            reset_detected_stlink_usb_devices()

        probes: List[STLinkProbe] = []
        for entry in _find_all_stlink_usb_devices():
            serial = entry.get("serial")
            if not serial:
                continue
            reg_entry = reg_probes.get(serial, {})
            description = reg_entry.get("model") or f"USB {entry['vid']:04x}:{entry['pid']:04x}"
            probes.append(STLinkProbe(serial, description))
            try:
                _save_probe_usb_ids(serial, int(entry["vid"]), int(entry["pid"]))
            except Exception:
                pass

        if probes:
            probes.sort(key=lambda p: p.serial)
            return probes

        if list_command:
            result = subprocess.run([*list_command, "-l", "stlink"], capture_output=True, text=True)
            fallback: List[STLinkProbe] = []
            for line in result.stdout.splitlines():
                if "ST-LINK SN" in line:
                    match = re.search(r"([0-9A-F]{24})", line)
                    if match:
                        sn = match.group(1)
                        desc_start = line.find(sn) + len(sn)
                        fallback.append(STLinkProbe(sn, line[desc_start:].strip()))
            return fallback

        return []

    except FileNotFoundError:
        print("Error: programmer binary not found on PATH.", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Error detecting probes: {exc}", file=sys.stderr)
        sys.exit(2)


def _poll_stlink_reenumerated(timeout_s: float = 5.0, serial: Optional[str] = None, preferred_pid: Optional[int] = None) -> bool:
    deadline = time.monotonic() + timeout_s
    t_start = deadline - timeout_s
    while time.monotonic() < deadline:
        time.sleep(0.05)
        if _find_stlink_by_serial(serial, preferred_pid) is not None:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            print(f"ST-Link re-enumerated after {elapsed_ms}ms")
            return True
    return False


def _sysfs_port_rebind(bus: int, devaddr: int) -> bool:
    import glob

    for entry in glob.glob("/sys/bus/usb/devices/*"):
        busnum_path = os.path.join(entry, "busnum")
        devnum_path = os.path.join(entry, "devnum")
        auth_path = os.path.join(entry, "authorized")
        try:
            if (int(open(busnum_path).read().strip()) == bus and
                    int(open(devnum_path).read().strip()) == devaddr and
                    os.path.exists(auth_path)):
                open(auth_path, "w").write("0")
                time.sleep(0.3)
                open(auth_path, "w").write("1")
                return True
        except (OSError, ValueError):
            continue
    return False


def usb_reset_stlink(serial: Optional[str] = None) -> bool:
    try:
        preferred_pid: Optional[int] = None
        if serial:
            entry = lookup_probe(serial) or {}
            preferred_pid = entry.get("usb_pid")

        dev = _find_stlink_by_serial(serial, preferred_pid)
        if dev is None:
            return False

        if serial:
            try:
                _save_probe_usb_ids(serial, int(dev.idVendor), int(dev.idProduct))
            except Exception:
                pass

        bus, devaddr = dev.bus, dev.address
        found_pid = int(dev.idProduct)

        try:
            dev.reset()
        except Exception:
            pass
        if _poll_stlink_reenumerated(5.0, serial, found_pid):
            return True

        if _sysfs_port_rebind(bus, devaddr):
            if _poll_stlink_reenumerated(5.0, serial, found_pid):
                return True

        devnode = f"/dev/bus/usb/{bus:03d}/{devaddr:03d}"
        usbreset_bin = shutil.which("usbreset")
        if usbreset_bin and os.path.exists(devnode):
            subprocess.run([usbreset_bin, devnode], timeout=10, check=False)
            if _poll_stlink_reenumerated(5.0, serial, found_pid):
                return True

        return False

    except Exception:
        return False


def reset_detected_stlink_usb_devices() -> None:
    devices = _find_all_stlink_usb_devices()
    for entry in devices:
        dev = entry["dev"]
        serial = entry["serial"]
        vid, pid = entry["vid"], entry["pid"]
        bus, address = entry["bus"], entry["address"]
        if serial:
            try:
                _save_probe_usb_ids(serial, vid, pid)
            except Exception:
                pass
        try:
            if dev is not None:
                dev.reset()
            else:
                _sysfs_port_rebind(bus, address)
        except Exception:
            continue
