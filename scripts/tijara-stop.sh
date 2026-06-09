#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage: bash scripts/tijara-stop.sh [options]

Stops Tijara Suite services through the Python service manager.

Options:
  --force-kill-ports         Kill any process still using known Tijara ports
  --dry-run                  Print actions without stopping services
  -h, --help                 Show this help
USAGE
}

python_cmd() {
    if command -v python3 >/dev/null 2>&1; then
        printf '%s\n' "python3"
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        printf '%s\n' "python"
        return 0
    fi
    echo "python3 or python is required." >&2
    exit 1
}

PYTHON="$(python_cmd)"
ARGS=("--root" "$ROOT_DIR" "stop")

while [ "$#" -gt 0 ]; do
    case "$1" in
        --force-kill-ports)
            ARGS+=("--force-kill-ports")
            ;;
        --dry-run)
            ARGS+=("--dry-run")
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

exec "$PYTHON" "$ROOT_DIR/scripts/tijara_services.py" "${ARGS[@]}"
