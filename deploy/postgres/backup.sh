#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${1:-${DB:-tijara_dev}}"
BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="$BACKUP_DIR/${DB_NAME}-${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

docker compose --env-file .env --env-file secrets/.env.secrets exec -T db \
    pg_dump -U "${POSTGRES_USER:-odoo}" -Fc "$DB_NAME" > "$OUTPUT_FILE"

echo "PostgreSQL backup written to $OUTPUT_FILE"
