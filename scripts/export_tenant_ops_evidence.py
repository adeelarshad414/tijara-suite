#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RESERVED_DATABASES = {"postgres", "template0", "template1"}
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
EXPECTED_ARTIFACTS = [
    "ops-manifest.json",
    "nginx-location.conf",
    "k8s-ingress.yaml",
    "external-dns-record.json",
    "cert-manager-certificate.yaml",
    "backup-policy.json",
    "prometheus-blackbox-target.json",
    "admin-bootstrap.md",
    "smoke-checklist.md",
]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _metadata_items(items):
    metadata = {}
    for raw in items or []:
        if "=" not in raw:
            raise ValueError("Metadata must use key=value format: %s" % raw)
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Metadata key cannot be blank.")
        metadata[key] = value.strip()
    return metadata


def _secret_like_keys(metadata):
    flagged = []
    for key in metadata:
        normalized = str(key).lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _resolve_path(raw_path):
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _hash_file(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _safe_relative(path):
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _valid_database_name(value):
    if not re.match(r"^[A-Za-z0-9_]+$", value or ""):
        return False
    return value not in RESERVED_DATABASES


def _positive_int(value):
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _add_check(rows, tenant_blockers, tenant_warnings, strict, name, passed, message):
    if passed:
        rows.append(_row(name, "passed", message))
        return
    if strict:
        tenant_blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        tenant_warnings.append(message)
        rows.append(_row(name, "warning", message))


def _tenant_paths(args):
    values = list(args.tenant_artifact or [])
    values.extend(_csv_items(os.environ.get("TIJARA_TENANT_OPS_ARTIFACTS")))
    deduped = []
    seen = set()
    for raw in values:
        if raw not in seen:
            seen.add(raw)
            deduped.append(raw)
    return [_resolve_path(raw) for raw in deduped]


def _tenant_review(path, strict, require_dns_provider, require_admin_email, require_restore_drill, require_monitoring, require_all_artifacts):
    rows = []
    blockers = []
    warnings = []
    tenant_dir = path if path.is_dir() else path.parent
    manifest_path = path if path.is_file() else tenant_dir / "ops-manifest.json"
    manifest = _read_json(manifest_path)
    if not manifest:
        message = "Tenant operations manifest is missing or unreadable: %s" % manifest_path
        blockers.append(message)
        rows.append(_row("manifest-readable", "failed", message))
        return {
            "path": _safe_relative(tenant_dir),
            "tenant_db": "",
            "domain": "",
            "decision": "failed",
            "ci_status": "fail",
            "artifact_count": 0,
            "missing_artifacts": EXPECTED_ARTIFACTS,
            "checks": rows,
            "blockers": blockers,
            "warnings": warnings,
        }

    rows.append(_row("manifest-readable", "passed", "Tenant operations manifest is readable."))
    tenant = manifest.get("tenant") or {}
    dns = manifest.get("dns") or {}
    ingress = manifest.get("ingress") or {}
    admin = manifest.get("admin") or {}
    backup = manifest.get("backup") or {}
    monitoring = manifest.get("monitoring") or {}
    smoke_checks = manifest.get("smoke_checks") or []
    backup_retention_ok = _positive_int(backup.get("retention_days"))

    tenant_db = tenant.get("database", "")
    domain = tenant.get("domain") or dns.get("hostname") or ingress.get("host", "")
    artifact_hashes = {}
    missing_artifacts = []
    for artifact in EXPECTED_ARTIFACTS:
        artifact_path = tenant_dir / artifact
        if artifact_path.is_file():
            artifact_hashes[artifact] = _hash_file(artifact_path)
        else:
            missing_artifacts.append(artifact)

    _add_check(
        rows,
        blockers,
        warnings,
        strict,
        "tenant-database",
        _valid_database_name(tenant_db),
        "Tenant database name is valid." if _valid_database_name(tenant_db) else "Tenant database name is missing, invalid, or reserved.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict,
        "tenant-domain",
        _present(domain),
        "Tenant domain is recorded." if _present(domain) else "Tenant domain is required.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict,
        "dns-target",
        _present(dns.get("target")),
        "DNS target is recorded." if _present(dns.get("target")) else "DNS target is required.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict and require_dns_provider,
        "dns-provider",
        (not require_dns_provider) or _present(dns.get("provider")),
        "DNS provider is recorded."
        if _present(dns.get("provider"))
        else "DNS provider reference is required for production tenant rollout.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict,
        "ingress-host",
        _present(ingress.get("host")) and _present(ingress.get("tls_secret")),
        "Ingress host and TLS secret reference are recorded."
        if _present(ingress.get("host")) and _present(ingress.get("tls_secret"))
        else "Ingress host and TLS secret reference are required.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict and require_admin_email,
        "admin-bootstrap",
        _present(admin.get("login")) and ((not require_admin_email) or _present(admin.get("email"))),
        "Admin bootstrap login%s is recorded."
        % ("/email" if _present(admin.get("email")) else "")
        if _present(admin.get("login")) and ((not require_admin_email) or _present(admin.get("email")))
        else "Admin bootstrap login and production admin email are required.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict,
        "backup-policy",
        _present(backup.get("policy")) and backup_retention_ok,
        "Backup policy and retention are recorded."
        if _present(backup.get("policy")) and backup_retention_ok
        else "Backup policy and positive retention days are required.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict and require_restore_drill,
        "restore-drill",
        (not require_restore_drill) or _present(backup.get("restore_drill_ref")),
        (
            "Restore drill reference is recorded."
            if _present(backup.get("restore_drill_ref"))
            else "Restore drill reference is optional for this run."
        )
        if (not require_restore_drill) or _present(backup.get("restore_drill_ref"))
        else "Restore drill reference is required for production tenant rollout.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict and require_monitoring,
        "monitoring-target",
        (not require_monitoring)
        or bool(monitoring.get("enabled"))
        and _present(monitoring.get("blackbox_url")),
        (
            "Monitoring target is enabled and recorded."
            if bool(monitoring.get("enabled")) and _present(monitoring.get("blackbox_url"))
            else "Monitoring target is optional for this run."
        )
        if (not require_monitoring)
        or bool(monitoring.get("enabled"))
        and _present(monitoring.get("blackbox_url"))
        else "Monitoring must be enabled with a Blackbox URL for production tenant rollout.",
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict,
        "smoke-checks",
        len(smoke_checks) >= 5,
        "%s smoke check(s) recorded." % len(smoke_checks),
    )
    _add_check(
        rows,
        blockers,
        warnings,
        strict and require_all_artifacts,
        "artifact-bundle",
        not missing_artifacts,
        "All expected tenant artifacts are present."
        if not missing_artifacts
        else "Missing tenant artifacts: %s" % ", ".join(missing_artifacts),
    )

    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    return {
        "path": _safe_relative(tenant_dir),
        "manifest_path": _safe_relative(manifest_path),
        "tenant_db": tenant_db,
        "domain": domain,
        "decision": decision,
        "ci_status": ci_status,
        "dns_provider": dns.get("provider", ""),
        "dns_target_present": _present(dns.get("target")),
        "ingress_host_present": _present(ingress.get("host")),
        "tls_secret_present": _present(ingress.get("tls_secret")),
        "admin_login_present": _present(admin.get("login")),
        "admin_email_present": _present(admin.get("email")),
        "backup_policy": backup.get("policy", ""),
        "backup_retention_days": backup.get("retention_days", 0),
        "restore_drill_reference_present": _present(backup.get("restore_drill_ref")),
        "monitoring_enabled": bool(monitoring.get("enabled")),
        "monitoring_blackbox_url_present": _present(monitoring.get("blackbox_url")),
        "monitoring_alert_route_present": _present(monitoring.get("alert_route")),
        "smoke_check_count": len(smoke_checks),
        "artifact_count": len(artifact_hashes),
        "expected_artifact_count": len(EXPECTED_ARTIFACTS),
        "missing_artifacts": missing_artifacts,
        "artifact_hashes": artifact_hashes,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }


def _summary(context, tenant_reviews, decision, blockers, warnings):
    tenant_lines = []
    for review in tenant_reviews:
        tenant_lines.append(
            "- %s (%s): %s, artifacts %s/%s, missing=%s"
            % (
                review.get("tenant_db") or "unknown",
                review.get("domain") or "no-domain",
                review.get("decision") or "unknown",
                review.get("artifact_count", 0),
                review.get("expected_artifact_count", len(EXPECTED_ARTIFACTS)),
                ", ".join(review.get("missing_artifacts") or []) or "none",
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    tenant_text = "\n".join(tenant_lines) or "- No tenant artifacts were reviewed."
    return f"""
# Tenant Operations Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Tenant artifacts reviewed: {context["tenant_count"]}
- Output directory: {context["output"]}

## Tenant Reviews

{tenant_text}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Tenant operations evidence: tenant-ops-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(
        description="Export tenant DNS/ingress/admin/backup/monitoring readiness evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_TENANT_OPS_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_TENANT_OPS_ENVIRONMENT", "production"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_TENANT_OPS_OUTPUT", ""))
    parser.add_argument("--tenant-artifact", action="append", default=[])
    parser.add_argument(
        "--minimum-tenants",
        type=int,
        default=int(os.environ.get("TIJARA_TENANT_OPS_MINIMUM_TENANTS", "1")),
    )
    parser.add_argument("--require-dns-provider", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_OPS_REQUIRE_DNS_PROVIDER")))
    parser.add_argument("--require-admin-email", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_OPS_REQUIRE_ADMIN_EMAIL")))
    parser.add_argument("--require-restore-drill", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_OPS_REQUIRE_RESTORE_DRILL")))
    parser.add_argument("--require-monitoring", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_OPS_REQUIRE_MONITORING", "1")))
    parser.add_argument("--require-all-artifacts", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_OPS_REQUIRE_ALL_ARTIFACTS")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_TENANT_OPS_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when tenant operations evidence is incomplete.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    require_dns_provider = args.require_dns_provider or strict
    require_admin_email = args.require_admin_email or strict
    require_restore_drill = args.require_restore_drill or strict
    require_monitoring = args.require_monitoring or strict
    require_all_artifacts = args.require_all_artifacts or strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/tenant-ops-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append(_row("metadata-format", "failed", str(error)))
    else:
        rows.append(_row("metadata-format", "passed", "%s metadata item(s) parsed." % len(metadata)))

    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append(_row("metadata-secret-safety", "failed", message))
    else:
        rows.append(_row("metadata-secret-safety", "passed", "No secret-like metadata keys found."))

    tenant_paths = _tenant_paths(args)
    if len(tenant_paths) < max(args.minimum_tenants, 0):
        message = "At least %s tenant artifact(s) are required; %s provided." % (
            max(args.minimum_tenants, 0),
            len(tenant_paths),
        )
        if strict:
            blockers.append(message)
            rows.append(_row("minimum-tenants", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("minimum-tenants", "warning", message))
    else:
        rows.append(_row("minimum-tenants", "passed", "%s tenant artifact(s) provided." % len(tenant_paths)))

    tenant_reviews = []
    for tenant_path in tenant_paths:
        review = _tenant_review(
            tenant_path,
            strict,
            require_dns_provider,
            require_admin_email,
            require_restore_drill,
            require_monitoring,
            require_all_artifacts,
        )
        tenant_reviews.append(review)
        tenant_label = review.get("tenant_db") or review.get("path") or "unknown"
        for check in review.get("checks") or []:
            rows.append(
                _row("tenant:%s:%s" % (tenant_label, check["name"]), check["status"], check["message"])
            )
        blockers.extend(review.get("blockers") or [])
        warnings.extend(review.get("warnings") or [])

    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "tenant_count": len(tenant_reviews),
        "strict": strict,
        "minimum_tenants": max(args.minimum_tenants, 0),
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "requirements": {
            "require_dns_provider": require_dns_provider,
            "require_admin_email": require_admin_email,
            "require_restore_drill": require_restore_drill,
            "require_monitoring": require_monitoring,
            "require_all_artifacts": require_all_artifacts,
        },
        "metadata": metadata,
        "tenants": tenant_reviews,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "tenant_count=%s" % len(tenant_reviews),
            "minimum_tenants=%s" % max(args.minimum_tenants, 0),
            "strict=%s" % strict,
            "require_dns_provider=%s" % require_dns_provider,
            "require_admin_email=%s" % require_admin_email,
            "require_restore_drill=%s" % require_restore_drill,
            "require_monitoring=%s" % require_monitoring,
            "require_all_artifacts=%s" % require_all_artifacts,
        ]
    )

    _write(output / "tenant-ops-evidence.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, tenant_reviews, decision, blockers, warnings))

    print("Tenant operations evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if ci_status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
