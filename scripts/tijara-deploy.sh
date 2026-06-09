#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage: bash scripts/tijara-deploy.sh [options]

Deploys/hosts Tijara Suite through the Python hosting manager.

Options:
  --environment NAME         development, staging, or production
  --public-url URL           Set TIJARA_PUBLIC_URL
  --domain DOMAIN            Set production-style https://DOMAIN defaults
  --production               Apply production defaults and block placeholders
  --generate-secrets         Generate local random placeholder replacements
  --allow-placeholders       Allow placeholders even with --production
  --hardware, --with-hardware
                             Start the hardware bridge profile
  --monitoring, --with-monitoring
                             Start the monitoring profile
  --all, --all-profiles      Start every optional profile
  --pull, --no-pull          Pull images before startup (default: pull)
  --build                    Build local services before startup
  --install-suite            Install Tijara modules after startup
  --seed-demo                Seed demo POS data after startup
  --db NAME                  Odoo database for install/seed (default: tijara_dev)
  --host-label HOST          Host label printed in endpoint summary
  --dry-run                  Print actions without changing files/services
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
ARGS=("--root" "$ROOT_DIR" "deploy")

while [ "$#" -gt 0 ]; do
    case "$1" in
        --environment|--public-url|--domain|--db|--host-label)
            opt="$1"
            shift
            [ "$#" -gt 0 ] || { echo "$opt requires a value" >&2; exit 2; }
            ARGS+=("$opt" "$1")
            ;;
        --production|--generate-secrets|--allow-placeholders|--build|--install-suite|--seed-demo|--dry-run)
            ARGS+=("$1")
            ;;
        --hardware|--with-hardware)
            ARGS+=("--with-hardware")
            ;;
        --monitoring|--with-monitoring)
            ARGS+=("--with-monitoring")
            ;;
        --all|--all-profiles)
            ARGS+=("--all-profiles")
            ;;
        --pull|--no-pull)
            ARGS+=("$1")
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

exec "$PYTHON" "$ROOT_DIR/scripts/tijara_host.py" "${ARGS[@]}"
