"""
stlink-org/stlink integration wrapper for stlink-toolkit

This module provides a Python interface to invoke the official stlink tools (st-info, st-flash, st-util)
installed via your system package manager (e.g. dnf).

Project: https://github.com/stlink-org/stlink

Example usage:
    from stlink_toolkit import stlink_wrapper
    stlink_wrapper.st_info()
    stlink_wrapper.st_flash('--help')
    stlink_wrapper.st_util('--version')

You can use this wrapper in your test scripts or as part of your probe/board automation.
"""
import subprocess
import shutil

def _find_tool(tool_name: str) -> str:
    path = shutil.which(tool_name)
    if not path:
        raise FileNotFoundError(f"{tool_name} not found in PATH. Please install stlink via your package manager.")
    return path

def st_info(*args) -> int:
    """Run st-info with optional arguments."""
    cmd = [_find_tool('st-info'), *args]
    print(f"[stlink] Running: {' '.join(cmd)}")
    return subprocess.call(cmd)

def st_flash(*args) -> int:
    """Run st-flash with optional arguments."""
    cmd = [_find_tool('st-flash'), *args]
    print(f"[stlink] Running: {' '.join(cmd)}")
    return subprocess.call(cmd)

def st_util(*args) -> int:
    """Run st-util with optional arguments."""
    cmd = [_find_tool('st-util'), *args]
    print(f"[stlink] Running: {' '.join(cmd)}")
    return subprocess.call(cmd)
