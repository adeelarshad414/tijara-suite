#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB="${DB:-tijara_dev}"
CREDENTIALS_CSV="${TIJARA_TEST_CREDENTIALS_CSV:-docs/TEST_CREDENTIALS.csv}"
RUN_ID="${TIJARA_DEMO_USERS_RUN_ID:-demo-users-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_DIR="${TIJARA_DEMO_USERS_EVIDENCE_DIR:-deploy/runtime/demo-users/$RUN_ID}"
SEED_OUTPUT="$EVIDENCE_DIR/seed-output.log"
SUMMARY_FILE="$EVIDENCE_DIR/summary.md"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -f "$CREDENTIALS_CSV" ]]; then
    echo "Missing credentials CSV: $CREDENTIALS_CSV" >&2
    exit 1
fi

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

CREDENTIALS_B64="$(base64 < "$CREDENTIALS_CSV" | tr -d '\n')"

seed_status=0
if docker compose "${ENV_FILE_ARGS[@]}" exec \
    -e "TIJARA_DEMO_USERS_CSV_B64=${CREDENTIALS_B64}" \
    -e "TIJARA_DEMO_USERS_SOURCE=${CREDENTIALS_CSV}" \
    -T odoo \
    odoo shell \
    --config="${ODOO_RUNTIME_CONFIG:-/tmp/tijara-odoo.conf}" \
    -d "$DB" \
    < scripts/seed_demo_users.py \
    | tee "$SEED_OUTPUT"; then
    seed_status=0
else
    seed_status=$?
fi

FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
    echo "# Tijara Demo User Seed Evidence"
    echo
    echo "- Run ID: \`$RUN_ID\`"
    echo "- Database: \`$DB\`"
    echo "- Credentials source: \`$CREDENTIALS_CSV\`"
    echo "- Started at: \`$STARTED_AT\`"
    echo "- Finished at: \`$FINISHED_AT\`"
    echo "- Command status: \`$seed_status\`"
    echo "- Seed output: \`$SEED_OUTPUT\`"
} > "$SUMMARY_FILE"

exit "$seed_status"
