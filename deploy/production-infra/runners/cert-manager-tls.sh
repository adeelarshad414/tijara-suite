#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  bash deploy/production-infra/runners/cert-manager-tls.sh apply --namespace tijara --domain app.example.com --tls-secret app-tls --issuer letsencrypt-prod
  bash deploy/production-infra/runners/cert-manager-tls.sh rollback --namespace tijara --domain app.example.com --tls-secret app-tls

Real kubectl changes require CONFIRM_PROVIDER_ACTION=YES. Without that
confirmation this script prints the Certificate manifest or rollback command.
USAGE
}

ACTION="${1:-}"
if [[ -z "$ACTION" || "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi
shift

NAMESPACE="tijara"
DOMAIN=""
TLS_SECRET=""
ISSUER="letsencrypt-prod"
CERT_NAME=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --namespace) NAMESPACE="${2:-}"; shift 2 ;;
        --domain) DOMAIN="${2:-}"; shift 2 ;;
        --tls-secret) TLS_SECRET="${2:-}"; shift 2 ;;
        --issuer) ISSUER="${2:-}"; shift 2 ;;
        --certificate-name) CERT_NAME="${2:-}"; shift 2 ;;
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

require_value "--domain" "$DOMAIN"
require_value "--tls-secret" "$TLS_SECRET"

if [[ -z "$CERT_NAME" ]]; then
    CERT_NAME="$(printf '%s' "$DOMAIN" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g; s/--*/-/g; s/^-//; s/-$//')"
fi

render_certificate() {
    cat <<YAML
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: $CERT_NAME
  namespace: $NAMESPACE
spec:
  secretName: $TLS_SECRET
  dnsNames:
    - $DOMAIN
  issuerRef:
    name: $ISSUER
    kind: ClusterIssuer
YAML
}

CONFIRMED="${CONFIRM_PROVIDER_ACTION:-NO}"

case "$ACTION" in
    apply)
        if [[ "$CONFIRMED" != "YES" ]]; then
            echo "[dry-run] cert-manager apply namespace=$NAMESPACE domain=$DOMAIN tls_secret=$TLS_SECRET issuer=$ISSUER"
            render_certificate
            exit 0
        fi
        command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required for cert-manager TLS calls." >&2; exit 127; }
        render_certificate | kubectl apply -f -
        ;;
    rollback)
        if [[ "$CONFIRMED" != "YES" ]]; then
            echo "[dry-run] kubectl -n $NAMESPACE delete certificate $CERT_NAME --ignore-not-found=true"
            echo "[dry-run] kubectl -n $NAMESPACE delete secret $TLS_SECRET --ignore-not-found=true"
            exit 0
        fi
        command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required for cert-manager TLS calls." >&2; exit 127; }
        kubectl -n "$NAMESPACE" delete certificate "$CERT_NAME" --ignore-not-found=true
        kubectl -n "$NAMESPACE" delete secret "$TLS_SECRET" --ignore-not-found=true
        ;;
    *)
        echo "Unknown action: $ACTION" >&2
        usage >&2
        exit 2
        ;;
esac
