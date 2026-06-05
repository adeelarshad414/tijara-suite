#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


RESERVED_DATABASES = {"postgres", "template0", "template1"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(value):
    return re.sub(r"[^a-z0-9-]+", "-", str(value or "").lower().replace("_", "-")).strip("-")


def _validate_database_name(value):
    if not re.match(r"^[A-Za-z0-9_]+$", value or ""):
        raise ValueError("Tenant database must use only letters, numbers, and underscores.")
    if value in RESERVED_DATABASES:
        raise ValueError("Refusing to generate operations artifacts for reserved database: %s" % value)


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate tenant DNS, ingress, backup, and monitoring artifacts.")
    parser.add_argument("tenant_db")
    parser.add_argument("domain")
    parser.add_argument("--admin-email", default="")
    parser.add_argument("--admin-login", default="admin")
    parser.add_argument("--tenant-name", default="")
    parser.add_argument("--dns-provider", default="manual")
    parser.add_argument("--dns-target", default="tijara-ingress")
    parser.add_argument("--ingress-class", default="nginx")
    parser.add_argument("--namespace", default="tijara")
    parser.add_argument("--service-name", default="odoo")
    parser.add_argument("--service-port", default="8069")
    parser.add_argument("--tls-issuer", default="letsencrypt-prod")
    parser.add_argument("--backup-policy", default="daily")
    parser.add_argument("--backup-retention-days", type=int, default=30)
    parser.add_argument("--restore-drill-ref", default="")
    parser.add_argument("--monitoring", default="true", choices=["true", "false"])
    parser.add_argument("--alert-route", default="")
    parser.add_argument("--monitoring-dashboard-ref", default="")
    parser.add_argument("--output-dir", default="deploy/runtime/tenants")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        _validate_database_name(args.tenant_db)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    tenant_dir = Path(args.output_dir) / args.tenant_db
    tenant_dir.mkdir(parents=True, exist_ok=True)
    monitoring_enabled = _truthy(args.monitoring)
    tenant_slug = _slug(args.tenant_db)
    tls_secret = "%s-tls" % tenant_slug
    tenant_name = args.tenant_name or args.tenant_db.replace("_", " ").title()
    blackbox_url = "https://%s/web/login" % args.domain
    smoke_checks = [
        "tenant-web-login",
        "database-isolation-header",
        "admin-login-created",
        "module-install-complete",
        "subscription-feature-flags-applied",
        "pos-checkout-smoke",
        "inventory-adjustment-smoke",
        "receipt-render-smoke",
        "display-route-smoke",
        "backup-job-registered",
        "monitoring-target-healthy",
    ]
    manifest = {
        "context": {
            "generated_at": _utc_now(),
            "generator": "scripts/generate_tenant_ops_manifest.py",
            "artifact_schema": "tenant-ops/v1",
        },
        "tenant": {
            "name": tenant_name,
            "database": args.tenant_db,
            "domain": args.domain,
        },
        "dns": {
            "provider": args.dns_provider,
            "hostname": args.domain,
            "target": args.dns_target,
            "record_type": "CNAME",
            "mode": "manual-or-provider-api",
        },
        "ingress": {
            "class": args.ingress_class,
            "host": args.domain,
            "database_header": args.tenant_db,
            "namespace": args.namespace,
            "service_name": args.service_name,
            "service_port": args.service_port,
            "tls_issuer": args.tls_issuer,
            "tls_secret": tls_secret,
        },
        "admin": {
            "email": args.admin_email,
            "login": args.admin_login,
            "bootstrap_secret_ref": "secret-manager:%s/admin-bootstrap" % tenant_slug,
        },
        "backup": {
            "policy": args.backup_policy,
            "database": args.tenant_db,
            "retention_days": max(args.backup_retention_days, 1),
            "restore_drill_required": True,
            "restore_drill_ref": args.restore_drill_ref,
        },
        "monitoring": {
            "enabled": monitoring_enabled,
            "blackbox_url": blackbox_url,
            "alert_route": args.alert_route,
            "dashboard_ref": args.monitoring_dashboard_ref,
            "labels": {"tenant_db": args.tenant_db, "job": "tijara-tenant"},
        },
        "smoke_checks": smoke_checks,
        "artifacts": {
            "nginx_location": "nginx-location.conf",
            "kubernetes_ingress": "k8s-ingress.yaml",
            "external_dns_record": "external-dns-record.json",
            "cert_manager_certificate": "cert-manager-certificate.yaml",
            "backup_policy": "backup-policy.json",
            "prometheus_blackbox_target": "prometheus-blackbox-target.json",
            "admin_bootstrap": "admin-bootstrap.md",
            "smoke_checklist": "smoke-checklist.md",
        },
    }
    _write(tenant_dir / "ops-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(
        tenant_dir / "nginx-location.conf",
        "\n".join(
            [
                "# Include in the tenant server block after TLS is configured.",
                "proxy_set_header X-Odoo-dbfilter ^%s$;" % args.tenant_db,
                "proxy_set_header X-Forwarded-Host %s;" % args.domain,
                "proxy_pass http://%s:%s;" % (args.service_name, args.service_port),
            ]
        ),
    )
    _write(
        tenant_dir / "prometheus-blackbox-target.json",
        json.dumps(
            [
                {
                    "targets": [blackbox_url],
                    "labels": {
                        "tenant_db": args.tenant_db,
                        "tenant_domain": args.domain,
                        "job": "tijara-tenant",
                    },
                }
            ],
            indent=2,
            sort_keys=True,
        ),
    )
    _write(
        tenant_dir / "k8s-ingress.yaml",
        """
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {tenant_slug}
  namespace: {namespace}
  annotations:
    kubernetes.io/ingress.class: {ingress_class}
    cert-manager.io/cluster-issuer: {tls_issuer}
    external-dns.alpha.kubernetes.io/hostname: {domain}
spec:
  ingressClassName: {ingress_class}
  tls:
    - hosts:
        - {domain}
      secretName: {tls_secret}
  rules:
    - host: {domain}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {service_name}
                port:
                  number: {service_port}
""".format(
            tenant_slug=tenant_slug,
            namespace=args.namespace,
            ingress_class=args.ingress_class,
            tls_issuer=args.tls_issuer,
            domain=args.domain,
            tls_secret=tls_secret,
            service_name=args.service_name,
            service_port=args.service_port,
        ),
    )
    _write(
        tenant_dir / "external-dns-record.json",
        json.dumps(
            {
                "provider": args.dns_provider,
                "hostname": args.domain,
                "target": args.dns_target,
                "record_type": "CNAME",
                "ttl": 300,
                "mode": "manual-or-provider-api",
            },
            indent=2,
            sort_keys=True,
        ),
    )
    _write(
        tenant_dir / "cert-manager-certificate.yaml",
        """
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: {tenant_slug}
  namespace: {namespace}
spec:
  secretName: {tls_secret}
  dnsNames:
    - {domain}
  issuerRef:
    name: {tls_issuer}
    kind: ClusterIssuer
""".format(
            tenant_slug=tenant_slug,
            namespace=args.namespace,
            tls_secret=tls_secret,
            domain=args.domain,
            tls_issuer=args.tls_issuer,
        ),
    )
    _write(
        tenant_dir / "backup-policy.json",
        json.dumps(
            {
                "tenant_db": args.tenant_db,
                "policy": args.backup_policy,
                "retention_days": max(args.backup_retention_days, 1),
                "restore_drill_required": True,
                "restore_drill_ref": args.restore_drill_ref,
                "artifact": "deploy/postgres/README.md",
            },
            indent=2,
            sort_keys=True,
        ),
    )
    _write(
        tenant_dir / "admin-bootstrap.md",
        """
# Tenant Admin Bootstrap

- Tenant: {tenant_name}
- Database: {tenant_db}
- Domain: {domain}
- Admin login: {admin_login}
- Admin email: {admin_email}
- Secret reference: secret-manager:{tenant_slug}/admin-bootstrap

Store the initial password in the configured secret manager. Do not write
passwords or API tokens into this artifact directory.
""".format(
            tenant_name=tenant_name,
            tenant_db=args.tenant_db,
            domain=args.domain,
            admin_login=args.admin_login,
            admin_email=args.admin_email or "<set-before-production>",
            tenant_slug=tenant_slug,
        ),
    )
    _write(
        tenant_dir / "smoke-checklist.md",
        "\n".join(
            ["# Tenant Smoke Checklist", "", "- Tenant: %s" % tenant_name, "- Domain: %s" % args.domain, ""]
            + ["- [ ] %s" % check for check in smoke_checks]
        ),
    )
    print("Generated tenant operations artifacts in %s" % tenant_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
