#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if find "$ROOT_DIR/secrets" -type f ! -name "*.example" 2>/dev/null | grep -q .; then
    echo "Found non-example files under secrets/. Keep real secrets out of the repo." >&2
    exit 1
fi

if find "$ROOT_DIR" -type d -name "__pycache__" -print | grep -q .; then
    echo "Found __pycache__ build artifacts. Remove them before committing." >&2
    exit 1
fi

if grep -R "odoo_enterprise\\|enterprise/addons" "$ROOT_DIR/addons" "$ROOT_DIR/docker-compose.yml" >/dev/null 2>&1; then
    echo "Found an Odoo Enterprise reference in the open-source core." >&2
    exit 1
fi

if grep -R "replace-with-long-random" "$ROOT_DIR" \
    --exclude-dir=.git \
    --exclude="*.example" \
    --exclude=".env.example" \
    --exclude="security_audit.sh" >/dev/null 2>&1; then
    echo "Placeholder secrets appear outside example files." >&2
    exit 1
fi

echo "Tijara security audit baseline passed."
