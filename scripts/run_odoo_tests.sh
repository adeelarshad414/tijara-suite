#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEST_DB="${TEST_DB:-tijara_test}"
MODULES="${TIJARA_TEST_MODULES:-tijara_base,tijara_retail_core,tijara_inventory_intelligence,tijara_pos_pk,tijara_saas_control,tijara_pos_experience,tijara_analytics,tijara_vertical_pharmacy,tijara_vertical_restaurant,tijara_vertical_garments,tijara_vertical_electronics,tijara_vertical_cloth,tijara_vertical_superstore,tijara_vertical_grocery,tijara_vertical_bakery}"
TEST_TAGS="${TIJARA_TEST_TAGS:-/tijara_saas_control,/tijara_pos_pk,/tijara_pos_experience,/tijara_analytics}"

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

docker compose "${ENV_FILE_ARGS[@]}" run --rm odoo bash /usr/local/bin/tijara-start-odoo \
    -d "$TEST_DB" \
    -i "$MODULES" \
    --without-demo \
    --test-enable \
    --test-tags "$TEST_TAGS" \
    --stop-after-init

