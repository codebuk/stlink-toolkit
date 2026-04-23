import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .usb import find_probes


def _load_existing(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _ensure_template_shape(reg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(reg)
    if not isinstance(out.get("probes"), list):
        out["probes"] = []
    if not isinstance(out.get("boards"), list):
        out["boards"] = []
    if not isinstance(out.get("mode_probe_map"), dict):
        out["mode_probe_map"] = {}
    if not isinstance(out.get("mode_probe_map_auto_update"), bool):
        out["mode_probe_map_auto_update"] = False
    return out


def _probe_record(serial: str, model: str) -> Dict[str, Any]:
    return {
        "serial": serial,
        "nick": serial[-3:] if len(serial) >= 3 else serial,
        "model": model,
    }


def init_registry(path: Path) -> int:
    existing = _ensure_template_shape(_load_existing(path))

    serial_to_probe: Dict[str, Dict[str, Any]] = {}
    for item in existing["probes"]:
        if not isinstance(item, dict):
            continue
        serial = item.get("serial")
        if isinstance(serial, str) and serial:
            serial_to_probe[serial] = dict(item)

    detected = find_probes()
    added_serials: List[str] = []
    for probe in detected:
        if probe.serial in serial_to_probe:
            continue
        serial_to_probe[probe.serial] = _probe_record(probe.serial, probe.description or "ST-Link")
        added_serials.append(probe.serial)

    existing["probes"] = [serial_to_probe[sn] for sn in sorted(serial_to_probe)]
    path.write_text(json.dumps(existing, indent=2) + "\n")

    print(f"Wrote {path} with {len(existing['probes'])} probe(s).")
    if added_serials:
        suffixes = ", ".join(sn[-3:] if len(sn) >= 3 else sn for sn in sorted(added_serials))
        print(f"Added detected probe(s): {suffixes}")
    else:
        print("No new probes were added from live detection.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stlink-toolkit", description="ST-Link toolkit helpers")
    sub = parser.add_subparsers(dest="command")

    init_cmd = sub.add_parser(
        "init-registry",
        help="Create/update probes registry template and add currently detected probes",
    )
    init_cmd.add_argument(
        "--path",
        default="probes.json",
        help="Registry file path (default: probes.json)",
    )
    return parser


def main(argv: List[str] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-registry":
        return init_registry(Path(args.path))

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())