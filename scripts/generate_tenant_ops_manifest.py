#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate tenant DNS, ingress, backup, and monitoring artifacts.")
    parser.add_argument("tenant_db")
    parser.add_argument("domain")
    parser.add_argument("--admin-email", default="")
    parser.add_argument("--ingress-class", default="nginx")
    parser.add_argument("--backup-policy", default="daily")
    parser.add_argument("--monitoring", default="true", choices=["true", "false"])
    parser.add_argument("--output-dir", default="deploy/runtime/tenants")
    return parser.parse_args()


def main():
    args = parse_args()
    tenant_dir = Path(args.output_dir) / args.tenant_db
    tenant_dir.mkdir(parents=True, exist_ok=True)
    monitoring_enabled = args.monitoring == "true"
    manifest = {
        "tenant": {"database": args.tenant_db, "domain": args.domain},
        "dns": {"hostname": args.domain, "target": "tijara-ingress", "mode": "manual-or-provider-api"},
        "ingress": {
            "class": args.ingress_class,
            "host": args.domain,
            "database_header": args.tenant_db,
            "tls_secret": args.tenant_db.replace("_", "-") + "-tls",
        },
        "admin": {"email": args.admin_email, "login": "admin"},
        "backup": {"policy": args.backup_policy, "database": args.tenant_db},
        "monitoring": {
            "enabled": monitoring_enabled,
            "blackbox_url": "https://%s/web/login" % args.domain,
        },
    }
    (tenant_dir / "ops-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (tenant_dir / "nginx-location.conf").write_text(
        "\n".join(
            [
                "# Include in the tenant server block after TLS is configured.",
                "proxy_set_header X-Odoo-dbfilter ^%s$;" % args.tenant_db,
                "proxy_set_header X-Forwarded-Host %s;" % args.domain,
                "proxy_pass http://odoo:8069;",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tenant_dir / "prometheus-blackbox-target.json").write_text(
        json.dumps(
            [
                {
                    "targets": ["https://%s/web/login" % args.domain],
                    "labels": {"tenant_db": args.tenant_db, "job": "tijara-tenant"},
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Generated tenant operations artifacts in %s" % tenant_dir)


if __name__ == "__main__":
    main()
