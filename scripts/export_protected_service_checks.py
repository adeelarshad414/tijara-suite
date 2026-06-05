#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret", "auth_value"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


def _is_secret_key(key):
    normalized = str(key or "").lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)


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
    return [key for key in metadata if _is_secret_key(key)]


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _redact_url(value):
    if not _present(value):
        return "<unset>"
    try:
        parsed = urlsplit(str(value).strip())
    except ValueError:
        return "<invalid-url>"
    if not parsed.scheme or not parsed.netloc:
        return "<invalid-url>"
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = "%s:%s" % (netloc, parsed.port)
    return urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))


def _join_url(base_url, path):
    parsed = urlsplit(str(base_url).strip())
    normalized = (parsed.path or "").rstrip("/") + "/" + path.lstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, normalized or "/", "", ""))


def _headers(header, value_env):
    value = os.environ.get(value_env, "") if value_env else ""
    if header and value:
        return {header: value}, {"header": header, "value_env": value_env, "value_present": True}
    return {}, {"header": header or "", "value_env": value_env or "", "value_present": False}


def _request(name, method, url, timeout, headers=None, body=None):
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"User-Agent": "tijara-service-checks/1", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 0) or response.getcode() or 0)
            raw = response.read(128 * 1024)
            return {
                "name": name,
                "url": _redact_url(url),
                "method": method,
                "status_code": status_code,
                "reachable": 200 <= status_code < 400,
                "body_preview": raw[:200].decode("utf-8", errors="replace"),
                "error": "",
            }
    except urllib.error.HTTPError as error:
        return {
            "name": name,
            "url": _redact_url(url),
            "method": method,
            "status_code": int(error.code),
            "reachable": 200 <= int(error.code) < 400,
            "body_preview": "",
            "error": str(error.reason or ""),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        return {
            "name": name,
            "url": _redact_url(url),
            "method": method,
            "status_code": 0,
            "reachable": False,
            "body_preview": "",
            "error": str(reason),
        }


def _odoo_auth_probe(base_url, database, username, password, timeout):
    url = _join_url(base_url, "/web/session/authenticate")
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"db": database, "login": username, "password": password},
        "id": int(time.time()),
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    result = _request(
        "odoo-session-authenticate",
        "POST",
        url,
        timeout,
        headers={"Content-Type": "application/json"},
        body=body,
    )
    if result["reachable"]:
        try:
            parsed = json.loads(result["body_preview"] or "{}")
        except json.JSONDecodeError:
            parsed = {}
        result["authenticated"] = bool((parsed.get("result") or {}).get("uid"))
        result["body_preview"] = "<jsonrpc-redacted>"
    else:
        result["authenticated"] = False
    return result


def _bridge_signature(secret, timestamp, body):
    message = timestamp.encode("utf-8") + b"." + body
    return "sha256=%s" % hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _bridge_test_probe(base_url, secret, timeout):
    url = _join_url(base_url, "/v1/test")
    body = json.dumps({"source": "protected-service-check", "dry_run": True}, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Tijara-Timestamp": timestamp,
        "X-Tijara-Signature": _bridge_signature(secret, timestamp, body),
    }
    result = _request("hardware-bridge-signed-test", "POST", url, timeout, headers=headers, body=body)
    result["signed"] = bool(secret)
    return result


def _service_entries(timeout):
    return [
        {
            "name": "odoo-login",
            "base_url": os.environ.get("ODOO_BASE_URL") or os.environ.get("TIJARA_BASE_URL", ""),
            "path": "/web/login",
            "kind": "http",
        },
        {
            "name": "odoo-session-authenticate",
            "base_url": os.environ.get("ODOO_BASE_URL") or os.environ.get("TIJARA_BASE_URL", ""),
            "kind": "odoo-auth",
            "database_env": "ODOO_DATABASE",
            "username_env": "TIJARA_E2E_LOGIN",
            "password_env": "TIJARA_E2E_PASSWORD",
        },
        {
            "name": "hardware-bridge-health",
            "base_url": os.environ.get("TIJARA_HARDWARE_BRIDGE_URL", ""),
            "path": "/health",
            "kind": "http",
            "auth_header": os.environ.get("TIJARA_SERVICE_BRIDGE_AUTH_HEADER") or os.environ.get("TIJARA_PREFLIGHT_BRIDGE_AUTH_HEADER", "X-Tijara-Bridge-Secret"),
            "auth_value_env": os.environ.get("TIJARA_SERVICE_BRIDGE_AUTH_VALUE_ENV") or os.environ.get("TIJARA_PREFLIGHT_BRIDGE_AUTH_VALUE_ENV", "TIJARA_BRIDGE_SHARED_SECRET"),
        },
        {
            "name": "hardware-bridge-signed-test",
            "base_url": os.environ.get("TIJARA_HARDWARE_BRIDGE_URL", ""),
            "kind": "bridge-signed-test",
            "secret_env": "TIJARA_BRIDGE_SHARED_SECRET",
        },
        {
            "name": "prometheus-ready",
            "base_url": os.environ.get("TIJARA_PROMETHEUS_URL", ""),
            "path": "/-/ready",
            "kind": "http",
            "auth_header": os.environ.get("TIJARA_SERVICE_PROMETHEUS_AUTH_HEADER") or os.environ.get("TIJARA_PREFLIGHT_PROMETHEUS_AUTH_HEADER", ""),
            "auth_value_env": os.environ.get("TIJARA_SERVICE_PROMETHEUS_AUTH_VALUE_ENV") or os.environ.get("TIJARA_PREFLIGHT_PROMETHEUS_AUTH_VALUE_ENV", ""),
        },
        {
            "name": "alertmanager-ready",
            "base_url": os.environ.get("TIJARA_ALERTMANAGER_URL", ""),
            "path": "/-/ready",
            "kind": "http",
            "auth_header": os.environ.get("TIJARA_SERVICE_ALERTMANAGER_AUTH_HEADER") or os.environ.get("TIJARA_PREFLIGHT_ALERTMANAGER_AUTH_HEADER", ""),
            "auth_value_env": os.environ.get("TIJARA_SERVICE_ALERTMANAGER_AUTH_VALUE_ENV") or os.environ.get("TIJARA_PREFLIGHT_ALERTMANAGER_AUTH_VALUE_ENV", ""),
        },
        {
            "name": "grafana-health",
            "base_url": os.environ.get("TIJARA_GRAFANA_URL", ""),
            "path": "/api/health",
            "kind": "http",
            "auth_header": os.environ.get("TIJARA_SERVICE_GRAFANA_AUTH_HEADER") or os.environ.get("TIJARA_PREFLIGHT_GRAFANA_AUTH_HEADER", ""),
            "auth_value_env": os.environ.get("TIJARA_SERVICE_GRAFANA_AUTH_VALUE_ENV") or os.environ.get("TIJARA_PREFLIGHT_GRAFANA_AUTH_VALUE_ENV", ""),
        },
    ]


