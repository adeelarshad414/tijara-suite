#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB="${DB:-tijara_dev}"
BASE_URL="${ODOO_BASE_URL:-http://127.0.0.1:8069}"
RUN_ID="${TIJARA_LOCAL_E2E_RUN_ID:-local-e2e-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_EVIDENCE_DIR="${TIJARA_LOCAL_E2E_EVIDENCE_DIR:-deploy/runtime/local-e2e/$RUN_ID}"
STATUS_FILE="$LOCAL_EVIDENCE_DIR/status.tsv"
SUMMARY_FILE="$LOCAL_EVIDENCE_DIR/summary.md"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
E2E_SEED_DIR="deploy/runtime/e2e-seed/$RUN_ID"
STAGING_E2E_DIR="deploy/runtime/e2e-evidence/$RUN_ID"
EXECUTION_DIR="deploy/runtime/e2e-execution/$RUN_ID"
EXPORT_FILE="$LOCAL_EVIDENCE_DIR/e2e-seed-exports.sh"

mkdir -p "$LOCAL_EVIDENCE_DIR"
printf "step\tstatus\tlog\n" > "$STATUS_FILE"

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

credential_value() {
    local persona="$1"
    local column="$2"
    awk -F, -v persona="$persona" -v column="$column" '
        NR == 1 {
            for (i = 1; i <= NF; i++) {
                header[$i] = i
            }
            next
        }
        $1 == persona {
            print $header[column]
            exit
        }
    ' docs/TEST_CREDENTIALS.csv
}

CASHIER_LOGIN="${TIJARA_LOCAL_E2E_LOGIN:-$(credential_value cashier email)}"
CASHIER_PASSWORD="${TIJARA_LOCAL_E2E_PASSWORD:-$(credential_value cashier password)}"

run_step() {
    local name="$1"
    shift
    local log="$LOCAL_EVIDENCE_DIR/${name}.log"
    echo "Running $name..."
    set +e
    "$@" > "$log" 2>&1
    local status=$?
    set -e
    if [[ "$status" -eq 0 ]]; then
        printf "%s\tpassed\t%s\n" "$name" "$log" >> "$STATUS_FILE"
    else
        printf "%s\tfailed\t%s\n" "$name" "$log" >> "$STATUS_FILE"
        echo "$name failed. Last log lines:"
        tail -80 "$log" || true
        return "$status"
    fi
}

wait_for_odoo() {
    local elapsed=0
    local max_seconds="${TIJARA_LOCAL_E2E_WAIT_SECONDS:-90}"
    while [[ "$elapsed" -lt "$max_seconds" ]]; do
        if curl -fsS --max-time 5 "$BASE_URL/web/login" >/dev/null 2>&1; then
            return 0
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done
    echo "Odoo did not respond at $BASE_URL/web/login within ${max_seconds}s." >&2
    return 1
}

write_summary() {
    local status="$1"
    local exit_code="$2"
    {
        echo "# Tijara Local Browser E2E Evidence"
        echo
        echo "- Status: $status"
        echo "- Exit code: $exit_code"
        echo "- Run ID: $RUN_ID"
        echo "- Database: $DB"
        echo "- Base URL: $BASE_URL"
        echo "- Started: $STARTED_AT"
        echo "- Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "- Local evidence directory: $LOCAL_EVIDENCE_DIR"
        echo "- E2E seed evidence: $E2E_SEED_DIR"
        echo "- Browser E2E evidence: $STAGING_E2E_DIR"
        echo "- Execution evidence: $EXECUTION_DIR"
        echo
        echo "## Step Status"
        tail -n +2 "$STATUS_FILE" | while IFS=$'\t' read -r step step_status log; do
            echo "- $step: $step_status ($log)"
        done
    } > "$SUMMARY_FILE"
}

overall_status=0

if ! run_step "compose-up" docker compose "${ENV_FILE_ARGS[@]}" up -d; then
    overall_status=$?
    write_summary "failed: compose startup" "$overall_status"
    exit "$overall_status"
fi

if ! run_step "wait-for-odoo" wait_for_odoo; then
    overall_status=$?
    write_summary "failed: Odoo unreachable" "$overall_status"
    exit "$overall_status"
fi

if [[ "${TIJARA_LOCAL_E2E_UPGRADE:-1}" == "1" ]]; then
    run_step "upgrade-pkr-gst" make upgrade-pkr-gst DB="$DB" || overall_status=$?
    if [[ "$overall_status" -ne 0 ]]; then
        write_summary "failed: module upgrade" "$overall_status"
        exit "$overall_status"
    fi
fi

run_step "verify-pkr-gst" env DB="$DB" bash scripts/verify_pkr_gst.sh || overall_status=$?
if [[ "$overall_status" -ne 0 ]]; then
    write_summary "failed: PKR/GST verification" "$overall_status"
    exit "$overall_status"
fi

