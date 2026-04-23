"""CLI entrypoint: argparse-style flag dispatch for the toolkit.

Backwards-compatible with the legacy `awto.py` flag surface.
"""

from __future__ import annotations

import atexit
import os
import sys
import time
from typing import List, Optional

from . import log
from .gdb_server import gdb_server_start
from .programmer import (
    FALLBACK_SWD_FREQ,
    MAX_SWD_FREQ,
    detect_attached_board,
    elf_build_mode,
    erase_device,
    program_with_recovery,
    scan_all_probes,
)
from .registry import (
    get_mode_probe_map,
    mode_probe_auto_update_enabled,
    update_mode_probe_map,
)
from .servers import find_running_shared_server_for_serial, run_server_cleanup_step
from .usb import STLinkProbe, find_probes, usb_reset_stlink

HELP_TEXT = """
Flash or erase STM32 devices using the Cube wrapper ("cube programmer").

Usage:
    awto.py [ELF_PATH]                          # Flash (default)
    awto.py --all [ELF_PATH]                    # Flash all probes
    awto.py --sn SERIAL [ELF_PATH]              # Flash specific probe
    awto.py --auto-probe [ELF_PATH]             # Pick probe matching ELF mode
    awto.py --erase [--all|--sn SERIAL]         # Erase
    awto.py --scan                              # List probes + boards
    awto.py --gdb-server --mode PDM             # Start GDB server
    awto.py --gdb-server --sn SERIAL            # Start GDB server (by SN)
    awto.py --cleanup-servers-only              # Just kill stale gdb-servers

Common options:
    --auto-update-mode-map  Persist mode->probe pin in probes.json
    --no-mode-check         Skip ELF/board build-mode safety check
    --full / --incremental  Force full or incremental write (default: incremental)
    --shared / --shared-auto  Shared-mode (StlinkServer) variants
    --no-id-check           Skip pre-flash device-ID probe (faster)
    --verbose / --no-passthrough / --timestamps  Output controls
    --freq KHz              Override SWD frequency (default 24000)
    --help                  Show this message

OTP commands (require --sn SERIAL or --auto-probe ELF):
    --read-otp                          Print full OTP block dump
    --provision-otp                     Burn product identity into next free block
    --reprovision-otp --confirm         Replace existing record (consumes a block)
    --lock-otp --confirm-permanent      PERMANENTLY lock the active block
""".strip()


def _print_runtime(start: float) -> None:
    print(f"[flash] Script total runtime: {time.monotonic() - start:0.3f}s")


# ── OTP handler registration ──────────────────────────────────────────────
# The toolkit is product-agnostic: it parses --read-otp / --provision-otp / etc
# and resolves the probe SN, then hands off to a project-supplied callback.
# The callback signature is (op: str, sn: str, confirm: bool, confirm_permanent: bool) -> int.
_otp_handler = None


def register_otp_handler(fn) -> None:
    """Register the project-specific OTP dispatcher. See :mod:`scripts.awto_otp`."""
    global _otp_handler
    _otp_handler = fn


def _resolve_probe_sn(specified_sn: Optional[str], auto_probe: bool, elf_path: str) -> Optional[str]:
    """Pick a probe SN from --sn or --auto-probe (using ELF build mode)."""
    if specified_sn:
        return specified_sn
    if not auto_probe:
        log.error("need --sn SERIAL or --auto-probe with an ELF path")
        return None
    mode = elf_build_mode(elf_path)
    if not mode:
        log.error("--auto-probe needs a Debug-{MODE} ELF path to infer the build mode")
        return None
    live = find_probes()
    pinned = get_mode_probe_map().get(mode)
    if pinned and any(p.serial == pinned for p in live):
        return pinned
    matches = [p.serial for p in live if (b := detect_attached_board(p.serial)) and b.get("build_mode") == mode]
    if len(matches) == 1:
        return matches[0]
    log.error("--auto-probe could not unambiguously pick a probe for mode %s (matches=%d)", mode, len(matches))
    return None


