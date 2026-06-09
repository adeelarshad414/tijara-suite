#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage: bash scripts/tijara-production-infra.sh [options]

Generates production DNS, TLS, backup, restore-drill, apply, and rollback
wrappers from tenant ops manifests.

Examples:
  bash scripts/tijara-production-infra.sh --tenant-artifact deploy/runtime/tenants/tijara_customer_001
  bash scripts/tijara-production-infra.sh --mode apply --execute --confirm YES --tenant-artifact deploy/runtime/tenants/tijara_customer_001

All options are passed through to scripts/run_production_infra_automation.py.
Use --help after this wrapper for the Python script's full option list.
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

if [[ "${1:-}" == "-h" || "${1:-}" == "--wrapper-help" ]]; then
    usage
    exit 0
fi

PYTHON="$(python_cmd)"
exec "$PYTHON" "$ROOT_DIR/scripts/run_production_infra_automation.py" "$@"
