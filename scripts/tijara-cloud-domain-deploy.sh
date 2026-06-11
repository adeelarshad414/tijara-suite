#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage: bash scripts/tijara-cloud-domain-deploy.sh --domain DOMAIN [options]

Cross-platform cloud/domain deployment wrapper for Linux and macOS servers.
It configures Tijara Suite for a public domain, deploys the Docker Compose
stack through scripts/tijara_host.py, and can optionally generate DNS/TLS/
backup automation evidence through scripts/run_production_infra_automation.py.

Options:
  --domain DOMAIN              Public domain, for example pos.example.com
  --environment NAME           development, staging, or production (default: production)
  --db NAME                    Odoo database for install/seed (default: tijara_prod)
  --provider-template NAME     Optional infra template, for example cloudflare-cert-manager-postgres
  --tenant-artifact PATH       Optional tenant ops artifact for DNS/TLS/backup planning
  --infra-mode plan|apply      Infra automation mode (default: plan)
  --execute-infra              Allow infra runner execution when --infra-mode apply is used
  --confirm YES                Confirmation forwarded to infra automation
  --skip-infra-plan            Only configure/deploy the app; skip DNS/TLS/backup plan generation
  --monitoring, --with-monitoring
                              Start monitoring profile
  --hardware, --with-hardware Start hardware bridge profile
  --all, --all-profiles       Start every optional profile
  --build                     Build local services before startup
  --pull, --no-pull           Pull images before startup (default: pull)
  --install-suite             Install Tijara modules after startup
  --seed-demo                 Seed demo data after startup
  --generate-secrets          Generate local random placeholder secrets
  --allow-placeholders        Allow placeholders even with production defaults
  --dry-run                   Print deployment actions without changing services/config
  -h, --help                  Show this help

Examples:
  bash scripts/tijara-cloud-domain-deploy.sh --domain pos.example.com --monitoring --install-suite
  bash scripts/tijara-cloud-domain-deploy.sh --domain staging.example.com --environment staging --generate-secrets --monitoring --install-suite
  bash scripts/tijara-cloud-domain-deploy.sh --domain pos.example.com --provider-template cloudflare-cert-manager-postgres --tenant-artifact deploy/runtime/tenants/tijara_customer_001
USAGE
}

python_cmd() {
    if command -v python3 >/dev/null 2>&1; then
        printf '%s\n' "python3"
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        printf '%s\n' "python"
        return 0
    fi
    echo "python3 or python is required." >&2
    exit 1
}

DOMAIN=""
ENVIRONMENT="production"
DB="tijara_prod"
PROVIDER_TEMPLATE=""
TENANT_ARTIFACT=""
INFRA_MODE="plan"
CONFIRM="NO"
EXECUTE_INFRA=0
SKIP_INFRA_PLAN=0
DRY_RUN=0
HOST_FLAGS=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        --domain|--environment|--db|--provider-template|--tenant-artifact|--infra-mode|--confirm)
            opt="$1"
            shift
            [ "$#" -gt 0 ] || { echo "$opt requires a value" >&2; exit 2; }
            case "$opt" in
                --domain) DOMAIN="$1" ;;
                --environment) ENVIRONMENT="$1" ;;
                --db) DB="$1" ;;
                --provider-template) PROVIDER_TEMPLATE="$1" ;;
                --tenant-artifact) TENANT_ARTIFACT="$1" ;;
                --infra-mode) INFRA_MODE="$1" ;;
                --confirm) CONFIRM="$1" ;;
            esac
            ;;
        --execute-infra)
            EXECUTE_INFRA=1
            ;;
        --skip-infra-plan)
            SKIP_INFRA_PLAN=1
            ;;
        --monitoring|--with-monitoring)
            HOST_FLAGS+=("--with-monitoring")
            ;;
        --hardware|--with-hardware)
            HOST_FLAGS+=("--with-hardware")
            ;;
        --all|--all-profiles)
            HOST_FLAGS+=("--all-profiles")
            ;;
        --build|--install-suite|--seed-demo|--generate-secrets|--allow-placeholders|--pull|--no-pull)
            HOST_FLAGS+=("$1")
            ;;
        --dry-run)
            DRY_RUN=1
            HOST_FLAGS+=("--dry-run")
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if [ -z "$DOMAIN" ]; then
    echo "--domain is required." >&2
    usage >&2
    exit 2
fi

if [ "$ENVIRONMENT" != "development" ] && [ "$ENVIRONMENT" != "staging" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo "--environment must be development, staging, or production." >&2
    exit 2
fi

if [ "$INFRA_MODE" != "plan" ] && [ "$INFRA_MODE" != "apply" ]; then
    echo "--infra-mode must be plan or apply." >&2
    exit 2
fi

PYTHON="$(python_cmd)"
HOST_ARGS=(
    "--root" "$ROOT_DIR"
    "deploy"
    "--environment" "$ENVIRONMENT"
    "--domain" "$DOMAIN"
    "--host-label" "$DOMAIN"
    "--db" "$DB"
)

if [ "$ENVIRONMENT" = "production" ]; then
    HOST_ARGS+=("--production")
fi
HOST_ARGS+=("${HOST_FLAGS[@]}")

echo "Deploying Tijara Suite for domain: $DOMAIN"
"$PYTHON" "$ROOT_DIR/scripts/tijara_host.py" "${HOST_ARGS[@]}"

if [ "$SKIP_INFRA_PLAN" -eq 1 ]; then
    echo "Skipped DNS/TLS/backup infra plan generation."
    exit 0
fi

if [ -z "$PROVIDER_TEMPLATE" ] && [ -z "$TENANT_ARTIFACT" ]; then
    cat <<EOF

App deployment finished. DNS/TLS/backup planning was not generated because no
--provider-template or --tenant-artifact was supplied.

Next example:
  bash scripts/tijara-cloud-domain-deploy.sh --domain $DOMAIN \\
    --provider-template cloudflare-cert-manager-postgres \\
    --tenant-artifact deploy/runtime/tenants/tijara_customer_001
EOF
    exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Dry-run enabled; skipping infra automation output generation."
    exit 0
fi

INFRA_ARGS=("--target-environment" "$ENVIRONMENT" "--mode" "$INFRA_MODE" "--confirm" "$CONFIRM" "--strict")
if [ -n "$PROVIDER_TEMPLATE" ]; then
    INFRA_ARGS+=("--provider-template" "$PROVIDER_TEMPLATE")
fi
if [ -n "$TENANT_ARTIFACT" ]; then
    INFRA_ARGS+=("--tenant-artifact" "$TENANT_ARTIFACT")
fi
if [ "$EXECUTE_INFRA" -eq 1 ]; then
    INFRA_ARGS+=("--execute")
fi

echo "Generating DNS/TLS/backup infra evidence plan..."
"$PYTHON" "$ROOT_DIR/scripts/run_production_infra_automation.py" "${INFRA_ARGS[@]}"

