"""stlink_toolkit - reusable ST-Link probe helpers.

Modules:
- registry: probes.json management
- usb: USB probe enumeration and reset helpers
- servers: stale gdbserver process detection/cleanup
- sizes: optional ELF section size logging utilities
"""

from importlib.util import find_spec


def _assert_support_packages() -> None:
    """Fail fast when required runtime dependencies are missing."""
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
from .registry import get_mode_probe_map, lookup_board, lookup_probe, mode_probe_auto_update_enabled, update_mode_probe_map
from .servers import find_running_shared_server_for_serial, kill_stale_servers, run_server_cleanup_step
from .sizes import configure as configure_sizes, log_build_size
from .usb import STLINK_PIDS, STLINK_VID, STLinkProbe, find_probes, reset_detected_stlink_usb_devices, usb_reset_stlink

__all__ = [
    "STLINK_PIDS",
    "STLINK_VID",
    "STLinkProbe",
    "configure_registry",
    "configure_sizes",
    "find_probes",
    "find_running_shared_server_for_serial",
    "get_mode_probe_map",
    "kill_stale_servers",
    "log_build_size",
    "lookup_board",
    "lookup_probe",
    "mode_probe_auto_update_enabled",
    "reset_detected_stlink_usb_devices",
    "run_server_cleanup_step",
    "update_mode_probe_map",
    "usb_reset_stlink",
]
