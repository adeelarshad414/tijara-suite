#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/dev-pids.txt"

cd "$ROOT_DIR"
mkdir -p "$LOG_DIR"

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

kill_recorded_pids() {
    [ -f "$PID_FILE" ] || return 0
    while read -r pid _name; do
        case "$pid" in
            ""|0|*[!0-9]*) continue ;;
        esac
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done <"$PID_FILE"
}

kill_port_if_requested() {
    local port="$1"
    if [ "${TIJARA_FORCE_KILL_PORTS:-0}" != "1" ]; then
        return 0
    fi
    if command -v lsof >/dev/null 2>&1; then
        local pids
        pids="$(lsof -ti ":$port" 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill -9 2>/dev/null || true
        fi
    fi
}

port_status() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1 && lsof -ti ":$port" >/dev/null 2>&1; then
        echo "Port $port still in use"
    else
        echo "Port $port is free"
    fi
}

echo "Stopping Tijara Suite Compose services..."
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    compose_cmd --profile hardware --profile monitoring down || compose_cmd down || true
fi

kill_recorded_pids

HTTP_PORT="$(read_env HTTP_PORT 8069)"
LONGPOLLING_PORT="$(read_env LONGPOLLING_PORT 8072)"
BRIDGE_PORT="$(read_env TIJARA_BRIDGE_PORT 9109)"
PROMETHEUS_PORT="$(read_env PROMETHEUS_PORT 9090)"
BLACKBOX_PORT="$(read_env BLACKBOX_PORT 9115)"
ALERTMANAGER_PORT="$(read_env ALERTMANAGER_PORT 9093)"
LOKI_PORT="$(read_env LOKI_PORT 3100)"
GRAFANA_PORT="$(read_env GRAFANA_PORT 3000)"

for port in "$HTTP_PORT" "$LONGPOLLING_PORT" 5432 "$BRIDGE_PORT" "$PROMETHEUS_PORT" "$BLACKBOX_PORT" "$ALERTMANAGER_PORT" "$LOKI_PORT" "$GRAFANA_PORT"; do
    kill_port_if_requested "$port"
done

: >"$PID_FILE"

echo
for port in "$HTTP_PORT" "$LONGPOLLING_PORT" 5432 "$BRIDGE_PORT" "$PROMETHEUS_PORT" "$BLACKBOX_PORT" "$ALERTMANAGER_PORT" "$LOKI_PORT" "$GRAFANA_PORT"; do
    port_status "$port"
done

echo
echo "All Tijara Suite Compose services stopped."
echo "Set TIJARA_FORCE_KILL_PORTS=1 before running this script to force-kill any non-Compose process still occupying known ports."
