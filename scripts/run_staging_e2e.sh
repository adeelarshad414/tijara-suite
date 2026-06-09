#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SCOPE="${TIJARA_E2E_SCOPE:-full}"
BASE_URL="${ODOO_BASE_URL:-http://127.0.0.1:8069}"
RUN_ID="${TIJARA_E2E_RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
EVIDENCE_DIR="${TIJARA_E2E_EVIDENCE_DIR:-deploy/runtime/e2e-evidence/$RUN_ID}"
SUMMARY_FILE="$EVIDENCE_DIR/summary.md"
ENV_FILE="$EVIDENCE_DIR/env-summary.txt"
STATUS_FILE="$EVIDENCE_DIR/status.tsv"
READINESS_FILE="$EVIDENCE_DIR/e2e-readiness.json"
READINESS_SUMMARY_FILE="$EVIDENCE_DIR/e2e-readiness-summary.md"
LOG_FILE="$EVIDENCE_DIR/playwright-output.log"
JSON_FILE="$EVIDENCE_DIR/playwright-results.json"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$EVIDENCE_DIR"

public_required=(
    ODOO_BASE_URL
    TIJARA_DISPLAY_SLUG
    TIJARA_KIOSK_SLUG
    TIJARA_CUSTOMER_DISPLAY_SLUG
)

authenticated_required=(
    ODOO_BASE_URL
    ODOO_USERNAME
    ODOO_PASSWORD
    ODOO_DATABASE
    TIJARA_POS_CONFIG_ID
    TIJARA_E2E_PRODUCT_ID
    TIJARA_E2E_PAYMENT_METHOD_ID
    TIJARA_E2E_REFUND_REASON_ID
    TIJARA_E2E_REFUND_BARCODE
    TIJARA_REFUND_ACTION_URL
    TIJARA_REPORT_ORDER_URL
    TIJARA_OFFLINE_QUEUE_ACTION_URL
)

case "$SCOPE" in
    public)
        required_vars=("${public_required[@]}")
        specs=(tests/e2e/display-kiosk.spec.mjs)
        ;;
    authenticated)
        required_vars=("${authenticated_required[@]}")
        specs=(tests/e2e/pos-checkout-print.spec.mjs tests/e2e/pos-enterprise-journey.spec.mjs tests/e2e/pos-direct-ui-clickthrough.spec.mjs tests/e2e/refunds-reports.spec.mjs)
        ;;
    full)
        required_vars=("${public_required[@]}" "${authenticated_required[@]}")
        specs=(tests/e2e/display-kiosk.spec.mjs tests/e2e/pos-checkout-print.spec.mjs tests/e2e/pos-enterprise-journey.spec.mjs tests/e2e/pos-direct-ui-clickthrough.spec.mjs tests/e2e/refunds-reports.spec.mjs)
        ;;
    *)
        echo "Unsupported TIJARA_E2E_SCOPE='$SCOPE'. Use public, authenticated, or full." >&2
        exit 2
        ;;
esac

export ODOO_BASE_URL="$BASE_URL"
export TIJARA_RUN_POS_UI_E2E="${TIJARA_RUN_POS_UI_E2E:-1}"

missing=()
for var_name in "${required_vars[@]}"; do
    if [[ -z "${!var_name:-}" ]]; then
        missing+=("$var_name")
    fi
done

{
    echo "Tijara staging E2E environment"
    echo "run_id=$RUN_ID"
    echo "scope=$SCOPE"
    echo "base_url=$BASE_URL"
    echo "evidence_dir=$EVIDENCE_DIR"
    echo "started_at=$STARTED_AT"
    echo
    for var_name in "${required_vars[@]}"; do
        if [[ "$var_name" == *PASSWORD* || "$var_name" == *SECRET* || "$var_name" == *TOKEN* ]]; then
            if [[ -n "${!var_name:-}" ]]; then
                echo "$var_name=<set>"
            else
                echo "$var_name=<missing>"
            fi
        else
            echo "$var_name=${!var_name:-<missing>}"
        fi
    done
    echo "TIJARA_RUN_POS_UI_E2E=${TIJARA_RUN_POS_UI_E2E}"
    echo "TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=${TIJARA_RUN_DIRECT_POS_CLICKTHROUGH:-0}"
    echo "TIJARA_RUN_DIRECT_POS_VALIDATE_E2E=${TIJARA_RUN_DIRECT_POS_VALIDATE_E2E:-0}"
    echo "TIJARA_RUN_DIRECT_REFUND_FORM_E2E=${TIJARA_RUN_DIRECT_REFUND_FORM_E2E:-0}"
    echo "TIJARA_RUN_MOBILE_OFFLINE_E2E=${TIJARA_RUN_MOBILE_OFFLINE_E2E:-0}"
} > "$ENV_FILE"

