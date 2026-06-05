#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEST_DB="${TEST_DB:-tijara_test}"
MODULES="${TIJARA_TEST_MODULES:-tijara_base,tijara_retail_core,tijara_inventory_intelligence,tijara_pos_pk,tijara_saas_control,tijara_pos_experience,tijara_analytics,tijara_vertical_pharmacy,tijara_vertical_restaurant,tijara_vertical_garments,tijara_vertical_electronics,tijara_vertical_cloth,tijara_vertical_superstore,tijara_vertical_grocery,tijara_vertical_bakery}"
TEST_TAGS="${TIJARA_TEST_TAGS:-/tijara_saas_control,/tijara_retail_core,/tijara_pos_pk,/tijara_pos_experience,/tijara_analytics}"

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

if [[ "${TIJARA_SKIP_DB_PREFLIGHT:-0}" != "1" ]]; then
    echo "Checking Odoo database credentials..."
    if ! docker compose "${ENV_FILE_ARGS[@]}" run --rm --entrypoint python3 odoo - <<'PY'; then
import os
import sys

import psycopg2


host = os.environ.get("ODOO_DB_HOST") or os.environ.get("HOST") or "db"
port = int(os.environ.get("ODOO_DB_PORT") or "5432")
user = os.environ.get("ODOO_DB_USER") or os.environ.get("USER") or "odoo"
password = os.environ.get("ODOO_DB_PASSWORD") or os.environ.get("PASSWORD") or ""
database = os.environ.get("POSTGRES_DB") or "postgres"

try:
    connection = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=database,
        connect_timeout=10,
    )
except Exception as error:
    print(
        "Could not authenticate to PostgreSQL as %s against %s:%s/%s."
        % (user, host, port, database),
        file=sys.stderr,
    )
    print(
        "Verify POSTGRES_PASSWORD and ODOO_DB_PASSWORD match the active database password. "
        "If the password changed after the Docker volume was created, rotate it inside "
        "Postgres or intentionally recreate the local db volume.",
        file=sys.stderr,
    )
    print("Driver error: %s" % error.__class__.__name__, file=sys.stderr)
    sys.exit(1)
else:
    connection.close()
    print("Odoo database credential preflight passed.")
PY
        echo "Odoo test database preflight failed; set TIJARA_SKIP_DB_PREFLIGHT=1 only for deliberate diagnostics." >&2
        exit 1
    fi
fi

docker compose "${ENV_FILE_ARGS[@]}" run --rm odoo bash /usr/local/bin/tijara-start-odoo \
    -d "$TEST_DB" \
    -i "$MODULES" \
    --without-demo \
    --test-enable \
    --test-tags "$TEST_TAGS" \
    --stop-after-init
