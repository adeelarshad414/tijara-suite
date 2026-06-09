#!/usr/bin/env bash
set -euo pipefail

CONFIG_TEMPLATE="${ODOO_CONFIG_TEMPLATE:-/etc/odoo/odoo.conf.template}"
RUNTIME_CONFIG="${ODOO_RUNTIME_CONFIG:-/tmp/tijara-odoo.conf}"

export ODOO_DB_HOST="${ODOO_DB_HOST:-${HOST:-db}}"
export ODOO_DB_PORT="${ODOO_DB_PORT:-5432}"
export ODOO_DB_USER="${ODOO_DB_USER:-${USER:-odoo}}"
export ODOO_DB_PASSWORD="${ODOO_DB_PASSWORD:-${PASSWORD:-}}"
export ODOO_MASTER_PASSWORD="${ODOO_MASTER_PASSWORD:-}"
export ODOO_PROXY_MODE="${ODOO_PROXY_MODE:-True}"
export ODOO_WITHOUT_DEMO="${ODOO_WITHOUT_DEMO:-True}"
export ODOO_WORKERS="${ODOO_WORKERS:-0}"
export ODOO_LIMIT_TIME_CPU="${ODOO_LIMIT_TIME_CPU:-120}"
export ODOO_LIMIT_TIME_REAL="${ODOO_LIMIT_TIME_REAL:-240}"
export ODOO_LOG_LEVEL="${ODOO_LOG_LEVEL:-info}"
export ODOO_DB_FILTER="${ODOO_DB_FILTER:-.*}"
export ODOO_LIST_DB="${ODOO_LIST_DB:-True}"

if [[ -z "$ODOO_DB_PASSWORD" ]]; then
    echo "ODOO_DB_PASSWORD is required. Set it in secrets/.env.secrets or a managed secret store." >&2
    exit 1
fi

if [[ -z "$ODOO_MASTER_PASSWORD" ]]; then
    echo "ODOO_MASTER_PASSWORD is required. Set it in secrets/.env.secrets or a managed secret store." >&2
    exit 1
fi

if [[ "${TIJARA_ENV:-development}" == "production" ]]; then
    for secret_value in "$ODOO_DB_PASSWORD" "$ODOO_MASTER_PASSWORD"; do
        if [[ "$secret_value" == replace-with-* || "$secret_value" == "change-me-in-production" || "$secret_value" == "odoo_dev_password" ]]; then
            echo "Refusing to start production with placeholder or development secrets." >&2
            exit 1
        fi
    done
    if [[ -n "${TIJARA_METRICS_TOKEN:-}" && ( "${TIJARA_METRICS_TOKEN}" == dummy-* || "${TIJARA_METRICS_TOKEN}" == replace-with-* ) ]]; then
        echo "Refusing to start production with a placeholder TIJARA_METRICS_TOKEN." >&2
        exit 1
    fi
fi

python3 - "$CONFIG_TEMPLATE" "$RUNTIME_CONFIG" <<'PY'
import os
import sys
from pathlib import Path

template_path = Path(sys.argv[1])
runtime_path = Path(sys.argv[2])

template = template_path.read_text()
keys = [
    "ODOO_MASTER_PASSWORD",
    "ODOO_DB_HOST",
    "ODOO_DB_PORT",
    "ODOO_DB_USER",
    "ODOO_DB_PASSWORD",
    "ODOO_PROXY_MODE",
    "ODOO_WITHOUT_DEMO",
    "ODOO_WORKERS",
    "ODOO_LIMIT_TIME_CPU",
    "ODOO_LIMIT_TIME_REAL",
    "ODOO_LOG_LEVEL",
    "ODOO_DB_FILTER",
    "ODOO_LIST_DB",
]

for key in keys:
    template = template.replace("${" + key + "}", os.environ[key])

runtime_path.write_text(template)
PY

exec odoo --config="$RUNTIME_CONFIG" "$@"
