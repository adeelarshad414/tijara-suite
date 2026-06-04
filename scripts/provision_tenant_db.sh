#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
    cat <<'USAGE'
Usage:
  scripts/provision_tenant_db.sh <tenant_database> [tenant_name]

Environment:
  TIJARA_PROVISION_MODULES  Comma-separated module list to install.
  TIJARA_WITHOUT_DEMO      Defaults to True.

This creates or updates an isolated Odoo tenant database by running the Tijara
module install command inside the open-source Odoo container.
USAGE
}

DB_NAME="${1:-}"
TENANT_NAME="${2:-$DB_NAME}"
if [[ -z "$DB_NAME" || "$DB_NAME" == "-h" || "$DB_NAME" == "--help" ]]; then
    usage
    exit 1
fi

if [[ ! "$DB_NAME" =~ ^[a-zA-Z0-9_]+$ ]]; then
    echo "Tenant database must use only letters, numbers, and underscores." >&2
    exit 1
fi

case "$DB_NAME" in
    postgres|template0|template1)
        echo "Refusing to provision reserved database name: $DB_NAME" >&2
        exit 1
        ;;
esac

MODULES="${TIJARA_PROVISION_MODULES:-tijara_base,tijara_retail_core,tijara_inventory_intelligence,tijara_pos_pk,tijara_saas_control,tijara_pos_experience,tijara_analytics,tijara_vertical_pharmacy,tijara_vertical_restaurant,tijara_vertical_garments,tijara_vertical_electronics,tijara_vertical_cloth,tijara_vertical_superstore,tijara_vertical_grocery,tijara_vertical_bakery}"
WITHOUT_DEMO="${TIJARA_WITHOUT_DEMO:-True}"

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

echo "Provisioning tenant '$TENANT_NAME' into database '$DB_NAME'..."
docker compose "${ENV_FILE_ARGS[@]}" run --rm odoo bash /usr/local/bin/tijara-start-odoo \
    -d "$DB_NAME" \
    -i "$MODULES" \
    --without-demo="$WITHOUT_DEMO" \
    --stop-after-init

echo "Tenant database provisioned. Mark the matching Tijara provisioning request as provisioned in SaaS Admin."

