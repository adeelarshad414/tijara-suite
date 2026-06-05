#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${TIJARA_PROTECTED_RUN_ID:-${TIJARA_E2E_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}}"
TARGET_ENVIRONMENT="${TIJARA_TARGET_ENVIRONMENT:-staging}"
RUNTIME_ROOT="${TIJARA_PROTECTED_E2E_RUNTIME_ROOT:-deploy/runtime}"
ORCH_DIR="${TIJARA_PROTECTED_E2E_ORCH_DIR:-$RUNTIME_ROOT/protected-e2e/$RUN_ID}"
SEED_DIR="${TIJARA_E2E_SEED_EVIDENCE_DIR:-$RUNTIME_ROOT/e2e-seed/$RUN_ID}"
PROFILE_DIR="${TIJARA_E2E_PROFILE_OUTPUT:-$RUNTIME_ROOT/e2e-profile/$RUN_ID}"
E2E_DIR="${TIJARA_E2E_EVIDENCE_DIR:-$RUNTIME_ROOT/e2e-evidence/$RUN_ID}"
EXECUTION_DIR="${TIJARA_E2E_EXECUTION_OUTPUT:-$RUNTIME_ROOT/e2e-execution/$RUN_ID}"

SEED_E2E="${TIJARA_PROTECTED_E2E_SEED:-0}"
PROFILE_E2E="${TIJARA_PROTECTED_E2E_PROFILE:-1}"
RUN_BROWSER_E2E="${TIJARA_PROTECTED_E2E_RUN_BROWSER:-1}"
EXECUTION_EVIDENCE="${TIJARA_PROTECTED_E2E_EXECUTION_EVIDENCE:-1}"
STRICT="${TIJARA_PROTECTED_E2E_STRICT:-1}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

SUMMARY_FILE="$ORCH_DIR/summary.md"
STATUS_FILE="$ORCH_DIR/status.tsv"
ENV_FILE="$ORCH_DIR/env-summary.txt"
mkdir -p "$ORCH_DIR"
: > "$STATUS_FILE"

