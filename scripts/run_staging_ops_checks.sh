#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${TIJARA_OPS_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
EVIDENCE_DIR="${TIJARA_OPS_EVIDENCE_DIR:-deploy/runtime/ops-evidence/$RUN_ID}"
SUMMARY_FILE="$EVIDENCE_DIR/summary.md"
STATUS_FILE="$EVIDENCE_DIR/status.tsv"
ENV_FILE="$EVIDENCE_DIR/env-summary.txt"
MANIFEST_FILE="$EVIDENCE_DIR/ops-evidence.json"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STRICT="${TIJARA_OPS_STRICT:-0}"
REQUIRED_CHECKS="${TIJARA_OPS_REQUIRED_CHECKS:-}"

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
    echo "required_checks=${REQUIRED_CHECKS:-<none>}"
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
    echo "TIJARA_LOAD_VUS=${TIJARA_LOAD_VUS:-5}"
    echo "TIJARA_LOAD_DURATION=${TIJARA_LOAD_DURATION:-30s}"
    echo "TIJARA_LOAD_MAX_P95_MS=${TIJARA_LOAD_MAX_P95_MS:-1000}"
    echo "TIJARA_LOAD_MAX_FAIL_RATE=${TIJARA_LOAD_MAX_FAIL_RATE:-0.05}"
    echo "TIJARA_LOAD_MIN_CHECKS_RATE=${TIJARA_LOAD_MIN_CHECKS_RATE:-0.95}"
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

canonical_check_name() {
    local normalized="$1"
    case "$normalized" in
        monitoring | monitoring-drill)
            echo "monitoring-drill"
            ;;
        restore | restore-drill)
            echo "restore-drill"
            ;;
        load | load-smoke)
            echo "load-smoke"
            ;;
        dependency | dependency-scan)
            echo "dependency-scan"
            ;;
        container | container-scan)
            echo "container-scan"
            ;;
        *)
            echo "$normalized"
            ;;
    esac
}

require_check_results() {
    local raw_checks="$1"
    local item
    local normalized
    local canonical
    local old_ifs="$IFS"
    [[ -z "$raw_checks" ]] && return 0
    IFS=","
    for item in $raw_checks; do
        normalized="$(echo "$item" | tr '[:upper:]' '[:lower:]' | xargs)"
        [[ -z "$normalized" ]] && continue
        canonical="$(canonical_check_name "$normalized")"
        if ! awk -F '\t' -v name="$canonical" '$1 == name {found=1} END {exit found ? 0 : 1}' "$STATUS_FILE"; then
            record_status "required-$canonical" "failed" "3" "$EVIDENCE_DIR/required-$canonical.log" "Required operations check '$canonical' was not executed."
            echo "Required operations check '$canonical' was not executed." > "$EVIDENCE_DIR/required-$canonical.log"
            continue
        fi
        if ! awk -F '\t' -v name="$canonical" '$1 == name && $2 == "passed" {passed=1} END {exit passed ? 0 : 1}' "$STATUS_FILE"; then
            record_status "required-$canonical" "failed" "4" "$EVIDENCE_DIR/required-$canonical.log" "Required operations check '$canonical' did not pass."
            echo "Required operations check '$canonical' did not pass." > "$EVIDENCE_DIR/required-$canonical.log"
        fi
    done
    IFS="$old_ifs"
}

