# stlink-toolkit

Reusable Python helpers for ST-Link workflows.

## Install Dependencies

Preferred on Fedora (system Python packages via dnf):

```bash
sudo dnf install -y python3 python3-psutil python3-pyusb
```

Or run the helper script:

```bash
bash scripts/install-deps-fedora.sh
```

Fallback (any distro, pip):

```bash
python3 -m pip install --upgrade psutil pyusb
```

The toolkit fails fast when required support packages are missing.

## What it provides
- Probe registry helpers (`registry.py`)
- USB probe enumeration and reset (`usb.py`)
- Stale GDB server cleanup (`servers.py`)
- Optional ELF size logging (`sizes.py`)
- VS Code extension disable/re-enable around probe use (`extensions.py`)

## Generic by default
This package does not infer device mode from binary/ELF naming.
If your app needs build modes (`PDM`, `CON`, etc.), pass mode explicitly in app-level logic.

## Quick start
```python
from stlink_toolkit import configure_registry, find_probes, run_server_cleanup_step

configure_registry("./probes.json")
run_server_cleanup_step("startup")
probes = find_probes()
```

## Notes
- `find_probes()` works from USB/sysfs alone.
- Fallback to programmer probe listing is optional via `find_probes(list_command=[...])`.
- Registry path is configurable via `configure_registry(path)`.

## CLI
See [HELP.txt](HELP.txt) for a quick command reference.

Create or update a local registry template and auto-add currently connected probes:

```bash
stlink-toolkit init-registry --path probes.json
```

If `--path` is omitted, it defaults to `probes.json` in the current directory.

Create a deterministic dummy C source and corresponding ELF fixture:

```bash
stlink-toolkit create-dummy-elf --out-dir test-assets/dummy-elf --name dummy_zero
```

Defaults are `--out-dir test-assets/dummy-elf` and `--name dummy_zero`.

List VCP serial ports and map them to detected ST-Link probe identifiers:

```bash
stlink-toolkit list-vcps
stlink-toolkit list-vcps --json
```

List probes only (compact):

```bash
stlink-toolkit list-probes
```

Add optional VCP lines or tree view under each probe:

```bash
stlink-toolkit list-probes --with-vcps
stlink-toolkit list-probes --tree
```

## VS Code extension management

`extensions.py` temporarily disables ST debugging extensions before any probe
operation and re-enables them afterwards.  This prevents VS Code's debug
adapters from grabbing the ST-Link while a flash or cpuid is in progress.

Extensions are disabled by writing directly to VS Code's SQLite state database
(`~/.config/Code/User/globalStorage/state.vscdb`) — they remain installed and
are restored automatically.  VS Code must be restarted / the extension host
reloaded for the change to become visible, but the DB write is instant and
safe to do while VS Code is running.

### What is disabled

The default set (`ST_DEBUG_EXTENSIONS` / `DEFAULT_ST_EXTENSION_IDS`) covers:

```
stmicroelectronics.stm32-vscode-extension
stmicroelectronics.stm32cube-ide-debug-core
stmicroelectronics.stm32cube-ide-debug-generic-gdbserver
stmicroelectronics.stm32cube-ide-debug-stlink-gdbserver
stmicroelectronics.stm32cube-ide-registers
stmicroelectronics.stm32cube-ide-rtos
stmicroelectronics.stm32cube-ide-debug-jlink-gdbserver
eclipse-cdt.memory-inspector
mcu-debug.memory-view
mcu-debug.debug-tracker-vscode
mcu-debug.rtos-views
mcu-debug.peripheral-viewer
marus25.cortex-debug
ms-vscode.vscode-embedded-tools
```

Any extension from this list that is not installed on the current machine is
silently skipped.

### Where the toggle happens

`usb_reset_stlink()` and `reset_detected_stlink_usb_devices()` in `usb.py`
call `disable_extensions_for_flash()` before touching the probe and
`enable_extensions_after_flash()` in a `finally` block, so re-enable is
guaranteed even if the operation raises.

The flash / cpuid / GDB-server dispatch (`cli_main`, `configure_programmer`)
lives in the consuming project (e.g. `l8-427/scripts/awto.py`).  That project
must also wrap its programmer subprocess with the same two calls — see
**Integration** below.

### Integration in the consuming project

```python
from stlink_toolkit import disable_extensions_for_flash, enable_extensions_after_flash

disable_extensions_for_flash()
try:
    # run_programmer / cpuid / gdb-server subprocess here
    ...
finally:
    enable_extensions_after_flash()
```

Both functions log every action with the `[flash][step]` prefix so output is
consistent with the rest of the toolkit's flash step logging.

### CLI

Disable or re-enable manually (useful for debugging):

```bash
stlink-toolkit ext-disable
stlink-toolkit ext-enable

# Target a specific extension only:
stlink-toolkit ext-disable --ext marus25.cortex-debug
stlink-toolkit ext-enable  --ext marus25.cortex-debug
```
