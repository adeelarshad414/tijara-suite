#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


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


def _resolve_path(raw_path):
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _safe_relative(path):
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _hash_file(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _row(name, status, tenant_db, url, status_code, message):
    return {
        "name": name,
        "status": status,
        "tenant_db": tenant_db,
        "url": url,
        "status_code": status_code,
        "message": message,
    }


def _status_tsv(rows):
    lines = ["check\tstatus\ttenant_db\turl\tstatus_code\tmessage"]
    lines.extend(
        "%s\t%s\t%s\t%s\t%s\t%s"
        % (
            row["name"],
            row["status"],
            row["tenant_db"],
            row["url"],
            row["status_code"],
            row["message"],
        )
        for row in rows
    )
    return "\n".join(lines)


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


def _mapping_items(items):
    mapped = {}
    for raw in items or []:
        if "=" not in raw:
            raise ValueError("Mapping must use key=value format: %s" % raw)
        key, value = raw.split("=", 1)
        mapped[key.strip()] = value.strip()
    return mapped


def _tenant_artifact_paths(args):
    values = list(args.tenant_artifact or [])
    values.extend(_csv_items(os.environ.get("TIJARA_TENANT_SMOKE_ARTIFACTS")))
    values.extend(_csv_items(os.environ.get("TIJARA_TENANT_OPS_ARTIFACTS")))
    deduped = []
    seen = set()
    for raw in values:
        if raw and raw not in seen:
            seen.add(raw)
            deduped.append(raw)
    return [_resolve_path(raw) for raw in deduped]


def _load_manifest(path):
    tenant_dir = path if path.is_dir() else path.parent
    manifest_path = path if path.is_file() else tenant_dir / "ops-manifest.json"
    payload = _read_json(manifest_path)
    return tenant_dir, manifest_path, payload


def _join_url(base_url, route):
    if route.startswith("http://") or route.startswith("https://"):
        return route
    if route.startswith("/"):
        return base_url.rstrip("/") + route
    return base_url.rstrip("/") + "/" + route


def _route_items(items):
    routes = []
    for raw in items or []:
        if "=" in raw:
            name, value = raw.split("=", 1)
        else:
            name, value = "custom-%s" % (len(routes) + 1), raw
        name = name.strip()
        value = value.strip()
        if name and value:
            routes.append((name, value))
    return routes


def _tenant_route_items(items):
    routes = {}
    for raw in items or []:
        if ":" not in raw or "=" not in raw:
            raise ValueError("Tenant route must use tenant_db:name=url-or-path format: %s" % raw)
        tenant_db, rest = raw.split(":", 1)
        name, value = rest.split("=", 1)
        tenant_db = tenant_db.strip()
        name = name.strip()
        value = value.strip()
        if tenant_db and name and value:
            routes.setdefault(tenant_db, []).append((name, value))
    return routes


def _check_url(name, tenant_db, url, timeout, headers, allowed_statuses):
    try:
        request = urllib.request.Request(
            url,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.getcode() or 200
            body = response.read(2048)
        passed = status_code in allowed_statuses or 200 <= status_code < 400
        return _row(
            name,
            "passed" if passed else "failed",
            tenant_db,
            url,
            status_code,
            "Fetched %s bytes." % len(body),
        )
    except urllib.error.HTTPError as error:
        status_code = error.code
        passed = status_code in allowed_statuses or 200 <= status_code < 400
        return _row(
            name,
            "passed" if passed else "failed",
            tenant_db,
            url,
            status_code,
            "HTTP status %s." % status_code,
        )
    except Exception as error:
        return _row(name, "failed", tenant_db, url, 0, str(error))


def _tenant_base_url(tenant, dns, ingress, base_overrides):
    tenant_db = tenant.get("database", "")
    domain = tenant.get("domain") or dns.get("hostname") or ingress.get("host") or ""
    if tenant_db in base_overrides:
        return base_overrides[tenant_db].rstrip("/")
    if domain in base_overrides:
        return base_overrides[domain].rstrip("/")
    if not domain:
        return ""
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    return "https://%s" % domain.rstrip("/")


def _tenant_checks(tenant_db, base_url, manifest, tenant_dir, global_routes, tenant_routes, include_monitoring):
    routes = [
        ("web-root", base_url),
        ("web-login", _join_url(base_url, "/web/login")),
    ]
    monitoring = manifest.get("monitoring") or {}
    blackbox_url = monitoring.get("blackbox_url", "")
    if include_monitoring and _present(blackbox_url):
        if blackbox_url.startswith("http://") or blackbox_url.startswith("https://"):
            url = blackbox_url
        else:
            url = _join_url(base_url, blackbox_url)
        if url not in {item[1] for item in routes}:
            routes.append(("monitoring-blackbox", url))
    for name, value in global_routes:
        routes.append((name, _join_url(base_url, value)))
    for name, value in tenant_routes.get(tenant_db, []):
        routes.append((name, _join_url(base_url, value)))

    deduped = []
    seen = set()
    for name, url in routes:
        key = (name, url)
        if url and key not in seen:
            seen.add(key)
            deduped.append((name, url))
    return deduped


def _tenant_review(
    path,
    args,
    strict,
    base_overrides,
    global_routes,
    tenant_routes,
    global_headers,
    allowed_statuses,
):
    tenant_dir, manifest_path, manifest = _load_manifest(path)
    tenant = manifest.get("tenant") or {}
    dns = manifest.get("dns") or {}
    ingress = manifest.get("ingress") or {}
    tenant_db = tenant.get("database", "")
    domain = tenant.get("domain") or dns.get("hostname") or ingress.get("host") or ""
    base_url = _tenant_base_url(tenant, dns, ingress, base_overrides)
    rows = []
    blockers = []
    warnings = []

    if not manifest:
        message = "Tenant operations manifest is missing or unreadable: %s" % manifest_path
        blockers.append(message)
        return {
            "path": _safe_relative(tenant_dir),
            "manifest_path": _safe_relative(manifest_path),
            "tenant_db": tenant_db,
            "domain": domain,
            "base_url": base_url,
            "decision": "failed",
            "ci_status": "fail",
            "checks": rows,
            "blockers": blockers,
            "warnings": warnings,
        }

    smoke_checks = manifest.get("smoke_checks") or []
    if args.require_smoke_checklist and not smoke_checks:
        message = "Tenant manifest has no smoke checklist."
        if strict:
            blockers.append(message)
        else:
            warnings.append(message)

    if not base_url:
        message = "Tenant %s has no domain/base URL for smoke execution." % (tenant_db or _safe_relative(tenant_dir))
        blockers.append(message)
        return {
            "path": _safe_relative(tenant_dir),
            "manifest_path": _safe_relative(manifest_path),
            "manifest_sha256": _hash_file(manifest_path),
            "tenant_db": tenant_db,
            "domain": domain,
            "base_url": base_url,
            "decision": "failed",
            "ci_status": "fail",
            "check_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "smoke_check_count": len(smoke_checks),
            "checks": rows,
            "blockers": blockers,
            "warnings": warnings,
        }

    headers = {
        "User-Agent": "TijaraTenantSmoke/1.0",
    }
    headers.update(global_headers)
    if args.dbfilter_header and tenant_db:
        headers.setdefault("X-Odoo-dbfilter", "^%s$" % tenant_db)

    routes = _tenant_checks(
        tenant_db,
        base_url,
        manifest,
        tenant_dir,
        global_routes,
        tenant_routes,
        args.include_monitoring_route,
    )
    if len(routes) < max(args.minimum_routes_per_tenant, 0):
        message = "Tenant %s has %s smoke route(s); minimum is %s." % (
            tenant_db or _safe_relative(tenant_dir),
            len(routes),
            max(args.minimum_routes_per_tenant, 0),
        )
        if strict:
            blockers.append(message)
        else:
            warnings.append(message)

    for name, url in routes:
        rows.append(_check_url(name, tenant_db, url, args.timeout, headers, allowed_statuses))

    for row in rows:
        if row["status"] == "failed":
            message = "Tenant %s route %s failed: %s" % (
                tenant_db or _safe_relative(tenant_dir),
                row["name"],
                row["message"],
            )
            if strict:
                blockers.append(message)
            else:
                warnings.append(message)

    passed_count = sum(1 for row in rows if row["status"] == "passed")
    failed_count = sum(1 for row in rows if row["status"] == "failed")
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
        "manifest_sha256": _hash_file(manifest_path),
        "tenant_db": tenant_db,
        "domain": domain,
        "base_url": base_url,
        "decision": decision,
        "ci_status": ci_status,
        "check_count": len(rows),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "smoke_check_count": len(smoke_checks),
        "dbfilter_header_used": bool(args.dbfilter_header and tenant_db),
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }


def _summary(context, tenant_reviews, decision, ci_status, blockers, warnings):
    tenant_lines = []
    for review in tenant_reviews:
        tenant_lines.append(
            "- %s (%s): %s, routes passed/failed=%s/%s, checklist=%s, base=%s"
            % (
                review.get("tenant_db") or "unknown",
                review.get("domain") or "no-domain",
                review.get("decision") or "unknown",
                review.get("passed_count", 0),
                review.get("failed_count", 0),
                review.get("smoke_check_count", 0),
                review.get("base_url") or "unset",
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Tenant Smoke Evidence

- Status: {decision}
- CI status: {ci_status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Tenant artifacts reviewed: {context["tenant_count"]}
- Output directory: {context["output"]}

## Tenant Reviews

{chr(10).join(tenant_lines) or "- No tenant smoke checks were executed."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Tenant smoke evidence: tenant-smoke-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Run tenant-aware Tijara smoke checks.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_TENANT_SMOKE_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_TENANT_SMOKE_ENVIRONMENT", "production"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_TENANT_SMOKE_OUTPUT", ""))
    parser.add_argument("--tenant-artifact", action="append", default=[])
    parser.add_argument("--tenant-base-url", action="append", default=_csv_items(os.environ.get("TIJARA_TENANT_SMOKE_BASE_URLS")))
    parser.add_argument("--route", action="append", default=[])
    parser.add_argument("--tenant-route", action="append", default=[])
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--allow-status", action="append", default=[])
    parser.add_argument(
        "--minimum-tenants",
        type=int,
        default=int(os.environ.get("TIJARA_TENANT_SMOKE_MINIMUM_TENANTS", "1")),
    )
    parser.add_argument(
        "--minimum-routes-per-tenant",
        type=int,
        default=int(os.environ.get("TIJARA_TENANT_SMOKE_MINIMUM_ROUTES", "2")),
    )
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_TENANT_SMOKE_TIMEOUT", "10")))
    parser.add_argument("--no-dbfilter-header", action="store_false", dest="dbfilter_header")
    parser.set_defaults(dbfilter_header=not _truthy(os.environ.get("TIJARA_TENANT_SMOKE_NO_DBFILTER_HEADER")))
    parser.add_argument("--require-smoke-checklist", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_SMOKE_REQUIRE_CHECKLIST", "1")))
    parser.add_argument("--include-monitoring-route", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_SMOKE_INCLUDE_MONITORING", "1")))
    parser.add_argument("--skip-monitoring-route", action="store_false", dest="include_monitoring_route")
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_TENANT_SMOKE_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when tenant smoke evidence is incomplete or endpoints fail.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/tenant-smoke" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    try:
        metadata = _metadata_items(args.metadata)
        base_overrides = _mapping_items(args.tenant_base_url)
        headers = _mapping_items(args.header)
        global_routes = _route_items(args.route)
        tenant_routes = _tenant_route_items(args.tenant_route)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    flagged = _secret_like_keys(metadata) + _secret_like_keys(headers)
    if flagged:
        print("Secret-like metadata/header keys are not allowed: %s" % ", ".join(flagged), file=sys.stderr)
        return 2

    allowed_statuses = set()
    for raw in args.allow_status:
        for item in _csv_items(raw):
            try:
                allowed_statuses.add(int(item))
            except ValueError:
                print("Invalid HTTP status: %s" % item, file=sys.stderr)
                return 2

    tenant_paths = _tenant_artifact_paths(args)
    if len(tenant_paths) < max(args.minimum_tenants, 0):
        message = "At least %s tenant artifact(s) are required; %s provided." % (
            max(args.minimum_tenants, 0),
            len(tenant_paths),
        )
        if strict:
            blockers.append(message)
        else:
            warnings.append(message)

    tenant_reviews = []
    for tenant_path in tenant_paths:
        review = _tenant_review(
            tenant_path,
            args,
            strict,
            base_overrides,
            global_routes,
            tenant_routes,
            headers,
            allowed_statuses,
        )
        tenant_reviews.append(review)
        rows.extend(review.get("checks") or [])
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
        "strict": strict,
        "tenant_count": len(tenant_reviews),
        "minimum_tenants": max(args.minimum_tenants, 0),
        "minimum_routes_per_tenant": max(args.minimum_routes_per_tenant, 0),
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "metadata": metadata,
        "requirements": {
            "require_smoke_checklist": bool(args.require_smoke_checklist),
            "include_monitoring_route": bool(args.include_monitoring_route),
            "dbfilter_header": bool(args.dbfilter_header),
            "allowed_statuses": sorted(allowed_statuses),
        },
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
            "minimum_routes_per_tenant=%s" % max(args.minimum_routes_per_tenant, 0),
            "strict=%s" % strict,
            "timeout=%s" % args.timeout,
            "dbfilter_header=%s" % bool(args.dbfilter_header),
            "include_monitoring_route=%s" % bool(args.include_monitoring_route),
            "route_count=%s" % len(global_routes),
            "tenant_route_count=%s" % sum(len(value) for value in tenant_routes.values()),
            "base_override_count=%s" % len(base_overrides),
        ]
    )

    _write(output / "tenant-smoke-evidence.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, tenant_reviews, decision, ci_status, blockers, warnings))

    print("Tenant smoke evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
