#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  bash deploy/production-infra/runners/postgres-backup-runner.sh backup --database tijara_customer_001 --retention-days 30
  bash deploy/production-infra/runners/postgres-backup-runner.sh restore-drill --database tijara_customer_001 --backup-ref deploy/runtime/backups/file.dump

Real backup or restore-drill execution requires CONFIRM_PROVIDER_ACTION=YES.
Without that confirmation this script prints a dry-run plan only.
USAGE
}

ACTION="${1:-}"
if [[ -z "$ACTION" || "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi
shift

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DATABASE=""
RETENTION_DAYS="30"
BACKUP_REF=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --database) DATABASE="${2:-}"; shift 2 ;;
        --retention-days) RETENTION_DAYS="${2:-}"; shift 2 ;;
        --backup-ref) BACKUP_REF="${2:-}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

require_value() {
    local name="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        echo "$name is required." >&2
        exit 2
    fi
}

require_value "--database" "$DATABASE"

CONFIRMED="${CONFIRM_PROVIDER_ACTION:-NO}"
if [[ "$CONFIRMED" != "YES" ]]; then
    echo "[dry-run] postgres action=$ACTION database=$DATABASE retention_days=$RETENTION_DAYS backup_ref=${BACKUP_REF:-operator-selected-backup}"
    exit 0
fi

cd "$ROOT_DIR"

case "$ACTION" in
    backup)
        bash deploy/postgres/backup.sh "$DATABASE"
        ;;
    restore-drill)
        require_value "--backup-ref" "$BACKUP_REF"
        if [[ ! -f "$BACKUP_REF" ]]; then
            echo "Restore drill backup artifact not found: $BACKUP_REF" >&2
            exit 2
        fi
        CONFIRM_RESTORE_DRILL=YES bash deploy/postgres/restore-drill.sh "$BACKUP_REF"
        ;;
    *)
        echo "Unknown action: $ACTION" >&2
        usage >&2
        exit 2
        ;;
esac