def main(default_elf: str = "Debug/l8-427.elf") -> None:
    script_start = time.monotonic()
    atexit.register(_print_runtime, script_start)

    do_erase = False
    program_all = False
    specified_sn: Optional[str] = None
    auto_probe = False
    use_shared = False
    shared_auto = False
    skip_id_check = False
    force_full = False
    verbose = True
    passthrough = False
    timestamps = False
    freq_override: Optional[int] = None
    elf_path = default_elf
    do_scan = False
    do_gdb_server = False
    gdb_server_mode: Optional[str] = None
    no_mode_check = False
    auto_update_mode_map = False
    connect_under_reset_for_flash = False
    cleanup_servers_only = False

    # OTP operations (project-specific dispatch via scripts/awto_otp.py)
    otp_op: Optional[str] = None  # 'read' | 'provision' | 'reprovision' | 'lock'
    otp_confirm = False
    otp_confirm_permanent = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            print(HELP_TEXT)
            sys.exit(0)
        elif arg == "--erase":
            do_erase = True
        elif arg == "--scan":
            do_scan = True
        elif arg == "--gdb-server":
            do_gdb_server = True
        elif arg == "--mode":
            if i + 1 >= len(args):
                log.error("--mode requires a mode name"); sys.exit(2)
            gdb_server_mode = args[i + 1].upper(); i += 1
        elif arg == "--no-mode-check":
            no_mode_check = True
        elif arg in ("--all", "-a"):
            program_all = True
        elif arg == "--sn":
            if i + 1 >= len(args):
                log.error("--sn requires a serial number"); sys.exit(2)
            specified_sn = args[i + 1]; i += 1
        elif arg == "--auto-probe":
            auto_probe = True
        elif arg == "--auto-update-mode-map":
            auto_update_mode_map = True
        elif arg == "--shared":
            use_shared = True
        elif arg in ("--shared-auto", "--auto-shared"):
            shared_auto = True
        elif arg == "--cleanup-servers-only":
            cleanup_servers_only = True
        elif arg == "--read-otp":
            otp_op = "read"
        elif arg == "--provision-otp":
            otp_op = "provision"
        elif arg == "--reprovision-otp":
            otp_op = "reprovision"
        elif arg == "--lock-otp":
            otp_op = "lock"
        elif arg == "--confirm":
            otp_confirm = True
        elif arg == "--confirm-permanent":
            otp_confirm_permanent = True
        elif arg == "--no-id-check":
            skip_id_check = True
        elif arg in ("--full", "--no-incremental"):
            force_full = True
        elif arg == "--incremental":
            force_full = False
        elif arg == "--verbose":
            verbose = True
        elif arg == "--no-passthrough":
            passthrough = False
        elif arg == "--timestamps":
            timestamps = True
        elif arg == "--freq":
            if i + 1 >= len(args):
                log.error("--freq requires a KHz value"); sys.exit(2)
            try:
                freq_override = int(args[i + 1])
            except ValueError:
                print(f"Error: --freq value must be an integer KHz, got: {args[i+1]}", file=sys.stderr)
                sys.exit(2)
            i += 1
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}", file=sys.stderr)
            print(HELP_TEXT)
            sys.exit(2)
        else:
            elf_path = arg
        i += 1

    if shared_auto and not use_shared:
        print("Error: --shared-auto requires --shared", file=sys.stderr); sys.exit(2)

    connect_under_reset_for_flash = bool(specified_sn)

    if not do_erase and not do_scan and not do_gdb_server and not cleanup_servers_only and not os.path.isfile(elf_path):
        print(f"Error: ELF file not found: {elf_path}", file=sys.stderr); sys.exit(2)

    if do_scan:
        sys.exit(scan_all_probes())

    if do_gdb_server:
        sys.exit(gdb_server_start(mode=gdb_server_mode, serial=specified_sn, freq=freq_override or MAX_SWD_FREQ))

    if cleanup_servers_only:
        run_server_cleanup_step("manual cleanup request (--cleanup-servers-only)")
        sys.exit(0)

    if otp_op is not None:
        if _otp_handler is None:
            log.error("OTP commands not available: no handler registered by the project layer")
            sys.exit(2)
        sn = _resolve_probe_sn(specified_sn, auto_probe, elf_path)
        if sn is None:
            sys.exit(2)
        sys.exit(_otp_handler(otp_op, sn, otp_confirm, otp_confirm_permanent))

    run_server_cleanup_step("startup")

    if auto_probe:
        auto_probe_start = time.monotonic()

        def auto_log(message: str) -> None:
            print(f"[auto-probe +{time.monotonic() - auto_probe_start:0.3f}s] {message}")

        if specified_sn:
            print("Error: --auto-probe and --sn are mutually exclusive", file=sys.stderr); sys.exit(2)
        if do_erase:
            print("Error: --auto-probe is only supported for programming", file=sys.stderr); sys.exit(2)
        elf_mode = elf_build_mode(elf_path)
        if not elf_mode:
            print(f"Error: --auto-probe could not infer build mode from ELF path: {elf_path}", file=sys.stderr)
            sys.exit(2)
        auto_log(f"Looking for a live probe attached to a {elf_mode} board...")
        enum_start = time.monotonic()
        live_probes = find_probes()
        auto_log(f"Probe enumeration finished in {time.monotonic() - enum_start:0.3f}s; found {len(live_probes)} probe(s)")
        if not live_probes:
            print("Error: --auto-probe found no ST-LINK probes", file=sys.stderr); sys.exit(2)

        map_start = time.monotonic()
        pinned_map = get_mode_probe_map()
        auto_log(f"Loaded mode_probe_map in {time.monotonic() - map_start:0.3f}s")
        pinned_sn = pinned_map.get(elf_mode)
        if pinned_sn:
            pinned_probe = next((p for p in live_probes if p.serial == pinned_sn), None)
            if pinned_probe:
                specified_sn = pinned_probe.serial
                connect_under_reset_for_flash = True
                auto_log(f"pinned: mode {elf_mode} -> probe {pinned_probe.last_3} ({pinned_probe.serial})")
                auto_log(f"Selected probe {pinned_probe.last_3} ({specified_sn})")
            else:
                auto_log(f"pinned probe for {elf_mode} not currently connected: {pinned_sn}")
                reset_start = time.monotonic()
                if usb_reset_stlink(pinned_sn):
                    auto_log(f"USB reset succeeded in {time.monotonic() - reset_start:0.3f}s")
                    enum_start = time.monotonic()
                    live_probes = find_probes()
                    auto_log(f"Probe re-enumeration finished in {time.monotonic() - enum_start:0.3f}s; found {len(live_probes)} probe(s)")
                    pinned_probe = next((p for p in live_probes if p.serial == pinned_sn), None)
                    if pinned_probe:
                        specified_sn = pinned_probe.serial
                        connect_under_reset_for_flash = True
                        auto_log(f"Selected probe {pinned_probe.last_3} ({specified_sn})")

        if not specified_sn:
            matches: List[STLinkProbe] = []
            for p in live_probes:
                t_detect = time.monotonic()
                auto_log(f"Checking probe {p.last_3} ({p.serial}) for attached board...")
                board = detect_attached_board(p.serial)
                detect_elapsed = time.monotonic() - t_detect
                if board and board.get("build_mode") == elf_mode:
                    matches.append(p)
                    auto_log(f"match after {detect_elapsed:0.3f}s: probe {p.last_3} -> {board.get('label', board.get('id'))}")
                elif board:
                    auto_log(f"probe {p.last_3} resolved in {detect_elapsed:0.3f}s to {board.get('label', board.get('id'))} [{board.get('build_mode', '?')}]")
                else:
                    auto_log(f"probe {p.last_3} had no detectable board after {detect_elapsed:0.3f}s")
            if not matches:
                print(f"Error: --auto-probe found no live probe attached to a {elf_mode} board", file=sys.stderr); sys.exit(2)
            if len(matches) > 1:
                print(f"Error: --auto-probe found {len(matches)} live probes attached to {elf_mode} boards", file=sys.stderr); sys.exit(2)
            specified_sn = matches[0].serial
            connect_under_reset_for_flash = True
            auto_log(f"Selected probe {matches[0].last_3} ({specified_sn})")

        if shared_auto and specified_sn:
            srv = find_running_shared_server_for_serial(specified_sn)
            if srv:
                auto_log(f"shared-auto: reusing running shared gdb server pid={srv.get('pid')} port={srv.get('port') or '?'}")
            else:
                auto_log("shared-auto: no matching running shared gdb server found")

        if specified_sn and (auto_update_mode_map or mode_probe_auto_update_enabled()):
            try:
                update_mode_probe_map(elf_mode, specified_sn)
            except Exception as exc:
                print(f"[registry] Could not update mode_probe_map: {exc}", file=sys.stderr)

    if shared_auto and program_all:
        print("[flash] shared-auto is ignored with --all")

    if shared_auto and specified_sn and not program_all:
        srv = find_running_shared_server_for_serial(specified_sn)
        if srv:
            print(f"[flash] shared-auto: reusing running shared gdb server pid={srv.get('pid')} port={srv.get('port') or '?'}")

    # Apply per-probe swd_freq from registry if --freq wasn't given explicitly.
    if freq_override is None and specified_sn:
        from .registry import lookup_probe as _lookup_probe
        _pe = _lookup_probe(specified_sn)
        if _pe and _pe.get("swd_freq"):
            freq_override = int(_pe["swd_freq"])
            log.notice("probe %s: using registered swd_freq=%d KHz (capped — check swd_freq in probes.json)", specified_sn[-3:], freq_override)

    common_kwargs = dict(
        shared=use_shared,
        force_full=force_full,
        verbose=verbose,
        passthrough=passthrough,
        timestamps=timestamps,
        freq=freq_override,
        connect_under_reset=connect_under_reset_for_flash,
        no_mode_check=no_mode_check,
    )

    # Fast path: known SN + skip-id-check
    if specified_sn and skip_id_check and not program_all:
        probe = STLinkProbe(specified_sn)
        if do_erase:
            success, _ = erase_device(probe, include_sn=True, shared=use_shared, freq=freq_override, connect_under_reset=connect_under_reset_for_flash)
        else:
            success, _ = program_with_recovery(elf_path, probe, allow_server_kill=True, include_sn=True, **common_kwargs)
        sys.exit(0 if success else 3)

    print("Detecting ST-LINK probes...")
    probes = find_probes()
    if not probes:
        print("Error: No ST-LINK probes detected!", file=sys.stderr); sys.exit(2)

    if not skip_id_check:
        from .programmer import check_probe_device_id
        print("\nChecking connected devices...")
        for probe in probes:
            check_probe_device_id(probe)

    operation = "erase" if do_erase else "program"
    operation_icon = "🗑️ " if do_erase else "🚀"

    if specified_sn:
        probe = next((p for p in probes if p.serial == specified_sn or p.last_3 == specified_sn), None)
        if not probe:
            print(f"Error: Probe with serial {specified_sn} not found", file=sys.stderr); sys.exit(2)
        from .programmer import show_device_info
        show_device_info(probe, is_erase=do_erase)
        if do_erase:
            success, _ = erase_device(probe, include_sn=True, shared=use_shared, freq=freq_override, connect_under_reset=connect_under_reset_for_flash)
        else:
            success, _ = program_with_recovery(elf_path, probe, allow_server_kill=True, include_sn=True, **common_kwargs)
        sys.exit(0 if success else 3)

    if not program_all and len(probes) > 1:
        from .selector import select_probe
        from .programmer import show_device_info
        selected = select_probe(probes, operation)
        if selected is None:
            program_all = True
        else:
            show_device_info(selected, is_erase=do_erase)
            if do_erase:
                success, _ = erase_device(selected, include_sn=False, shared=use_shared, freq=freq_override, connect_under_reset=connect_under_reset_for_flash)
            else:
                success, _ = program_with_recovery(elf_path, selected, allow_server_kill=True, include_sn=False, **common_kwargs)
            sys.exit(0 if success else 3)

    if program_all:
        from .programmer import show_device_info
        operation_verb = "Erasing" if do_erase else "Programming"
        print(f"{operation_icon} {operation_verb} ALL {len(probes)} devices...\n")
        results = []
        total_start = time.time()
        for idx, probe in enumerate(probes, 1):
            print("═" * 55)
            print(f"Device {idx}/{len(probes)}")
            print("═" * 55)
            show_device_info(probe, is_erase=do_erase)
            if do_erase:
                success, elapsed = erase_device(probe, include_sn=True, shared=use_shared, freq=freq_override, connect_under_reset=connect_under_reset_for_flash)
            else:
                success, elapsed = program_with_recovery(elf_path, probe, allow_server_kill=True, include_sn=True, **common_kwargs)
            results.append((probe, success, elapsed))
        total_elapsed = time.time() - total_start
        print("\n" + "═" * 55)
        print(f"📊 {operation.upper()} SUMMARY")
        print("═" * 55)
        successful = sum(1 for _, s, _ in results if s)
        for probe, s, elapsed in results:
            status = "✓ SUCCESS" if s else "✗ FAILED"
            time_str = f"{elapsed:.1f}s" if elapsed > 0 else "N/A"
            print(f"  {status:12} | ...{probe.last_3} | {time_str}")
        print("═" * 55)
        print(f"Total: {successful}/{len(probes)} successful in {total_elapsed:.1f}s")
        print("═" * 55 + "\n")
        sys.exit(0 if successful == len(probes) else 3)

    if len(probes) == 1:
        from .programmer import show_device_info
        probe = probes[0]
        show_device_info(probe, is_erase=do_erase)
        if do_erase:
            success, _ = erase_device(probe, include_sn=False, shared=use_shared, freq=freq_override, connect_under_reset=connect_under_reset_for_flash)
        else:
            success, _ = program_with_recovery(elf_path, probe, allow_server_kill=True, include_sn=False, **common_kwargs)
        sys.exit(0 if success else 3)

    print("Error: Unexpected code path", file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main()