def _run_probe(entry, timeout):
    if not _present(entry.get("base_url")):
        return {"name": entry["name"], "configured": False, "reachable": False, "error": "Base URL is not configured."}
    if entry["kind"] == "odoo-auth":
        database = os.environ.get(entry["database_env"], "")
        username = os.environ.get(entry["username_env"], "")
        password = os.environ.get(entry["password_env"], "")
        configured = all(_present(value) for value in [database, username, password])
        if not configured:
            return {
                "name": entry["name"],
                "configured": False,
                "reachable": False,
                "database_present": _present(database),
                "username_present": _present(username),
                "password_present": _present(password),
                "error": "Odoo auth credentials are not fully configured.",
            }
        result = _odoo_auth_probe(entry["base_url"], database, username, password, timeout)
        result["configured"] = True
        return result
    if entry["kind"] == "bridge-signed-test":
        secret = os.environ.get(entry["secret_env"], "")
        if not secret:
            return {"name": entry["name"], "configured": False, "reachable": False, "secret_present": False, "error": "Bridge shared secret is not configured."}
        result = _bridge_test_probe(entry["base_url"], secret, timeout)
        result["configured"] = True
        result["secret_present"] = True
        return result
    headers, auth = _headers(entry.get("auth_header", ""), entry.get("auth_value_env", ""))
    result = _request(entry["name"], "GET", _join_url(entry["base_url"], entry["path"]), timeout, headers=headers)
    result["configured"] = True
    result["auth"] = auth
    return result


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Service Checks

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Probe enabled: {context["probe_enabled"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Service checks manifest: protected-service-checks.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export protected authenticated service check evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_SERVICE_CHECKS_OUTPUT", ""))
    parser.add_argument("--probe", action="store_true", default=_truthy(os.environ.get("TIJARA_SERVICE_CHECKS_PROBE", "0")))
    parser.add_argument("--require-probes", action="store_true", default=_truthy(os.environ.get("TIJARA_SERVICE_CHECKS_REQUIRE_PROBES", "0")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_SERVICE_CHECKS_TIMEOUT", "8")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_SERVICE_CHECKS_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-service-checks" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    try:
        metadata = _metadata_items(args.metadata)
        rows.append(_row("metadata-format", "passed", "%s metadata item(s) parsed." % len(metadata)))
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append(_row("metadata-format", "failed", str(error)))

    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append(_row("metadata-secret-safety", "failed", message))
    else:
        rows.append(_row("metadata-secret-safety", "passed", "No secret-like metadata keys found."))

    services = _service_entries(args.timeout)
    probes = []
    if not args.probe:
        message = "Authenticated service probes are disabled."
        if args.require_probes and strict:
            blockers.append(message)
            rows.append(_row("service-probes", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("service-probes", "warning", message))
    else:
        rows.append(_row("service-probes", "passed", "Authenticated service probes are enabled."))
        for entry in services:
            result = _run_probe(entry, args.timeout)
            probes.append(result)
            if not result.get("configured"):
                message = "%s is not fully configured." % entry["name"]
                if args.require_probes and strict:
                    blockers.append(message)
                    rows.append(_row(entry["name"], "failed", message))
                else:
                    warnings.append(message)
                    rows.append(_row(entry["name"], "warning", message))
                continue
            authenticated = result.get("authenticated")
            if result.get("reachable") and authenticated is not False:
                rows.append(_row(entry["name"], "passed", "Probe succeeded."))
            else:
                message = "%s probe failed: %s" % (entry["name"], result.get("error") or "not reachable/authenticated")
                if strict:
                    blockers.append(message)
                    rows.append(_row(entry["name"], "failed", message))
                else:
                    warnings.append(message)
                    rows.append(_row(entry["name"], "warning", message))

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
        "probe_enabled": bool(args.probe),
        "require_probes": bool(args.require_probes),
        "timeout": args.timeout,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "services": [
            {
                "name": entry["name"],
                "base_url": _redact_url(entry.get("base_url", "")),
                "kind": entry["kind"],
                "auth_header": entry.get("auth_header", ""),
                "auth_value_env": entry.get("auth_value_env", ""),
            }
            for entry in services
        ],
        "probes": probes,
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "probe_enabled=%s" % int(args.probe),
            "require_probes=%s" % int(args.require_probes),
            "probe_count=%s" % len(probes),
            "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-service-checks.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Protected service checks written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