run_step "seed-demo-users" env DB="$DB" bash scripts/seed_demo_users.sh || overall_status=$?
if [[ "$overall_status" -ne 0 ]]; then
    write_summary "failed: demo user seed" "$overall_status"
    exit "$overall_status"
fi

run_step "seed-e2e" env \
    DB="$DB" \
    ODOO_BASE_URL="$BASE_URL" \
    TIJARA_E2E_SEED_RUN_ID="$RUN_ID" \
    TIJARA_E2E_LOGIN="$CASHIER_LOGIN" \
    TIJARA_E2E_PASSWORD="$CASHIER_PASSWORD" \
    bash scripts/seed_e2e_odoo.sh || overall_status=$?
if [[ "$overall_status" -ne 0 ]]; then
    write_summary "failed: E2E seed" "$overall_status"
    exit "$overall_status"
fi

SEED_OUTPUT="$E2E_SEED_DIR/seed-output.log"
if [[ ! -f "$SEED_OUTPUT" ]]; then
    echo "Missing E2E seed output: $SEED_OUTPUT" >&2
    printf "%s\tfailed\t%s\n" "seed-export-load" "$SEED_OUTPUT" >> "$STATUS_FILE"
    write_summary "failed: missing seed exports" 2
    exit 2
fi

if ! grep '^export ' "$SEED_OUTPUT" > "$EXPORT_FILE"; then
    echo "Missing export lines in E2E seed output: $SEED_OUTPUT" >&2
    printf "%s\tfailed\t%s\n" "seed-export-load" "$SEED_OUTPUT" >> "$STATUS_FILE"
    write_summary "failed: missing seed exports" 2
    exit 2
fi
set -a
source "$EXPORT_FILE"
set +a

export ODOO_BASE_URL="$BASE_URL"
export ODOO_DATABASE="${ODOO_DATABASE:-$DB}"
export ODOO_USERNAME="${ODOO_USERNAME:-$CASHIER_LOGIN}"
export ODOO_PASSWORD="$CASHIER_PASSWORD"
export TIJARA_E2E_SCOPE="${TIJARA_E2E_SCOPE:-full}"
export TIJARA_E2E_RUN_ID="$RUN_ID"
export TIJARA_E2E_EVIDENCE_DIR="$STAGING_E2E_DIR"
export TIJARA_E2E_PROJECT="${TIJARA_E2E_PROJECT:-chromium-desktop}"
export TIJARA_RUN_POS_UI_E2E="${TIJARA_RUN_POS_UI_E2E:-1}"

set +e
bash scripts/run_staging_e2e.sh > "$LOCAL_EVIDENCE_DIR/run-staging-e2e.log" 2>&1
e2e_status=$?
set -e
if [[ "$e2e_status" -eq 0 ]]; then
    printf "%s\tpassed\t%s\n" "browser-e2e" "$LOCAL_EVIDENCE_DIR/run-staging-e2e.log" >> "$STATUS_FILE"
else
    printf "%s\tfailed\t%s\n" "browser-e2e" "$LOCAL_EVIDENCE_DIR/run-staging-e2e.log" >> "$STATUS_FILE"
    tail -120 "$LOCAL_EVIDENCE_DIR/run-staging-e2e.log" || true
fi

set +e
python3 scripts/export_e2e_execution_evidence.py \
    --run-id "$RUN_ID" \
    --target-environment local \
    --output "$EXECUTION_DIR" \
    --seed-evidence "$E2E_SEED_DIR/e2e-seed-evidence.json" \
    --e2e-evidence-dir "$STAGING_E2E_DIR" \
    --readiness-evidence "$STAGING_E2E_DIR/e2e-readiness.json" \
    --playwright-json "$STAGING_E2E_DIR/playwright-results.json" \
    --e2e-summary "$STAGING_E2E_DIR/summary.md" \
    > "$LOCAL_EVIDENCE_DIR/export-e2e-execution.log" 2>&1
execution_status=$?
set -e
if [[ "$execution_status" -eq 0 ]]; then
    printf "%s\tpassed\t%s\n" "execution-evidence" "$LOCAL_EVIDENCE_DIR/export-e2e-execution.log" >> "$STATUS_FILE"
else
    printf "%s\tfailed\t%s\n" "execution-evidence" "$LOCAL_EVIDENCE_DIR/export-e2e-execution.log" >> "$STATUS_FILE"
    tail -80 "$LOCAL_EVIDENCE_DIR/export-e2e-execution.log" || true
fi

if [[ "$e2e_status" -ne 0 ]]; then
    write_summary "failed: browser E2E" "$e2e_status"
    exit "$e2e_status"
fi
if [[ "$execution_status" -ne 0 ]]; then
    write_summary "failed: execution evidence" "$execution_status"
    exit "$execution_status"
fi

write_summary "passed" 0
echo "Local browser E2E evidence written to $LOCAL_EVIDENCE_DIR"
