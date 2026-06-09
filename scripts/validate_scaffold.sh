#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="${1:-$PROJECT_DIR}"
DEFAULT_PYCACHE_ROOT="${TMPDIR:-/tmp}"
DEFAULT_PYCACHE_ROOT="${DEFAULT_PYCACHE_ROOT%/}"
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$DEFAULT_PYCACHE_ROOT/tijara-pycache}"
export PYTHONPYCACHEPREFIX
mkdir -p "$PYTHONPYCACHEPREFIX"

python3 -m compileall -q "$ROOT_DIR/addons" "$ROOT_DIR/hardware-bridge"
python3 -c "from pathlib import Path; import xml.etree.ElementTree as ET; files=list(Path('$ROOT_DIR').rglob('*.xml')); [ET.parse(f) for f in files]; print(f'parsed {len(files)} xml files')"

echo "Tijara scaffold validation passed."
