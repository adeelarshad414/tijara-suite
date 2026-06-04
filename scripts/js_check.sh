#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
found=0

while IFS= read -r -d '' file; do
    found=1
    node --check "$file"
done < <(
    find "$ROOT_DIR/addons" "$ROOT_DIR/tests" -type f \( -name "*.js" -o -name "*.mjs" \) -print0 2>/dev/null
    if [[ -f "$ROOT_DIR/playwright.config.mjs" ]]; then
        printf '%s\0' "$ROOT_DIR/playwright.config.mjs"
    fi
)

if [[ "$found" == "0" ]]; then
    echo "No JavaScript files found."
else
    echo "Tijara JavaScript syntax checks passed."
fi
