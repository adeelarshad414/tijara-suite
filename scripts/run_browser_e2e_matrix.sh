#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${TIJARA_BROWSER_E2E_RUN_ID:-${TIJARA_PROTECTED_RUN_ID:-browser-matrix-$(date -u +%Y%m%dT%H%M%SZ)}}"
TARGET_ENVIRONMENT="${TIJARA_TARGET_ENVIRONMENT:-staging}"
BASE_URL="${ODOO_BASE_URL:-http://127.0.0.1:8069}"
SCOPE="${TIJARA_E2E_SCOPE:-full}"
PROJECTS_RAW="${TIJARA_BROWSER_E2E_PROJECTS:-chromium-desktop mobile-touch firefox-desktop webkit-desktop tablet-touch}"
MATRIX_DIR="${TIJARA_BROWSER_E2E_MATRIX_OUTPUT:-deploy/runtime/browser-e2e-matrix/$RUN_ID}"
PROJECT_STATUS_FILE="$MATRIX_DIR/project-status.tsv"
ENV_FILE="$MATRIX_DIR/env-summary.txt"
STRICT="${TIJARA_BROWSER_E2E_MATRIX_STRICT:-1}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$MATRIX_DIR"
printf "project\tstatus\te2e_exit\texecution_exit\te2e_dir\texecution_dir\tlog\tmessage\n" > "$PROJECT_STATUS_FILE"

read -r -a PROJECTS <<< "$PROJECTS_RAW"

truthy() {
    case "$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|y|on) return 0 ;;
        *) return 1 ;;
    esac
}

if [[ -n "${TIJARA_BROWSER_E2E_SEED_ENV:-}" && -f "$TIJARA_BROWSER_E2E_SEED_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$TIJARA_BROWSER_E2E_SEED_ENV"
    set +a
fi

if [[ -z "${ODOO_PASSWORD:-}" && -n "${TIJARA_E2E_PASSWORD:-}" ]]; then
    export ODOO_PASSWORD="$TIJARA_E2E_PASSWORD"
fi

{
    echo "run_id=$RUN_ID"
    echo "target_environment=$TARGET_ENVIRONMENT"
    echo "base_url=$BASE_URL"
    echo "scope=$SCOPE"
    echo "matrix_dir=$MATRIX_DIR"
    echo "started_at=$STARTED_AT"
    echo "strict=$STRICT"
    echo "projects=${PROJECTS[*]}"
    echo "seed_env=${TIJARA_BROWSER_E2E_SEED_ENV:-<unset>}"
    echo "ODOO_DATABASE=${ODOO_DATABASE:-<unset>}"
    echo "ODOO_USERNAME=${ODOO_USERNAME:+<set>}"
    echo "ODOO_PASSWORD=${ODOO_PASSWORD:+<set>}"
} > "$ENV_FILE"

for project in "${PROJECTS[@]}"; do
    project_dir="$MATRIX_DIR/projects/$project"
    e2e_dir="$project_dir/e2e-evidence"
    execution_dir="$project_dir/e2e-execution"
    e2e_log="$project_dir/run-staging-e2e.log"
    execution_log="$project_dir/export-execution-evidence.log"
    mkdir -p "$project_dir"

    echo "Running browser E2E project: $project"
    set +e
    env \
        ODOO_BASE_URL="$BASE_URL" \
        TIJARA_E2E_SCOPE="$SCOPE" \
        TIJARA_E2E_PROJECT="$project" \
        TIJARA_E2E_RUN_ID="$RUN_ID-$project" \
        TIJARA_E2E_EVIDENCE_DIR="$e2e_dir" \
        bash scripts/run_staging_e2e.sh > "$e2e_log" 2>&1
    e2e_status=$?
    set -e

    set +e
    python3 scripts/export_e2e_execution_evidence.py \
        --run-id "$RUN_ID-$project" \
        --target-environment "$TARGET_ENVIRONMENT" \
        --output "$execution_dir" \
        --e2e-evidence-dir "$e2e_dir" \
        --readiness-evidence "$e2e_dir/e2e-readiness.json" \
        --playwright-json "$e2e_dir/playwright-results.json" \
        --e2e-summary "$e2e_dir/summary.md" \
        > "$execution_log" 2>&1
    execution_status=$?
    set -e

    if [[ "$e2e_status" -eq 0 && "$execution_status" -eq 0 ]]; then
        status="passed"
        message="project passed"
    else
        status="failed"
        message="project failed"
    fi
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$project" \
        "$status" \
        "$e2e_status" \
        "$execution_status" \
        "$e2e_dir" \
        "$execution_dir" \
        "$e2e_log" \
        "$message" >> "$PROJECT_STATUS_FILE"
done

aggregate_args=(
    --run-id "$RUN_ID"
    --target-environment "$TARGET_ENVIRONMENT"
    --output "$MATRIX_DIR"
    --project-status "$PROJECT_STATUS_FILE"
)
for project in "${PROJECTS[@]}"; do
    aggregate_args+=(--project "$project")
done
if truthy "$STRICT"; then
    aggregate_args+=(--strict)
fi

set +e
python3 scripts/export_browser_e2e_matrix_evidence.py "${aggregate_args[@]}" > "$MATRIX_DIR/export-matrix-evidence.log" 2>&1
aggregate_status=$?
set -e

cat "$MATRIX_DIR/export-matrix-evidence.log"
echo "Browser E2E matrix evidence written to $MATRIX_DIR"

if [[ "$aggregate_status" -ne 0 ]] && truthy "$STRICT"; then
    exit "$aggregate_status"
fi
exit 0
