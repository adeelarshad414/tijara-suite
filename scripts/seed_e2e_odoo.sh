#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB="${DB:-tijara_dev}"
RUN_ID="${TIJARA_E2E_SEED_RUN_ID:-e2e-seed-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_DIR="${TIJARA_E2E_SEED_EVIDENCE_DIR:-deploy/runtime/e2e-seed/$RUN_ID}"
SEED_SCOPE="${TIJARA_E2E_SEED_SCOPE:-full}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SEED_OUTPUT="$EVIDENCE_DIR/seed-output.log"

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

EXEC_ENV_ARGS=()
if [[ -n "${TIJARA_E2E_LOGIN:-}" ]]; then
    EXEC_ENV_ARGS+=(-e "TIJARA_E2E_LOGIN=${TIJARA_E2E_LOGIN}")
fi
if [[ -n "${TIJARA_E2E_PASSWORD:-}" ]]; then
    EXEC_ENV_ARGS+=(-e "TIJARA_E2E_PASSWORD=${TIJARA_E2E_PASSWORD}")
fi

seed_status=0
if docker compose "${ENV_FILE_ARGS[@]}" exec "${EXEC_ENV_ARGS[@]}" -T odoo \
    odoo shell \
    --config="${ODOO_RUNTIME_CONFIG:-/tmp/tijara-odoo.conf}" \
    -d "$DB" \
    < scripts/e2e_seed.py \
    | tee "$SEED_OUTPUT"; then
    seed_status=0
else
    seed_status=$?
fi

password_provided=0
if [[ -n "${TIJARA_E2E_PASSWORD:-}" ]]; then
    password_provided=1
fi

evidence_status=0
python3 scripts/export_e2e_seed_evidence.py \
    --run-id "$RUN_ID" \
    --scope "$SEED_SCOPE" \
    --database "$DB" \
    --base-url "${ODOO_BASE_URL:-}" \
    --seed-output "$SEED_OUTPUT" \
    --output "$EVIDENCE_DIR" \
    --started-at "$STARTED_AT" \
    --command-status "$seed_status" \
    --password-provided "$password_provided" \
    || evidence_status=$?

if [[ "$seed_status" -ne 0 ]]; then
    exit "$seed_status"
fi

exit "$evidence_status"
