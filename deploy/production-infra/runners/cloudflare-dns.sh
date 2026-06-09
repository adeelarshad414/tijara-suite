#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  bash deploy/production-infra/runners/cloudflare-dns.sh apply --zone-id-env CLOUDFLARE_ZONE_ID --token-env CLOUDFLARE_API_TOKEN --hostname app.example.com --target ingress.example.com --record-type CNAME --ttl 300
  bash deploy/production-infra/runners/cloudflare-dns.sh rollback --zone-id-env CLOUDFLARE_ZONE_ID --token-env CLOUDFLARE_API_TOKEN --hostname app.example.com --record-id-env CLOUDFLARE_RECORD_ID

Real Cloudflare calls require CONFIRM_PROVIDER_ACTION=YES. Without that
confirmation this script prints a redacted dry-run plan only.
USAGE
}

ACTION="${1:-}"
if [[ -z "$ACTION" || "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi
shift

ZONE_ID_ENV="CLOUDFLARE_ZONE_ID"
TOKEN_ENV="CLOUDFLARE_API_TOKEN"
RECORD_ID_ENV="CLOUDFLARE_RECORD_ID"
HOSTNAME=""
TARGET=""
RECORD_TYPE="CNAME"
TTL="300"
PROXIED="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --zone-id-env) ZONE_ID_ENV="${2:-}"; shift 2 ;;
        --token-env) TOKEN_ENV="${2:-}"; shift 2 ;;
        --record-id-env) RECORD_ID_ENV="${2:-}"; shift 2 ;;
        --hostname) HOSTNAME="${2:-}"; shift 2 ;;
        --target) TARGET="${2:-}"; shift 2 ;;
        --record-type) RECORD_TYPE="${2:-}"; shift 2 ;;
        --ttl) TTL="${2:-}"; shift 2 ;;
        --proxied) PROXIED="${2:-}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

require_value() {
    local name="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        echo "$name is required." >&2
        exit 2
    fi
}

require_value "--hostname" "$HOSTNAME"
if [[ "$ACTION" == "apply" ]]; then
    require_value "--target" "$TARGET"
fi

CONFIRMED="${CONFIRM_PROVIDER_ACTION:-NO}"
ZONE_ID="${!ZONE_ID_ENV:-}"
TOKEN="${!TOKEN_ENV:-}"
RECORD_ID="${!RECORD_ID_ENV:-}"

if [[ "$CONFIRMED" != "YES" ]]; then
    echo "[dry-run] cloudflare action=$ACTION hostname=$HOSTNAME target=${TARGET:-<unset>} record_type=$RECORD_TYPE ttl=$TTL zone_id_env=$ZONE_ID_ENV token_env=$TOKEN_ENV record_id_env=$RECORD_ID_ENV"
    exit 0
fi

require_value "$ZONE_ID_ENV" "$ZONE_ID"
require_value "$TOKEN_ENV" "$TOKEN"
command -v curl >/dev/null 2>&1 || { echo "curl is required for Cloudflare DNS calls." >&2; exit 127; }

case "$ACTION" in
    apply)
        curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            --data "{\"type\":\"$RECORD_TYPE\",\"name\":\"$HOSTNAME\",\"content\":\"$TARGET\",\"ttl\":$TTL,\"proxied\":$PROXIED}"
        ;;
    rollback)
        require_value "$RECORD_ID_ENV" "$RECORD_ID"
        curl -sS -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
            -H "Authorization: Bearer $TOKEN"
        ;;
    *)
        echo "Unknown action: $ACTION" >&2
        usage >&2
        exit 2
        ;;
esac
