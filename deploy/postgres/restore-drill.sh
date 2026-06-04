#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: deploy/postgres/restore-drill.sh <backup.sql|backup.dump>" >&2
    exit 1
fi

if [[ "${CONFIRM_RESTORE_DRILL:-}" != "YES" ]]; then
    echo "Set CONFIRM_RESTORE_DRILL=YES to create and drop a temporary restore-drill database." >&2
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

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

DB_USER="${POSTGRES_USER:-odoo}"
DRILL_DB="tijara_restore_drill_$(date +%Y%m%d%H%M%S)"

cleanup() {
    docker compose "${ENV_FILE_ARGS[@]}" exec -T db dropdb -U "$DB_USER" --if-exists "$DRILL_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Creating temporary restore database $DRILL_DB..."
docker compose "${ENV_FILE_ARGS[@]}" exec -T db createdb -U "$DB_USER" "$DRILL_DB"

case "$BACKUP_FILE" in
    *.sql)
        docker compose "${ENV_FILE_ARGS[@]}" exec -T db psql -U "$DB_USER" -d "$DRILL_DB" < "$BACKUP_FILE"
        ;;
    *)
        docker compose "${ENV_FILE_ARGS[@]}" exec -T db pg_restore -U "$DB_USER" -d "$DRILL_DB" --no-owner --no-acl < "$BACKUP_FILE"
        ;;
esac

docker compose "${ENV_FILE_ARGS[@]}" exec -T db psql -U "$DB_USER" -d "$DRILL_DB" -c "SELECT current_database(), now();"
echo "Restore drill passed for $BACKUP_FILE. Temporary database will be dropped."

