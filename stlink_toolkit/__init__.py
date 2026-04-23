"""stlink_toolkit - reusable ST-Link probe / STM32CubeProgrammer helpers.

Modules:
- registry: probes.json management
- usb: probe enumeration + USB reset
- servers: stale gdbserver process detection/cleanup
- sizes: ELF section size logging
- programmer: cube programmer wrapper, programming/erase/recovery
- selector: interactive multi-probe selection (LED cycling)
- gdb_server: ST-Link GDB server launcher
- cli: argparse-style command-line entrypoint
"""

from importlib.util import find_spec


def _assert_support_packages() -> None:
    missing = []
    if find_spec("psutil") is None:
        missing.append("psutil")
    if find_spec("usb.core") is None:
        missing.append("pyusb")
    if missing:
        pkgs = ", ".join(sorted(missing))
        raise RuntimeError(
            "Missing required support package(s): "
            f"{pkgs}. Install with Fedora dnf: "
            "sudo dnf install -y python3-psutil python3-pyusb "
            "or with pip: python3 -m pip install psutil pyusb"
        )


_assert_support_packages()

from .registry import configure as configure_registry
from .registry import (
    get_mode_probe_map,
    lookup_board,
    lookup_probe,
    mode_probe_auto_update_enabled,
    update_mode_probe_map,
)
from .servers import (
    find_running_shared_server_for_serial,
    kill_stale_servers,
    run_server_cleanup_step,
)
from .sizes import configure as configure_sizes
from .sizes import log_build_size
from .usb import (
    STLINK_PIDS,
    STLINK_VID,
    STLinkProbe,
    find_probes,
    reset_detected_stlink_usb_devices,
    usb_reset_stlink,
)
from .programmer import (
    FALLBACK_SWD_FREQ,
    MAX_SWD_FREQ,
    PROG,
    PROG_CMD,
    check_elf_matches_board,
    check_probe_device_id,
    configure as configure_programmer,
    detect_attached_board,
    elf_build_mode,
    erase_device,
    erase_sector0,
    is_expected_device,
    print_board_info,
    program_device,
    program_with_recovery,
    read_cpu_serial,
    register_new_probe,
    scan_all_probes,
    show_device_info,
)
from . import log
from .extensions import (
    DEFAULT_ST_EXTENSION_IDS,
    ST_DEBUG_EXTENSIONS,
    disable_extensions,
    disable_extensions_for_flash,
    enable_extensions,
    enable_extensions_after_flash,
    list_installed_extensions,
)
from .selector import flash_led_cycle, select_probe
from .gdb_server import gdb_server_start
from .cli import main as cli_main

__all__ = [
    "FALLBACK_SWD_FREQ",
    "MAX_SWD_FREQ",
    "PROG",
    "PROG_CMD",
    "STLINK_PIDS",
    "STLINK_VID",
    "STLinkProbe",
    "check_elf_matches_board",
    "check_probe_device_id",
    "cli_main",
    "configure_programmer",
    "configure_registry",
    "configure_sizes",
    "DEFAULT_ST_EXTENSION_IDS",
    "ST_DEBUG_EXTENSIONS",
    "detect_attached_board",
    "disable_extensions",
    "disable_extensions_for_flash",
    "enable_extensions",
    "enable_extensions_after_flash",
    "list_installed_extensions",

    "elf_build_mode",
    "erase_device",
    "erase_sector0",
    "find_probes",
    "find_running_shared_server_for_serial",
    "flash_led_cycle",
    "gdb_server_start",
    "get_mode_probe_map",
    "is_expected_device",
    "kill_stale_servers",
    "log",
    "log_build_size",
    "lookup_board",
    "lookup_probe",
    "mode_probe_auto_update_enabled",
    "print_board_info",
    "program_device",
    "program_with_recovery",
    "read_cpu_serial",
    "register_new_probe",
    "reset_detected_stlink_usb_devices",
    "run_server_cleanup_step",
    "scan_all_probes",
    "select_probe",
    "show_device_info",
    "update_mode_probe_map",
    "usb_reset_stlink",
]
