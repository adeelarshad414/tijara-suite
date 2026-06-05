#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${TIJARA_OPS_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
EVIDENCE_DIR="${TIJARA_OPS_EVIDENCE_DIR:-deploy/runtime/ops-evidence/$RUN_ID}"
SUMMARY_FILE="$EVIDENCE_DIR/summary.md"
STATUS_FILE="$EVIDENCE_DIR/status.tsv"
ENV_FILE="$EVIDENCE_DIR/env-summary.txt"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STRICT="${TIJARA_OPS_STRICT:-0}"

mkdir -p "$EVIDENCE_DIR"
: > "$STATUS_FILE"

requested_checks="${TIJARA_OPS_CHECKS:-monitoring,load,dependency}"
if [[ "$requested_checks" == "full" ]]; then
    requested_checks="monitoring,restore,load,dependency,container"
fi

IFS="," read -r -a checks <<< "$requested_checks"

{
    echo "Tijara staging operations evidence"
    echo "run_id=$RUN_ID"
    echo "checks=$requested_checks"
    echo "strict=$STRICT"
    echo "evidence_dir=$EVIDENCE_DIR"
    echo "started_at=$STARTED_AT"
    echo
    echo "TIJARA_STAGING_BASE_URL=${TIJARA_STAGING_BASE_URL:-http://localhost:8069}"
    echo "TIJARA_HARDWARE_BRIDGE_URL=${TIJARA_HARDWARE_BRIDGE_URL:-http://localhost:9199}"
    echo "TIJARA_PROMETHEUS_URL=${TIJARA_PROMETHEUS_URL:-http://localhost:9090}"
    echo "TIJARA_ALERTMANAGER_URL=${TIJARA_ALERTMANAGER_URL:-http://localhost:9093}"
    echo "TIJARA_GRAFANA_URL=${TIJARA_GRAFANA_URL:-http://localhost:3000}"
    echo "TIJARA_BACKUP_DRILL_FILE=${TIJARA_BACKUP_DRILL_FILE:-<unset>}"
    echo "TIJARA_RESTORE_DRILL_BACKUP=${TIJARA_RESTORE_DRILL_BACKUP:-<unset>}"
    echo "TIJARA_BASE_URL=${TIJARA_BASE_URL:-http://localhost:8069}"
    echo "ODOO_IMAGE=${ODOO_IMAGE:-odoo:19.0}"
    echo "POSTGRES_IMAGE=${POSTGRES_IMAGE:-postgres:16-alpine}"
} > "$ENV_FILE"

record_status() {
    local name="$1"
    local status="$2"
    local exit_code="$3"
    local log_file="$4"
    local message="$5"
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$status" "$exit_code" "$log_file" "$message" >> "$STATUS_FILE"
}

run_command_check() {
    local name="$1"
    local command="$2"
    local log_file="$EVIDENCE_DIR/$name.log"

    set +e
    bash -lc "$command" > "$log_file" 2>&1
    local exit_code=$?
    set -e

    if [[ "$exit_code" -eq 0 ]]; then
        record_status "$name" "passed" "$exit_code" "$log_file" ""
    else
        record_status "$name" "failed" "$exit_code" "$log_file" "command failed"
    fi
}

skip_check() {
    local name="$1"
    local message="$2"
    local log_file="$EVIDENCE_DIR/$name.log"
    echo "$message" > "$log_file"
    if [[ "$STRICT" == "1" ]]; then
        record_status "$name" "failed" "2" "$log_file" "$message"
    else
        record_status "$name" "skipped" "0" "$log_file" "$message"
    fi
}

run_monitoring() {
    run_command_check "monitoring-drill" "python3 scripts/staging_monitoring_drill.py"
}

run_load() {
    if ! command -v k6 >/dev/null 2>&1; then
        skip_check "load-smoke" "k6 is not installed; install k6 or omit load from TIJARA_OPS_CHECKS."
        return
    fi
    run_command_check "load-smoke" "k6 run scripts/load_smoke.k6.js"
}

run_dependency() {
    run_command_check "dependency-scan" "bash scripts/dependency_scan.sh"
}

run_container() {
    if ! command -v trivy >/dev/null 2>&1; then
        skip_check "container-scan" "trivy is not installed; install trivy or omit container from TIJARA_OPS_CHECKS."
        return
    fi
    run_command_check "container-scan" "bash scripts/container_scan.sh"
}

run_restore() {
    local backup_file="${TIJARA_RESTORE_DRILL_BACKUP:-${TIJARA_BACKUP_DRILL_FILE:-}}"
    if [[ -z "$backup_file" ]]; then
        skip_check "restore-drill" "Set TIJARA_RESTORE_DRILL_BACKUP or TIJARA_BACKUP_DRILL_FILE to run restore drill."
        return
    fi
    local quoted_backup
    quoted_backup="$(printf "%q" "$backup_file")"
    run_command_check "restore-drill" "CONFIRM_RESTORE_DRILL=YES bash deploy/postgres/restore-drill.sh $quoted_backup"
}

for check in "${checks[@]}"; do
    normalized="$(echo "$check" | tr '[:upper:]' '[:lower:]' | xargs)"
    case "$normalized" in
        monitoring | monitoring-drill)
            run_monitoring
            ;;
        restore | restore-drill)
            run_restore
            ;;
        load | load-smoke)
            run_load
            ;;
        dependency | dependency-scan)
            run_dependency
            ;;
        container | container-scan)
            run_container
            ;;
        "")
            ;;
        *)
            skip_check "$normalized" "Unknown operations check '$check'."
            ;;
    esac
done

passed_count="$(awk -F '\t' '$2 == "passed" {count++} END {print count + 0}' "$STATUS_FILE")"
failed_count="$(awk -F '\t' '$2 == "failed" {count++} END {print count + 0}' "$STATUS_FILE")"
skipped_count="$(awk -F '\t' '$2 == "skipped" {count++} END {print count + 0}' "$STATUS_FILE")"

overall_status="passed"
if [[ "$failed_count" -gt 0 ]]; then
    overall_status="failed"
elif [[ "$skipped_count" -gt 0 ]]; then
    overall_status="passed-with-skips"
fi

{
    echo "# Tijara Staging Operations Evidence"
    echo
    echo "- Status: $overall_status"
    echo "- Run ID: $RUN_ID"
    echo "- Checks: $requested_checks"
    echo "- Strict: $STRICT"
    echo "- Evidence directory: $EVIDENCE_DIR"
    echo "- Started: $STARTED_AT"
    echo "- Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- Passed: $passed_count"
    echo "- Failed: $failed_count"
    echo "- Skipped: $skipped_count"
    echo
    echo "## Results"
    while IFS=$'\t' read -r name status exit_code log_file message; do
        if [[ -n "$message" ]]; then
            echo "- $name: $status (exit $exit_code) - $message - $log_file"
        else
            echo "- $name: $status (exit $exit_code) - $log_file"
        fi
    done < "$STATUS_FILE"
    echo
    echo "## Evidence Files"
    echo "- Environment summary: $ENV_FILE"
    echo "- Status table: $STATUS_FILE"
} > "$SUMMARY_FILE"

echo "Staging operations evidence written to $EVIDENCE_DIR"

if [[ "$failed_count" -gt 0 ]]; then
    exit 1
fi
