"""Compare flash speed: current toolkit flow vs upstream st-flash.

Runs:
- Toolkit flow via ``python3 -m stlink_toolkit`` (CubeProgrammer-backed incremental logic)
- Upstream ``st-flash`` from stlink-org/stlink

Usage:
    # Cube-only run (default)
    python3 -m stlink_toolkit.flash_speed_compare --sn SERIAL --elf ELF_PATH

    # Include upstream st-flash comparison (explicit opt-in)
    python3 -m stlink_toolkit.flash_speed_compare --sn SERIAL --elf ELF_PATH --with-stflash
"""
import os
import subprocess
import time
import argparse

from .servers import run_server_cleanup_step


def _run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def run_toolkit_flash(serial, elf_path):
    print("\n[stlink-toolkit] Flashing with Python toolkit...")
    cmd = ["python3", "-m", "stlink_toolkit", "--sn", serial, elf_path]
    t0 = time.monotonic()
    proc = _run(cmd, timeout=300)
    elapsed = time.monotonic() - t0
    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr)
    print(f"[stlink-toolkit] Elapsed: {elapsed:.2f}s\n")
    return elapsed, proc.returncode


def run_st_flash(elf_path, address):
    print("[st-flash] Flashing with st-flash (stlink-org)...")
    bin_path = elf_path.replace(".elf", ".bin")
    if not os.path.exists(bin_path) or os.path.getmtime(bin_path) < os.path.getmtime(elf_path):
        print(f"[st-flash] Converting ELF to BIN: {bin_path}")
        subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", elf_path, bin_path])
    cmd = ["st-flash", "write", bin_path, address]
    t0 = time.monotonic()
    proc = _run(cmd, timeout=300)
    elapsed = time.monotonic() - t0
    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr)
    print(f"[st-flash] Elapsed: {elapsed:.2f}s\n")
    return elapsed, proc.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sn", required=True, help="ST-Link serial number")
    parser.add_argument("--elf", required=True, help="Path to ELF file")
    parser.add_argument("--address", default="0x08000000", help="Flash start address for st-flash (default: 0x08000000)")
    parser.add_argument("--with-stflash", action="store_true", help="Also run upstream st-flash benchmark (default: disabled)")
    args = parser.parse_args()

    print("[cleanup] Killing any running GDB/ST-Link servers...")
    run_server_cleanup_step("benchmark startup", serial=args.sn)

    # Keep both runs isolated from stale server state.
    toolkit_time, toolkit_rc = run_toolkit_flash(args.sn, args.elf)
    stflash_time = None
    stflash_rc = None
    if args.with_stflash:
        run_server_cleanup_step("between benchmark runs", serial=args.sn)
        stflash_time, stflash_rc = run_st_flash(args.elf, args.address)
    else:
        print("[st-flash] Skipped (pass --with-stflash to include open-project comparison)")

    print("=== Flash Speed Comparison ===")
    print(f"stlink-toolkit: {toolkit_time:.2f}s (rc={toolkit_rc})")
    if stflash_time is None:
        print("st-flash:       skipped")
        print("[RESULT] Cube/toolkit path executed (default workflow)")
    else:
        print(f"st-flash:       {stflash_time:.2f}s (rc={stflash_rc})")
        if toolkit_time < stflash_time:
            print("[RESULT] stlink-toolkit is faster!")
        elif stflash_time < toolkit_time:
            print("[RESULT] st-flash is faster!")
        else:
            print("[RESULT] Both tools are equally fast.")

if __name__ == "__main__":
    main()
