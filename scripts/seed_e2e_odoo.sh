#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB="${DB:-tijara_dev}"

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

docker compose "${ENV_FILE_ARGS[@]}" exec "${EXEC_ENV_ARGS[@]}" -T odoo \
    odoo shell \
    --config="${ODOO_RUNTIME_CONFIG:-/tmp/tijara-odoo.conf}" \
    -d "$DB" \
    < scripts/e2e_seed.py