readiness_args=(
    --run-id "$RUN_ID"
    --scope "$SCOPE"
    --base-url "$BASE_URL"
    --output "$EVIDENCE_DIR"
    --started-at "$STARTED_AT"
)
for var_name in "${required_vars[@]}"; do
    readiness_args+=(--required-var "$var_name")
done
for spec in "${specs[@]}"; do
    readiness_args+=(--spec "$spec")
done
for flag_name in \
    TIJARA_RUN_POS_UI_E2E \
    TIJARA_RUN_DIRECT_POS_CLICKTHROUGH \
    TIJARA_RUN_DIRECT_POS_VALIDATE_E2E \
    TIJARA_RUN_DIRECT_REFUND_FORM_E2E \
    TIJARA_RUN_MOBILE_OFFLINE_E2E; do
    readiness_args+=(--optional-flag "$flag_name")
done

set +e
python3 scripts/export_e2e_readiness.py "${readiness_args[@]}" >> "$LOG_FILE" 2>&1
readiness_status=$?
set -e

write_summary() {
    local status="$1"
    local exit_code="$2"
    {
        echo "# Tijara Staging Browser E2E Evidence"
        echo
        echo "- Status: $status"
        echo "- Exit code: $exit_code"
        echo "- Run ID: $RUN_ID"
        echo "- Scope: $SCOPE"
        echo "- Base URL: $BASE_URL"
        echo "- Evidence directory: $EVIDENCE_DIR"
        echo "- Started: $STARTED_AT"
        echo "- Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo
        echo "## Specs"
        for spec in "${specs[@]}"; do
            echo "- $spec"
        done
        echo
        echo "## Evidence Files"
        echo "- Environment summary: $ENV_FILE"
        echo "- Status table: $STATUS_FILE"
        echo "- Readiness JSON: $READINESS_FILE"
        echo "- Readiness summary: $READINESS_SUMMARY_FILE"
        echo "- Playwright output: $LOG_FILE"
        echo "- Playwright JSON: $JSON_FILE"
        if (( ${#missing[@]} > 0 )); then
            echo
            echo "## Missing Variables"
            for var_name in "${missing[@]}"; do
                echo "- $var_name"
            done
        fi
    } > "$SUMMARY_FILE"
}

wait_for_base_url() {
    local elapsed=0
    local max_seconds="${TIJARA_E2E_HEALTH_WAIT_SECONDS:-45}"
    local step_seconds="${TIJARA_E2E_HEALTH_RETRY_SECONDS:-3}"
    while [[ "$elapsed" -le "$max_seconds" ]]; do
        if curl -fsS --max-time "${TIJARA_E2E_HEALTH_TIMEOUT:-10}" "$BASE_URL/web/login" > /dev/null; then
            return 0
        fi
        sleep "$step_seconds"
        elapsed=$((elapsed + step_seconds))
    done
    return 1
}

if (( ${#missing[@]} > 0 )); then
    {
        echo "Missing required staging E2E environment variables:"
        printf ' - %s\n' "${missing[@]}"
        echo
        echo "See $ENV_FILE"
    } | tee -a "$LOG_FILE" >&2
    write_summary "blocked: missing environment" 2
    exit 2
fi

if [[ "$readiness_status" -ne 0 ]]; then
    echo "E2E readiness evidence failed with exit code $readiness_status." | tee -a "$LOG_FILE" >&2
    write_summary "blocked: readiness evidence failed" "$readiness_status"
    exit "$readiness_status"
fi

if ! wait_for_base_url; then
    echo "Odoo login page is not reachable at $BASE_URL/web/login" | tee -a "$LOG_FILE" >&2
    write_summary "blocked: base URL unreachable" 2
    exit 2
fi

playwright_args=("${specs[@]}")
if [[ -n "${TIJARA_E2E_PROJECT:-}" ]]; then
    playwright_args+=("--project" "$TIJARA_E2E_PROJECT")
fi

set +e
PLAYWRIGHT_JSON_OUTPUT_NAME="$JSON_FILE" npx playwright test "${playwright_args[@]}" --reporter=line,json > "$LOG_FILE" 2>&1
status=$?
set -e

if [[ "$status" -eq 0 ]]; then
    write_summary "passed" "$status"
else
    write_summary "failed" "$status"
fi

echo "Staging E2E evidence written to $EVIDENCE_DIR"
exit "$status"
