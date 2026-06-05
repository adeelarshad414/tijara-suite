#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${TIJARA_RELEASE_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
EVIDENCE_DIR="${TIJARA_RELEASE_EVIDENCE_DIR:-deploy/runtime/release-evidence/$RUN_ID}"
SUMMARY_FILE="$EVIDENCE_DIR/summary.md"
STATUS_FILE="$EVIDENCE_DIR/status.tsv"
ENV_FILE="$EVIDENCE_DIR/env-summary.txt"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REQUESTED_CHECKS="${TIJARA_RELEASE_CHECKS:-local}"

mkdir -p "$EVIDENCE_DIR"
: > "$STATUS_FILE"

checks=()
append_check() {
    checks+=("$1")
}

expand_check() {
    local check="$1"
    local normalized
    normalized="$(echo "$check" | tr '[:upper:]' '[:lower:]' | xargs)"
    case "$normalized" in
        local)
            append_check "validate"
            append_check "js"
            append_check "security"
            append_check "syntax"
            ;;
        full)
            append_check "git-clean"
            append_check "validate"
            append_check "js"
            append_check "security"
            append_check "syntax"
            append_check "odoo"
            append_check "e2e-staging"
            append_check "ops-staging"
            ;;
        "")
            ;;
        *)
            append_check "$normalized"
            ;;
    esac
}

IFS="," read -r -a requested <<< "$REQUESTED_CHECKS"
for check in "${requested[@]}"; do
    expand_check "$check"
done

{
    echo "Tijara release candidate gate"
    echo "run_id=$RUN_ID"
    echo "requested_checks=$REQUESTED_CHECKS"
    echo "expanded_checks=${checks[*]}"
    echo "evidence_dir=$EVIDENCE_DIR"
    echo "started_at=$STARTED_AT"
    echo "git_head=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "git_branch=$(git branch --show-current 2>/dev/null || echo unknown)"
    echo
    echo "ODOO_BASE_URL=${ODOO_BASE_URL:-<unset>}"
    echo "ODOO_DATABASE=${ODOO_DATABASE:-<unset>}"
    echo "TIJARA_E2E_SCOPE=${TIJARA_E2E_SCOPE:-<unset>}"
    echo "TIJARA_OPS_CHECKS=${TIJARA_OPS_CHECKS:-<unset>}"
    echo "TIJARA_OPS_STRICT=${TIJARA_OPS_STRICT:-<unset>}"
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

run_git_clean() {
    local name="git-clean"
    local log_file="$EVIDENCE_DIR/$name.log"
    git status --short > "$log_file"
    if [[ -s "$log_file" ]]; then
        record_status "$name" "failed" "1" "$log_file" "worktree has uncommitted changes"
    else
        record_status "$name" "passed" "0" "$log_file" ""
    fi
}

run_named_check() {
    local check="$1"
    case "$check" in
        validate)
            run_command_check "validate" "make validate"
            ;;
        js | js-check)
            run_command_check "js-check" "bash scripts/js_check.sh"
            ;;
        security | security-audit)
            run_command_check "security-audit" "bash scripts/security_audit.sh"
            ;;
        syntax)
            run_command_check "script-syntax" "bash -n scripts/*.sh deploy/bin/*.sh deploy/postgres/*.sh"
            ;;
        odoo | test-odoo)
            run_command_check "odoo-tests" "make test-odoo"
            ;;
        e2e | e2e-staging)
            run_command_check "e2e-staging" "make e2e-staging"
            ;;
        ops | ops-staging)
            run_command_check "ops-staging" "make ops-staging"
            ;;
        git | git-clean)
            run_git_clean
            ;;
        *)
            local log_file="$EVIDENCE_DIR/$check.log"
            echo "Unknown release candidate check '$check'." > "$log_file"
            record_status "$check" "failed" "2" "$log_file" "unknown check"
            ;;
    esac
}

for check in "${checks[@]}"; do
    run_named_check "$check"
done

passed_count="$(awk -F '\t' '$2 == "passed" {count++} END {print count + 0}' "$STATUS_FILE")"
failed_count="$(awk -F '\t' '$2 == "failed" {count++} END {print count + 0}' "$STATUS_FILE")"
overall_status="passed"
if [[ "$failed_count" -gt 0 ]]; then
    overall_status="failed"
fi

{
    echo "# Tijara Release Candidate Gate"
    echo
    echo "- Status: $overall_status"
    echo "- Run ID: $RUN_ID"
    echo "- Requested checks: $REQUESTED_CHECKS"
    echo "- Expanded checks: ${checks[*]}"
    echo "- Evidence directory: $EVIDENCE_DIR"
    echo "- Started: $STARTED_AT"
    echo "- Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- Git branch: $(git branch --show-current 2>/dev/null || echo unknown)"
    echo "- Git head: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "- Passed: $passed_count"
    echo "- Failed: $failed_count"
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

echo "Release candidate gate evidence written to $EVIDENCE_DIR"

if [[ "$failed_count" -gt 0 ]]; then
    exit 1
fi