truthy() {
  case "$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

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

{
  echo "run_id=$RUN_ID"
  echo "target_environment=$TARGET_ENVIRONMENT"
  echo "orchestration_dir=$ORCH_DIR"
  echo "e2e_seed_dir=$SEED_DIR"
  echo "e2e_profile_dir=$PROFILE_DIR"
  echo "e2e_evidence_dir=$E2E_DIR"
  echo "e2e_execution_dir=$EXECUTION_DIR"
  echo "seed_e2e=$SEED_E2E"
  echo "profile_e2e=$PROFILE_E2E"
  echo "run_browser_e2e=$RUN_BROWSER_E2E"
  echo "execution_evidence=$EXECUTION_EVIDENCE"
  echo "strict=$STRICT"
  echo "started_at=$STARTED_AT"
  echo "ODOO_BASE_URL=${ODOO_BASE_URL:-<unset>}"
  echo "ODOO_DATABASE=${ODOO_DATABASE:-<unset>}"
  echo "ODOO_USERNAME=${ODOO_USERNAME:+<set>}"
  echo "ODOO_PASSWORD=${ODOO_PASSWORD:+<set>}"
  echo "TIJARA_E2E_PASSWORD=${TIJARA_E2E_PASSWORD:+<set>}"
  echo "TIJARA_E2E_SCOPE=${TIJARA_E2E_SCOPE:-full}"
} > "$ENV_FILE"

if truthy "$SEED_E2E"; then
  run_step "e2e-seed" \
    env \
    TIJARA_E2E_SEED_RUN_ID="$RUN_ID" \
    TIJARA_E2E_SEED_EVIDENCE_DIR="$SEED_DIR" \
    TIJARA_E2E_SEED_SCOPE="${TIJARA_E2E_SCOPE:-full}" \
    make seed-e2e
  if [[ -f "$SEED_DIR/e2e-seed.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$SEED_DIR/e2e-seed.env"
    set +a
    if [[ -z "${ODOO_PASSWORD:-}" && -n "${TIJARA_E2E_PASSWORD:-}" ]]; then
      export ODOO_PASSWORD="$TIJARA_E2E_PASSWORD"
    fi
    record_status "e2e-seed-env" "passed" "0" "$SEED_DIR/e2e-seed.env" "seed env sourced"
  else
    record_status "e2e-seed-env" "warning" "0" "$SEED_DIR/e2e-seed.env" "seed env file not present"
  fi
else
  record_status "e2e-seed" "skipped" "0" "" "seed step not requested"
fi

if truthy "$PROFILE_E2E"; then
  run_step "e2e-profile" \
    env \
    TIJARA_E2E_PROFILE_RUN_ID="$RUN_ID" \
    TIJARA_E2E_PROFILE_OUTPUT="$PROFILE_DIR" \
    TIJARA_E2E_PROFILE_ENVIRONMENT="$TARGET_ENVIRONMENT" \
    TIJARA_E2E_SEED_ENV="$SEED_DIR/e2e-seed.env" \
    TIJARA_E2E_SEED_EVIDENCE="$SEED_DIR/e2e-seed-evidence.json" \
    make staging-e2e-profile
else
  record_status "e2e-profile" "skipped" "0" "" "profile preflight not requested"
fi

if truthy "$RUN_BROWSER_E2E"; then
  run_step "e2e-browser" \
    env \
    TIJARA_E2E_RUN_ID="$RUN_ID" \
    TIJARA_E2E_EVIDENCE_DIR="$E2E_DIR" \
    make e2e-staging
else
  record_status "e2e-browser" "skipped" "0" "" "browser E2E not requested"
fi

if truthy "$EXECUTION_EVIDENCE"; then
  run_step "e2e-execution-evidence" \
    env \
    TIJARA_E2E_EXECUTION_RUN_ID="$RUN_ID" \
    TIJARA_E2E_EXECUTION_ENVIRONMENT="$TARGET_ENVIRONMENT" \
    TIJARA_E2E_EXECUTION_OUTPUT="$EXECUTION_DIR" \
    TIJARA_E2E_EXECUTION_SEED_EVIDENCE="$SEED_DIR/e2e-seed-evidence.json" \
    TIJARA_E2E_EXECUTION_PROFILE_EVIDENCE="$PROFILE_DIR/staging-e2e-profile.json" \
    TIJARA_E2E_EXECUTION_E2E_DIR="$E2E_DIR" \
    TIJARA_E2E_EXECUTION_READINESS_EVIDENCE="$E2E_DIR/e2e-readiness.json" \
    TIJARA_E2E_EXECUTION_PLAYWRIGHT_JSON="$E2E_DIR/playwright-results.json" \
    TIJARA_E2E_EXECUTION_E2E_SUMMARY="$E2E_DIR/summary.md" \
    TIJARA_E2E_EXECUTION_ORCH_STATUS="$STATUS_FILE" \
    make e2e-execution-evidence
else
  record_status "e2e-execution-evidence" "skipped" "0" "" "execution evidence not requested"
fi

failed_count="$(awk -F '\t' 'NR > 1 && ($2 == "failed" || $2 == "blocked" || $2 == "error") {count++} END {print count + 0}' "$STATUS_FILE")"
warning_count="$(awk -F '\t' 'NR > 1 && ($2 == "warning" || $2 == "skipped") {count++} END {print count + 0}' "$STATUS_FILE")"
if [[ "$failed_count" -gt 0 ]]; then
  overall_status="failed"
elif [[ "$warning_count" -gt 0 ]]; then
  overall_status="warning"
else
  overall_status="passed"
fi

{
  echo "# Protected Browser E2E Evidence"
  echo
  echo "- Status: $overall_status"
  echo "- Run ID: $RUN_ID"
  echo "- Target environment: $TARGET_ENVIRONMENT"
  echo "- Started: $STARTED_AT"
  echo "- Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Evidence directory: $ORCH_DIR"
  echo
  echo "## Evidence Paths"
  echo "- Seed: $SEED_DIR"
  echo "- Profile: $PROFILE_DIR"
  echo "- Browser: $E2E_DIR"
  echo "- Execution: $EXECUTION_DIR"
  echo
  echo "## Status"
  awk -F '\t' 'NR > 1 {printf "- %s: %s - %s\n", $1, $2, $5}' "$STATUS_FILE"
  echo
  echo "## Evidence Files"
  echo "- Environment summary: $ENV_FILE"
  echo "- Status table: $STATUS_FILE"
} > "$SUMMARY_FILE"

echo "Protected Browser E2E evidence written to $ORCH_DIR"
echo "status=$overall_status"

if [[ "$failed_count" -gt 0 ]] && truthy "$STRICT"; then
  exit 1
fi
exit 0
