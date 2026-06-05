#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE="${1:-${TIJARA_LOAD_PROFILE:-smoke}}"
RUN_ID="${TIJARA_LOAD_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
OUTPUT_DIR="${TIJARA_LOAD_OUTPUT:-deploy/runtime/load-evidence/$RUN_ID}"
BASE_URL="${TIJARA_BASE_URL:-http://localhost:8069}"
VUS="${TIJARA_LOAD_VUS:-5}"
DURATION="${TIJARA_LOAD_DURATION:-30s}"
STRICT="${TIJARA_LOAD_STRICT:-0}"

case "$PROFILE" in
    smoke | load-smoke)
        PROFILE_NAME="load-smoke"
        K6_SCRIPT="scripts/load_smoke.k6.js"
        ;;
    enterprise | enterprise-surfaces | surfaces)
        PROFILE_NAME="enterprise-surfaces"
        K6_SCRIPT="scripts/load_enterprise_surfaces.k6.js"
        ;;
    *)
        echo "Unknown load profile '$PROFILE'. Use smoke or enterprise-surfaces." >&2
        exit 2
        ;;
esac

mkdir -p "$OUTPUT_DIR"
SUMMARY_JSON="$OUTPUT_DIR/k6-summary.json"
K6_LOG="$OUTPUT_DIR/k6.log"
EXPORT_LOG="$OUTPUT_DIR/load-evidence-export.log"

if ! command -v k6 >/dev/null 2>&1; then
    echo "k6 is not installed; install k6 before running load profiles." > "$K6_LOG"
    K6_EXIT=127
else
    if TIJARA_BASE_URL="$BASE_URL" k6 run --summary-export "$SUMMARY_JSON" "$K6_SCRIPT" > "$K6_LOG" 2>&1; then
        K6_EXIT=0
    else
        K6_EXIT=$?
    fi
fi

export_args=(
    scripts/export_load_evidence.py
    --run-id "$RUN_ID"
    --target-environment "${TIJARA_LOAD_ENVIRONMENT:-staging}"
    --output "$OUTPUT_DIR"
    --profile-name "$PROFILE_NAME"
    --base-url "$BASE_URL"
    --vus "$VUS"
    --duration "$DURATION"
)

if [[ -f "$SUMMARY_JSON" ]]; then
    export_args+=(--summary-json "$SUMMARY_JSON")
fi
if [[ "$STRICT" == "1" ]]; then
    export_args+=(--strict)
fi

if python3 "${export_args[@]}" > "$EXPORT_LOG" 2>&1; then
    EXPORT_EXIT=0
else
    EXPORT_EXIT=$?
fi

{
    echo "Tijara load profile evidence"
    echo "run_id=$RUN_ID"
    echo "profile=$PROFILE_NAME"
    echo "script=$K6_SCRIPT"
    echo "base_url=$BASE_URL"
    echo "vus=$VUS"
    echo "duration=$DURATION"
    echo "strict=$STRICT"
    echo "k6_exit=$K6_EXIT"
    echo "export_exit=$EXPORT_EXIT"
    echo "summary_json=$SUMMARY_JSON"
    echo "output_dir=$OUTPUT_DIR"
} > "$OUTPUT_DIR/profile-run.env"

echo "Load profile evidence written to $OUTPUT_DIR"
echo "profile=$PROFILE_NAME"
echo "k6_exit=$K6_EXIT"
echo "export_exit=$EXPORT_EXIT"

if [[ "$K6_EXIT" -ne 0 ]]; then
    exit "$K6_EXIT"
fi
if [[ "$EXPORT_EXIT" -ne 0 ]]; then
    exit "$EXPORT_EXIT"
fi
