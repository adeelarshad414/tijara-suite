#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB="${DB:-tijara_dev}"
RUN_ID="${TIJARA_PKR_GST_RUN_ID:-pkr-gst-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_DIR="${TIJARA_PKR_GST_EVIDENCE_DIR:-deploy/runtime/pkr-gst-verification/$RUN_ID}"
VERIFY_OUTPUT="$EVIDENCE_DIR/verification-output.log"
SUMMARY_FILE="$EVIDENCE_DIR/summary.md"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$EVIDENCE_DIR"

ENV_FILE_ARGS=()
if [[ -f ".env" ]]; then
    ENV_FILE_ARGS+=(--env-file .env)
elif [[ -f ".env.example" ]]; then
    ENV_FILE_ARGS+=(--env-file .env.example)
fi
if [[ -f "secrets/.env.secrets" ]]; then
    ENV_FILE_ARGS+=(--env-file secrets/.env.secrets)
elif [[ -f "secrets/.env.secrets.example" ]]; then
    ENV_FILE_ARGS+=(--env-file secrets/.env.secrets.example)
fi

verify_status=0
if docker compose "${ENV_FILE_ARGS[@]}" exec -T odoo \
    odoo shell \
    --config="${ODOO_RUNTIME_CONFIG:-/tmp/tijara-odoo.conf}" \
    -d "$DB" \
    < scripts/verify_pkr_gst.py \
    | tee "$VERIFY_OUTPUT"; then
    verify_status=0
else
    verify_status=$?
fi

FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
    echo "# Tijara PKR/GST Verification Evidence"
    echo
    echo "- Run ID: \`$RUN_ID\`"
    echo "- Database: \`$DB\`"
    echo "- Started at: \`$STARTED_AT\`"
    echo "- Finished at: \`$FINISHED_AT\`"
    echo "- Command status: \`$verify_status\`"
    echo "- Verification output: \`$VERIFY_OUTPUT\`"
} > "$SUMMARY_FILE"

exit "$verify_status"
