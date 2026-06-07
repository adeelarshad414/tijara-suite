#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/dev-pids.txt"
CONTAINER_FILE="$LOG_DIR/dev-containers.txt"

cd "$ROOT_DIR"
mkdir -p "$LOG_DIR"
: >"$PID_FILE"
: >"$CONTAINER_FILE"

read_env() {
    local key="$1"
    local fallback="$2"
    local value=""
    if [ -f "$ROOT_DIR/.env" ]; then
        value="$(awk -F= -v k="$key" '$1 == k {print substr($0, index($0, "=") + 1)}' "$ROOT_DIR/.env" | tail -n 1)"
    fi
    if [ -n "$value" ]; then
        printf "%s" "$value"
    else
        printf "%s" "$fallback"
    fi
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

require_command() {
    local name="$1"
    local install_hint="$2"
    if ! has_command "$name"; then
        echo "Missing required command: $name"
        echo "Install: $install_hint"
        exit 1
    fi
}

compose_cmd() {
    local args=(docker compose)
    if [ -f "$ROOT_DIR/.env" ]; then
        args+=(--env-file "$ROOT_DIR/.env")
    fi
    if [ -f "$ROOT_DIR/secrets/.env.secrets" ]; then
        args+=(--env-file "$ROOT_DIR/secrets/.env.secrets")
    fi
    "${args[@]}" "$@"
}

wait_for_http() {
    local label="$1"
    local url="$2"
    local max_seconds="${3:-60}"
    local elapsed=0
    while [ "$elapsed" -lt "$max_seconds" ]; do
        if has_command curl && curl -fsS "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    echo "$label did not become healthy within ${max_seconds}s: $url"
    return 1
}

copy_env_if_missing() {
    if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
        echo "Created .env from .env.example"
    fi
    if [ ! -f "$ROOT_DIR/secrets/.env.secrets" ] && [ -f "$ROOT_DIR/secrets/.env.secrets.example" ]; then
        mkdir -p "$ROOT_DIR/secrets"
        cp "$ROOT_DIR/secrets/.env.secrets.example" "$ROOT_DIR/secrets/.env.secrets"
        echo "Created secrets/.env.secrets from secrets/.env.secrets.example"
        echo "Review placeholder secrets before production or shared staging use."
    fi
}

record_containers() {
    compose_cmd ps -q >"$CONTAINER_FILE" || true
    while IFS= read -r container_id; do
        [ -n "$container_id" ] || continue
        if has_command docker; then
            docker inspect --format '{{.State.Pid}} {{.Name}}' "$container_id" 2>/dev/null >>"$PID_FILE" || true
        fi
    done <"$CONTAINER_FILE"
}

print_credentials() {
    local credentials="$ROOT_DIR/docs/TEST_CREDENTIALS.csv"
    if [ ! -f "$credentials" ]; then
        return 0
    fi
    echo
    echo "Demo credentials from docs/TEST_CREDENTIALS.csv:"
    awk -F, 'NR == 1 {next} NR <= 6 {printf "  - %s: %s / %s\n", $1, $2, $3}' "$credentials"
}

require_command docker "https://docs.docker.com/get-docker/"
if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is required. Install Docker Desktop or the compose plugin."
    exit 1
fi

if [ -f "$ROOT_DIR/package.json" ]; then
    require_command node "https://nodejs.org/"
    require_command npm "https://nodejs.org/"
    if [ ! -d "$ROOT_DIR/node_modules" ]; then
        echo "Installing Node dependencies..."
        npm install
    fi
fi

if ! has_command python3; then
    echo "python3 is recommended for release evidence scripts: https://www.python.org/downloads/"
fi

copy_env_if_missing

echo "Validating Docker Compose configuration..."
compose_cmd config >/dev/null

echo "Starting Tijara Suite core services..."
compose_cmd up -d

if [ "${TIJARA_DEV_START_HARDWARE:-0}" = "1" ]; then
    echo "Starting hardware bridge profile..."
    compose_cmd --profile hardware up -d hardware_bridge
fi

if [ "${TIJARA_DEV_START_MONITORING:-0}" = "1" ]; then
    echo "Starting monitoring profile..."
    compose_cmd --profile monitoring up -d prometheus blackbox alertmanager loki grafana
fi

record_containers

HTTP_PORT="$(read_env HTTP_PORT 8069)"
LONGPOLLING_PORT="$(read_env LONGPOLLING_PORT 8072)"
BRIDGE_PORT="$(read_env TIJARA_BRIDGE_PORT 9109)"
PROMETHEUS_PORT="$(read_env PROMETHEUS_PORT 9090)"
GRAFANA_PORT="$(read_env GRAFANA_PORT 3000)"

wait_for_http "Odoo web" "http://localhost:${HTTP_PORT}/web/login" 60 || true

if [ "${TIJARA_DEV_INSTALL_SUITE:-0}" = "1" ]; then
    echo "Installing Tijara modules into ${DB:-tijara_dev}..."
    make install-suite DB="${DB:-tijara_dev}"
fi

if [ "${TIJARA_DEV_SEED_POS_DEMO:-0}" = "1" ]; then
    echo "Installing Tijara POS demo seed into ${DB:-tijara_dev}..."
    make seed-pos-demo DB="${DB:-tijara_dev}"
fi

echo
printf "%-22s %-34s %-12s\n" "Service" "URL" "Status"
printf "%-22s %-34s %-12s\n" "Odoo web" "http://localhost:${HTTP_PORT}" "started"
printf "%-22s %-34s %-12s\n" "Odoo longpolling" "http://localhost:${LONGPOLLING_PORT}" "started"
printf "%-22s %-34s %-12s\n" "PostgreSQL" "localhost:5432" "started"
if [ "${TIJARA_DEV_START_HARDWARE:-0}" = "1" ]; then
    printf "%-22s %-34s %-12s\n" "Hardware bridge" "http://localhost:${BRIDGE_PORT}" "started"
fi
if [ "${TIJARA_DEV_START_MONITORING:-0}" = "1" ]; then
    printf "%-22s %-34s %-12s\n" "Prometheus" "http://localhost:${PROMETHEUS_PORT}" "started"
    printf "%-22s %-34s %-12s\n" "Grafana" "http://localhost:${GRAFANA_PORT}" "started"
fi

print_credentials

echo
echo "Logs:"
echo "  docker compose logs -f odoo"
echo "  tail -f logs/*.log"
echo
echo "Stop everything with: bash scripts/dev-stop.sh"
