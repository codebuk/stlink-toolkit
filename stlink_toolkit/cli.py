import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from .extensions import (
    DEFAULT_ST_EXTENSION_IDS,
    disable_extensions,
    enable_extensions,
)
from .usb import find_probe_vcps, find_probes


_DUMMY_C_SOURCE = """int main(void) {\n    return 0;\n}\n"""


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


def create_dummy_elf(out_dir: Path, name: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    src_path = out_dir / f"{name}.c"
    elf_path = out_dir / f"{name}.elf"

    src_path.write_text(_DUMMY_C_SOURCE)

    compiler = shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        print("Error: no C compiler found (gcc/clang).", file=sys.stderr)
        return 2

    cmd = [compiler, "-Os", "-s", "-o", str(elf_path), str(src_path)]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Error: failed to build dummy ELF with {compiler}: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote source: {src_path}")
    print(f"Wrote ELF: {elf_path}")
    return 0


def list_vcps(json_output: bool = False) -> int:
    rows = find_probe_vcps()
    if json_output:
        print(json.dumps(rows, indent=2))
        return 0

    rows.sort(key=lambda x: (x["device"], x["probe_serial"]))
    print(f"count={len(rows)}")
    for row in rows:
        by_id = ",".join(row.get("by_id", [])) or "-"
        print(
            f"tty={row['device']} "
            f"probe={row['probe_serial']} nick={row['probe_nick']} type={row['probe_type']} "
            f"vidpid={row['usb_vid']}:{row['usb_pid']} "
            f"busaddr={row['usb_bus']}:{row['usb_address']} by-id={by_id}"
        )
    return 0


def list_probes(tree: bool = False, with_vcps: bool = False, tree_device: bool = False) -> int:
    probes = find_probes()

    vcps_by_serial: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if with_vcps or tree:
        for row in find_probe_vcps():
            vcps_by_serial[row["probe_serial"]].append(row)
        for rows in vcps_by_serial.values():
            rows.sort(key=lambda x: x["device"])

    if tree and tree_device:
        rows: List[Dict[str, Any]] = []
        for serial_rows in vcps_by_serial.values():
            rows.extend(serial_rows)
        rows.sort(key=lambda x: (x["device"], x["probe_serial"]))

        seen_serials = set()
        for row in rows:
            by_id = ",".join(row.get("by_id", [])) or "-"
            print(f"tty={row['device']} by-id={by_id}")
            print(
                f"  |- probe={row['probe_serial']} nick={row['probe_nick']} "
                f"type={row['probe_type']}"
            )
            seen_serials.add(row["probe_serial"])

        for probe in probes:
            if probe.serial not in seen_serials:
                print(f"probe={probe.serial} nick={probe.last_3} type={probe.description} (no tty)")
        return 0

    if tree:
        for probe in probes:
            print(f"probe={probe.serial} nick={probe.last_3} type={probe.description}")
            rows = vcps_by_serial.get(probe.serial, [])
            if not rows:
                print("  |- tty=- by-id=-")
                continue
            for row in rows:
                by_id = ",".join(row.get("by_id", [])) or "-"
                print(f"  |- tty={row['device']} by-id={by_id}")
        return 0

    for probe in probes:
        print(f"probe={probe.serial} nick={probe.last_3} type={probe.description}")
        if with_vcps:
            for row in vcps_by_serial.get(probe.serial, []):
                by_id = ",".join(row.get("by_id", [])) or "-"
                print(f"  tty={row['device']} by-id={by_id}")
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

    dummy_cmd = sub.add_parser(
        "create-dummy-elf",
        help="Create deterministic dummy C source and build an ELF fixture",
    )
    dummy_cmd.add_argument(
        "--out-dir",
        default="test-assets/dummy-elf",
        help="Output directory for generated source/ELF (default: test-assets/dummy-elf)",
    )
    dummy_cmd.add_argument(
        "--name",
        default="dummy_zero",
        help="Base filename for source/ELF (default: dummy_zero)",
    )

    vcps_cmd = sub.add_parser(
        "list-vcps",
        help="List VCP serial ports and map them to ST-Link probe identifiers",
    )
    vcps_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )

    probes_cmd = sub.add_parser(
        "list-probes",
        help="List detected probes; optionally include mapped VCP tty entries",
    )
    probes_cmd.add_argument(
        "--with-vcps",
        action="store_true",
        help="Include VCP tty rows under each probe",
    )
    probes_cmd.add_argument(
        "--tree",
        action="store_true",
        help="Render programmer-first tree format (probe root, tty children)",
    )
    probes_cmd.add_argument(
        "--tree-device",
        action="store_true",
        help="Use device-first tree format (tty root, probe child) with --tree",
    )

    for name, help_text in (
        ("ext-disable", "Disable ST debugging VS Code extensions (sets disabled flag in VS Code state DB)"),
        ("ext-enable", "Re-enable ST debugging VS Code extensions (clears disabled flag in VS Code state DB)"),
    ):
        ext_cmd = sub.add_parser(name, help=help_text)
        ext_cmd.add_argument(
            "--ext",
            action="append",
            default=[],
            metavar="PUBLISHER.NAME",
            help=(
                "Extension id (repeatable). Defaults to: "
                + ", ".join(DEFAULT_ST_EXTENSION_IDS)
            ),
        )
    return parser


def main(argv: List[str] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-registry":
        return init_registry(Path(args.path))
    if args.command == "create-dummy-elf":
        return create_dummy_elf(Path(args.out_dir), args.name)
    if args.command == "list-vcps":
        return list_vcps(json_output=bool(args.json))
    if args.command == "list-probes":
        return list_probes(
            tree=bool(args.tree),
            with_vcps=bool(args.with_vcps),
            tree_device=bool(args.tree_device),
        )
    if args.command in ("ext-disable", "ext-enable"):
        ext_ids = tuple(args.ext) if args.ext else DEFAULT_ST_EXTENSION_IDS
        fn = disable_extensions if args.command == "ext-disable" else enable_extensions
        try:
            fn(ext_ids)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())