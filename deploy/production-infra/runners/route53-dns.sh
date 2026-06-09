#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  bash deploy/production-infra/runners/route53-dns.sh apply --hosted-zone-id-env ROUTE53_HOSTED_ZONE_ID --hostname app.example.com --target ingress.example.com --record-type CNAME --ttl 300
  bash deploy/production-infra/runners/route53-dns.sh rollback --hosted-zone-id-env ROUTE53_HOSTED_ZONE_ID --hostname app.example.com --record-type CNAME --previous-target-env ROUTE53_PREVIOUS_TARGET

Real Route53 calls require CONFIRM_PROVIDER_ACTION=YES. Without that
confirmation this script prints a redacted dry-run plan only.
USAGE
}

ACTION="${1:-}"
if [[ -z "$ACTION" || "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi
shift

HOSTED_ZONE_ID_ENV="ROUTE53_HOSTED_ZONE_ID"
PREVIOUS_TARGET_ENV="ROUTE53_PREVIOUS_TARGET"
HOSTNAME=""
TARGET=""
RECORD_TYPE="CNAME"
TTL="300"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --hosted-zone-id-env) HOSTED_ZONE_ID_ENV="${2:-}"; shift 2 ;;
        --previous-target-env) PREVIOUS_TARGET_ENV="${2:-}"; shift 2 ;;
        --hostname) HOSTNAME="${2:-}"; shift 2 ;;
        --target) TARGET="${2:-}"; shift 2 ;;
        --record-type) RECORD_TYPE="${2:-}"; shift 2 ;;
        --ttl) TTL="${2:-}"; shift 2 ;;
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
HOSTED_ZONE_ID="${!HOSTED_ZONE_ID_ENV:-}"
PREVIOUS_TARGET="${!PREVIOUS_TARGET_ENV:-}"

if [[ "$CONFIRMED" != "YES" ]]; then
    echo "[dry-run] route53 action=$ACTION hostname=$HOSTNAME target=${TARGET:-<unset>} previous_target_env=$PREVIOUS_TARGET_ENV record_type=$RECORD_TYPE ttl=$TTL hosted_zone_id_env=$HOSTED_ZONE_ID_ENV"
    exit 0
fi

require_value "$HOSTED_ZONE_ID_ENV" "$HOSTED_ZONE_ID"
command -v aws >/dev/null 2>&1 || { echo "aws CLI is required for Route53 DNS calls." >&2; exit 127; }

tmp_json="$(mktemp)"
trap 'rm -f "$tmp_json"' EXIT

case "$ACTION" in
    apply)
        cat > "$tmp_json" <<JSON
{
  "Comment": "Tijara tenant DNS apply",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$HOSTNAME",
        "Type": "$RECORD_TYPE",
        "TTL": $TTL,
        "ResourceRecords": [{"Value": "$TARGET"}]
      }
    }
  ]
}
JSON
        aws route53 change-resource-record-sets --hosted-zone-id "$HOSTED_ZONE_ID" --change-batch "file://$tmp_json"
        ;;
    rollback)
        require_value "$PREVIOUS_TARGET_ENV" "$PREVIOUS_TARGET"
        cat > "$tmp_json" <<JSON
{
  "Comment": "Tijara tenant DNS rollback",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$HOSTNAME",
        "Type": "$RECORD_TYPE",
        "TTL": $TTL,
        "ResourceRecords": [{"Value": "$PREVIOUS_TARGET"}]
      }
    }
  ]
}
JSON
        aws route53 change-resource-record-sets --hosted-zone-id "$HOSTED_ZONE_ID" --change-batch "file://$tmp_json"
        ;;
    *)
        echo "Unknown action: $ACTION" >&2
        usage >&2
        exit 2
        ;;
esac
