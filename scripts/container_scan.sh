#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v trivy >/dev/null 2>&1; then
    echo "trivy is required for container/config scanning. Install it before running this production check." >&2
    exit 127
fi

trivy config --severity HIGH,CRITICAL --exit-code 1 .
trivy image --severity HIGH,CRITICAL --exit-code 1 "${ODOO_IMAGE:-odoo:19.0}"
trivy image --severity HIGH,CRITICAL --exit-code 1 "${POSTGRES_IMAGE:-postgres:16-alpine}"

