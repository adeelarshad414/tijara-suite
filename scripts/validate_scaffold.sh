#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="${1:-$PROJECT_DIR}"
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/tijara-pycache}"
export PYTHONPYCACHEPREFIX

python3 -m compileall -q "$ROOT_DIR/addons" "$ROOT_DIR/hardware-bridge"
python3 -c "from pathlib import Path; import xml.etree.ElementTree as ET; files=list(Path('$ROOT_DIR').rglob('*.xml')); [ET.parse(f) for f in files]; print(f'parsed {len(files)} xml files')"

echo "Tijara scaffold validation passed."