run_command_check() {
    local name="$1"
    local command="$2"
    local log_file="$EVIDENCE_DIR/$name.log"

    set +e
    bash -c "$command" > "$log_file" 2>&1
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

run_load_evidence_export() {
    local summary_json="$1"
    local combined_log="$2"
    local load_evidence_dir="$EVIDENCE_DIR/load-evidence"
    local load_export_log="$EVIDENCE_DIR/load-evidence.log"
    local base_url="${TIJARA_BASE_URL:-http://localhost:8069}"
    local load_vus="${TIJARA_LOAD_VUS:-5}"
    local load_duration="${TIJARA_LOAD_DURATION:-30s}"
    local args=(
        scripts/export_load_evidence.py
        --run-id "$RUN_ID"
        --target-environment staging
        --output "$load_evidence_dir"
        --base-url "$base_url"
        --vus "$load_vus"
        --duration "$load_duration"
    )

    if [[ -n "$summary_json" ]]; then
        args+=(--summary-json "$summary_json")
    fi
    if [[ "$STRICT" == "1" ]]; then
        args+=(--strict)
    fi

    local evidence_exit=0
    if python3 "${args[@]}" > "$load_export_log" 2>&1; then
        evidence_exit=0
        record_status "load-evidence" "passed" "$evidence_exit" "$load_export_log" "$load_evidence_dir/load-evidence.json"
    else
        evidence_exit=$?
        record_status "load-evidence" "failed" "$evidence_exit" "$load_export_log" "load evidence export failed"
    fi

    {
        echo
        echo "== Load evidence export =="
        cat "$load_export_log"
    } >> "$combined_log"

    return "$evidence_exit"
}

run_load() {
    local log_file="$EVIDENCE_DIR/load-smoke.log"
    local summary_json="$EVIDENCE_DIR/k6-load-summary.json"

    if ! command -v k6 >/dev/null 2>&1; then
        local message="k6 is not installed; install k6 or omit load from TIJARA_OPS_CHECKS."
        echo "$message" > "$log_file"
        if [[ "$STRICT" == "1" ]]; then
            record_status "load-smoke" "failed" "2" "$log_file" "$message"
        else
            record_status "load-smoke" "skipped" "0" "$log_file" "$message"
        fi
        if run_load_evidence_export "" "$log_file"; then
            :
        else
            :
        fi
        return
    fi

    if k6 run --summary-export "$summary_json" scripts/load_smoke.k6.js > "$log_file" 2>&1; then
        record_status "load-smoke" "passed" "0" "$log_file" "$summary_json"
    else
        local exit_code=$?
        record_status "load-smoke" "failed" "$exit_code" "$log_file" "k6 load smoke failed"
    fi

    if run_load_evidence_export "$summary_json" "$log_file"; then
        :
    else
        :
    fi
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

require_check_results "$REQUIRED_CHECKS"

passed_count="$(awk -F '\t' '$2 == "passed" {count++} END {print count + 0}' "$STATUS_FILE")"
failed_count="$(awk -F '\t' '$2 == "failed" {count++} END {print count + 0}' "$STATUS_FILE")"
skipped_count="$(awk -F '\t' '$2 == "skipped" {count++} END {print count + 0}' "$STATUS_FILE")"
warning_count="$(awk -F '\t' '$2 == "warning" {count++} END {print count + 0}' "$STATUS_FILE")"

overall_status="passed"
if [[ "$failed_count" -gt 0 ]]; then
    overall_status="failed"
elif [[ "$skipped_count" -gt 0 || "$warning_count" -gt 0 ]]; then
    overall_status="passed-with-skips"
fi
FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
    echo "# Tijara Staging Operations Evidence"
    echo
    echo "- Status: $overall_status"
    echo "- Run ID: $RUN_ID"
    echo "- Checks: $requested_checks"
    echo "- Strict: $STRICT"
    echo "- Evidence directory: $EVIDENCE_DIR"
    echo "- Started: $STARTED_AT"
    echo "- Finished: $FINISHED_AT"
    echo "- Passed: $passed_count"
    echo "- Failed: $failed_count"
    echo "- Skipped: $skipped_count"
    echo "- Warnings: $warning_count"
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
    echo "- Operations manifest: $MANIFEST_FILE"
    echo "- Environment summary: $ENV_FILE"
    echo "- Status table: $STATUS_FILE"
    if [[ -f "$EVIDENCE_DIR/load-evidence/load-evidence.json" ]]; then
        echo "- Load evidence: $EVIDENCE_DIR/load-evidence/load-evidence.json"
    fi
} > "$SUMMARY_FILE"

python3 - "$RUN_ID" "$requested_checks" "${REQUIRED_CHECKS:-}" "$STRICT" "$STARTED_AT" "$FINISHED_AT" "$EVIDENCE_DIR" "$STATUS_FILE" "$MANIFEST_FILE" "$overall_status" "$passed_count" "$failed_count" "$skipped_count" "$warning_count" <<'PY'
import json
import sys
from pathlib import Path

run_id = sys.argv[1]
requested_checks = [item.strip() for item in sys.argv[2].split(",") if item.strip()]
required_checks = [item.strip() for item in sys.argv[3].split(",") if item.strip()]
strict = sys.argv[4] == "1"
started_at = sys.argv[5]
finished_at = sys.argv[6]
evidence_dir = sys.argv[7]
status_file = Path(sys.argv[8])
manifest_file = Path(sys.argv[9])
overall_status = sys.argv[10]
passed_count = int(sys.argv[11])
failed_count = int(sys.argv[12])
skipped_count = int(sys.argv[13])
warning_count = int(sys.argv[14])

rows = []
if status_file.is_file():
    for line in status_file.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        rows.append(
            {
                "name": parts[0],
                "status": parts[1],
                "exit_code": parts[2],
                "log_file": parts[3],
                "message": parts[4],
            }
        )

if failed_count:
    decision = "failed"
    ci_status = "fail"
elif skipped_count or warning_count:
    decision = "warning"
    ci_status = "pass_with_warnings"
else:
    decision = "passed"
    ci_status = "pass"

payload = {
    "context": {
        "run_id": run_id,
        "requested_checks": requested_checks,
        "required_checks": required_checks,
        "strict": strict,
        "started_at": started_at,
        "finished_at": finished_at,
        "evidence_dir": evidence_dir,
    },
    "decision": decision,
    "ci_status": ci_status,
    "overall_status": overall_status,
    "counts": {
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "warning": warning_count,
    },
    "checks": rows,
    "blockers": [
        "%(name)s: %(message)s" % row for row in rows if row["status"] == "failed"
    ],
    "warnings": [
        "%(name)s: %(message)s" % row
        for row in rows
        if row["status"] in {"skipped", "warning"}
    ],
}
manifest_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "Staging operations evidence written to $EVIDENCE_DIR"
if [[ "$failed_count" -gt 0 ]]; then
    exit 1
fi
