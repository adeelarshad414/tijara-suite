#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage: bash scripts/tijara-start.sh [options]

Starts Tijara Suite services through the Python service manager.

Options:
  --all, --all-profiles      Start hardware and monitoring profiles too
  --hardware, --with-hardware
                             Start the hardware bridge profile
  --monitoring, --with-monitoring
                             Start the monitoring profile
  --install-suite            Install Tijara modules after startup
  --seed-demo                Seed demo POS data after startup
  --db NAME                  Odoo database for install/seed (default: tijara_dev)
  --no-wait                  Do not wait for the Odoo login route
  --timeout SECONDS          Odoo wait timeout (default: Python manager default)
  --dry-run                  Print actions without starting services
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
ARGS=("--root" "$ROOT_DIR" "start")

while [ "$#" -gt 0 ]; do
    case "$1" in
        --all|--all-profiles)
            ARGS+=("--all-profiles")
            ;;
        --hardware|--with-hardware)
            ARGS+=("--with-hardware")
            ;;
        --monitoring|--with-monitoring)
            ARGS+=("--with-monitoring")
            ;;
        --install-suite)
            ARGS+=("--install-suite")
            ;;
        --seed-demo)
            ARGS+=("--seed-demo")
            ;;
        --db)
            shift
            [ "$#" -gt 0 ] || { echo "--db requires a value" >&2; exit 2; }
            ARGS+=("--db" "$1")
            ;;
        --no-wait)
            ARGS+=("--no-wait")
            ;;
        --timeout)
            shift
            [ "$#" -gt 0 ] || { echo "--timeout requires a value" >&2; exit 2; }
            ARGS+=("--timeout" "$1")
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
