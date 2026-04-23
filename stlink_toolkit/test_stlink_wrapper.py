"""
Test script for stlink_wrapper integration with stlink-org/stlink tools.

This script will run basic checks to verify that st-info, st-flash, and st-util
are installed and callable via the wrapper. It will print results to stdout.

Requires: stlink tools installed (e.g. via dnf: sudo dnf install stlink-tools)
"""
from stlink_toolkit import stlink_wrapper

print("Testing st-info --version:")
stlink_wrapper.st_info('--version')

print("\nTesting st-flash --version:")
stlink_wrapper.st_flash('--version')

print("\nTesting st-util --version:")
stlink_wrapper.st_util('--version')

print("\nAll stlink tool invocations completed.")
