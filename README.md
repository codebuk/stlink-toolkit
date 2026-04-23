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
