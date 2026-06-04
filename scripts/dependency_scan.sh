#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v npm >/dev/null 2>&1 && [[ -f package.json ]]; then
    npm audit --audit-level=high
fi

if command -v pip-audit >/dev/null 2>&1; then
    pip-audit --strict || exit 1
else
    echo "pip-audit not installed; skipping Python dependency CVE scan." >&2
fi

