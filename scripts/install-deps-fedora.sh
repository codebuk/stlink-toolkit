#!/usr/bin/env bash
set -euo pipefail

if ! command -v dnf >/dev/null 2>&1; then
  echo "This installer targets Fedora (dnf not found)." >&2
  echo "Use pip fallback instead:" >&2
  echo "  python3 -m pip install --upgrade psutil pyusb" >&2
  exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

$SUDO dnf install -y python3 python3-psutil python3-pyusb

echo "Installed dependencies with dnf."
echo "pip fallback (if needed): python3 -m pip install --upgrade psutil pyusb"
