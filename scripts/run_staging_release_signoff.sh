#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${TIJARA_STAGING_RELEASE_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
RUNTIME_ROOT="${TIJARA_STAGING_RELEASE_RUNTIME_ROOT:-deploy/runtime}"
ORCH_DIR="${TIJARA_STAGING_RELEASE_EVIDENCE_DIR:-$RUNTIME_ROOT/staging-release/$RUN_ID}"
RELEASE_DIR="${TIJARA_RELEASE_EVIDENCE_DIR:-$RUNTIME_ROOT/release-evidence/$RUN_ID}"
E2E_DIR="${TIJARA_E2E_EVIDENCE_DIR:-$RUNTIME_ROOT/e2e-evidence/$RUN_ID}"
OPS_DIR="${TIJARA_OPS_EVIDENCE_DIR:-$RUNTIME_ROOT/ops-evidence/$RUN_ID}"
SIGNOFF_DIR="${TIJARA_SIGNOFF_OUTPUT:-$RUNTIME_ROOT/signoff-packages/$RUN_ID}"
READINESS_FILE="$SIGNOFF_DIR/release-readiness.json"
SUMMARY_FILE="$ORCH_DIR/summary.md"
STATUS_FILE="$ORCH_DIR/status.tsv"
ENV_FILE="$ORCH_DIR/env-summary.txt"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

RELEASE_CHECKS="${TIJARA_STAGING_RELEASE_CHECKS:-full}"
SIGNOFF_ENVIRONMENT="${TIJARA_SIGNOFF_ENVIRONMENT:-staging}"
REQUIRED_GROUPS="${TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS:-release,e2e,ops}"
STRICT_REQUIRED="${TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE:-1}"
FAIL_ON_WARNING="${TIJARA_STAGING_RELEASE_FAIL_ON_WARNING:-${TIJARA_RELEASE_FAIL_ON_WARNING:-1}}"

mkdir -p "$ORCH_DIR"
: > "$STATUS_FILE"

{
    echo "Tijara staging release sign-off"
    echo "run_id=$RUN_ID"
    echo "runtime_root=$RUNTIME_ROOT"
    echo "orchestration_dir=$ORCH_DIR"
    echo "release_evidence_dir=$RELEASE_DIR"
    echo "e2e_evidence_dir=$E2E_DIR"
    echo "ops_evidence_dir=$OPS_DIR"
    echo "signoff_dir=$SIGNOFF_DIR"
    echo "readiness_file=$READINESS_FILE"
    echo "started_at=$STARTED_AT"
    echo "release_checks=$RELEASE_CHECKS"
    echo "required_evidence_groups=$REQUIRED_GROUPS"
    echo "strict_required_evidence=$STRICT_REQUIRED"
    echo "fail_on_warning=$FAIL_ON_WARNING"
    echo
    echo "ODOO_BASE_URL=${ODOO_BASE_URL:-<unset>}"
    echo "ODOO_DATABASE=${ODOO_DATABASE:-<unset>}"
    echo "ODOO_USERNAME=${ODOO_USERNAME:+<set>}"
    echo "TIJARA_E2E_SCOPE=${TIJARA_E2E_SCOPE:-full}"
    echo "TIJARA_OPS_CHECKS=${TIJARA_OPS_CHECKS:-full}"
    echo "TIJARA_OPS_STRICT=${TIJARA_OPS_STRICT:-<unset>}"
    echo "TIJARA_RESTORE_DRILL_BACKUP=${TIJARA_RESTORE_DRILL_BACKUP:-<unset>}"
} > "$ENV_FILE"

record_status() {
    local name="$1"
    local status="$2"
    local exit_code="$3"
    local log_file="$4"
    local message="$5"
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$status" "$exit_code" "$log_file" "$message" >> "$STATUS_FILE"
}

run_step() {
    local name="$1"
    shift
    local log_file="$ORCH_DIR/$name.log"

    set +e
    "$@" > "$log_file" 2>&1
    local exit_code=$?
    set -e

    if [[ "$exit_code" -eq 0 ]]; then
        record_status "$name" "passed" "$exit_code" "$log_file" ""
    else
        record_status "$name" "failed" "$exit_code" "$log_file" "step failed"
    fi
}

run_step "release-candidate" \
    env \
    TIJARA_RELEASE_RUN_ID="$RUN_ID" \
    TIJARA_RELEASE_EVIDENCE_DIR="$RELEASE_DIR" \
    TIJARA_RELEASE_CHECKS="$RELEASE_CHECKS" \
    TIJARA_E2E_RUN_ID="$RUN_ID" \
    TIJARA_E2E_EVIDENCE_DIR="$E2E_DIR" \
    TIJARA_OPS_RUN_ID="$RUN_ID" \
    TIJARA_OPS_EVIDENCE_DIR="$OPS_DIR" \
    make release-candidate

run_step "signoff-pack" \
    env \
    TIJARA_SIGNOFF_RUN_ID="$RUN_ID" \
    TIJARA_SIGNOFF_ENVIRONMENT="$SIGNOFF_ENVIRONMENT" \
    TIJARA_SIGNOFF_OUTPUT="$SIGNOFF_DIR" \
    TIJARA_SIGNOFF_EVIDENCE_PATHS="$RELEASE_DIR,$E2E_DIR,$OPS_DIR" \
    TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS="$REQUIRED_GROUPS" \
    TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE="$STRICT_REQUIRED" \
    make signoff-pack

run_step "release-readiness" \
    env \
    TIJARA_RELEASE_FAIL_ON_WARNING="$FAIL_ON_WARNING" \
    make check-release-readiness READINESS="$READINESS_FILE"

passed_count="$(awk -F '\t' '$2 == "passed" {count++} END {print count + 0}' "$STATUS_FILE")"
failed_count="$(awk -F '\t' '$2 == "failed" {count++} END {print count + 0}' "$STATUS_FILE")"
overall_status="passed"
if [[ "$failed_count" -gt 0 ]]; then
    overall_status="failed"
fi

{
    echo "# Tijara Staging Release Sign-Off"
    echo
    echo "- Status: $overall_status"
    echo "- Run ID: $RUN_ID"
    echo "- Release checks: $RELEASE_CHECKS"
    echo "- Required evidence groups: $REQUIRED_GROUPS"
    echo "- Strict required evidence: $STRICT_REQUIRED"
    echo "- Fail on warning: $FAIL_ON_WARNING"
    echo "- Started: $STARTED_AT"
    echo "- Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- Passed steps: $passed_count"
    echo "- Failed steps: $failed_count"
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
    echo "## Artifact Paths"
    echo "- Orchestration evidence: $ORCH_DIR"
    echo "- Release evidence: $RELEASE_DIR"
    echo "- Browser E2E evidence: $E2E_DIR"
    echo "- Operations evidence: $OPS_DIR"
    echo "- Sign-off package: $SIGNOFF_DIR"
    echo "- Readiness JSON: $READINESS_FILE"
    echo
    echo "## Evidence Files"
    echo "- Environment summary: $ENV_FILE"
    echo "- Status table: $STATUS_FILE"
} > "$SUMMARY_FILE"

echo "Staging release sign-off evidence written to $ORCH_DIR"
echo "Sign-off package: $SIGNOFF_DIR"
echo "Readiness JSON: $READINESS_FILE"

if [[ "$failed_count" -gt 0 ]]; then
    exit 1
fi
