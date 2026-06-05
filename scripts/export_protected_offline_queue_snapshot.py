#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
STATE_NAMES = [
    "queued",
    "validated",
    "replayed",
    "conflict",
    "failed",
    "duplicate",
    "merged",
    "cancelled",
]
ATTENTION_NAMES = ["ok", "watch", "blocked", "resolved"]
QUEUE_FIELDS = [
    "name",
    "state",
    "source_app",
    "source_device_id",
    "pos_config_id",
    "pilot_attention_state",
    "pilot_failure_bucket",
    "pilot_queue_age_minutes",
    "replay_attempts",
    "replay_latency_minutes",
    "review_action",
    "amount_total",
]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


def _secret_like(name):
    normalized = str(name or "").lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _safe_env(name, value):
    if not value:
        return "<missing>"
    if _secret_like(name):
        return "<set>"
    return str(value)


def _dedupe(items):
    clean = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            clean.append(value)
    return clean


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s"
            % (row["name"], row["status"], row["message"], row.get("source") or "")
        )
    return "\n".join(lines)


def _redact_url(value):
    if not _present(value):
        return "<unset>"
    try:
        parsed = urllib.parse.urlsplit(str(value).strip())
    except ValueError:
        return "<invalid-url>"
    if not parsed.scheme or not parsed.netloc:
        return "<invalid-url>"
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = "%s:%s" % (netloc, parsed.port)
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))


def _join_url(base_url, path, query=None):
    parsed = urllib.parse.urlsplit(str(base_url).strip())
    normalized = (parsed.path or "").rstrip("/") + "/" + path.lstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, normalized or "/", query or "", ""))


def _int_or_zero(value):
    try:
        return max(int(float(value if value not in (None, "") else 0)), 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _count_mapping(value):
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_or_zero(raw) for key, raw in value.items()}


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
    return [key for key in metadata if _secret_like(key)]


def _json_request(opener, name, method, url, timeout, payload=None):
    body = None
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "tijara-offline-queue-snapshot/1",
    }
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 0) or response.getcode() or 0)
            raw = response.read(512 * 1024)
            try:
                parsed = json.loads(raw.decode("utf-8", errors="replace") or "{}")
            except json.JSONDecodeError:
                parsed = {}
            return {
                "name": name,
                "url": _redact_url(url),
                "method": method,
                "status_code": status_code,
                "ok": 200 <= status_code < 400,
                "payload": parsed if isinstance(parsed, dict) else {},
                "error": "",
            }
    except urllib.error.HTTPError as error:
        return {
            "name": name,
            "url": _redact_url(url),
            "method": method,
            "status_code": int(error.code),
            "ok": False,
            "payload": {},
            "error": str(error.reason or ""),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        return {
            "name": name,
            "url": _redact_url(url),
            "method": method,
            "status_code": 0,
            "ok": False,
            "payload": {},
            "error": str(reason),
        }


def _authenticate(opener, base_url, database, username, password, timeout):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"db": database, "login": username, "password": password},
        "id": int(time.time()),
    }
    result = _json_request(
        opener,
        "odoo-session-authenticate",
        "POST",
        _join_url(base_url, "/web/session/authenticate"),
        timeout,
        payload=payload,
    )
    body = result.get("payload") or {}
    result["authenticated"] = bool((body.get("result") or {}).get("uid"))
    result["uid_present"] = result["authenticated"]
    result["payload"] = {"result": {"uid_present": result["uid_present"]}}
    return result


def _domain(args):
    domain = []
    if args.source_device_id:
        domain.append(["source_device_id", "=", args.source_device_id])
    if args.pos_config_id:
        domain.append(["pos_config_id", "=", int(args.pos_config_id)])
    if args.outage_ref:
        domain.append(["pilot_outage_reference", "=", args.outage_ref])
    if args.state:
        domain.append(["state", "in", args.state])
    return domain


def _call_kw(opener, base_url, timeout, model, method, args=None, kwargs=None):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": model,
            "method": method,
            "args": args or [],
            "kwargs": kwargs or {},
        },
        "id": int(time.time()),
    }
    return _json_request(
        opener,
        "%s-%s" % (model, method),
        "POST",
        _join_url(base_url, "/web/dataset/call_kw/%s/%s" % (model, method)),
        timeout,
        payload=payload,
    )


def _status_route(opener, base_url, timeout, source_device_id):
    query = ""
    if source_device_id:
        query = urllib.parse.urlencode({"source_device_id": source_device_id})
    return _json_request(
        opener,
        "offline-pos-status",
        "GET",
        _join_url(base_url, "/tijara/offline-pos/status", query=query),
        timeout,
    )


def _relation_label(value):
    if isinstance(value, list) and len(value) >= 2:
        return value[1]
    if isinstance(value, tuple) and len(value) >= 2:
        return value[1]
    return ""


def _hash_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _queue_sample(row):
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "state": row.get("state") or "",
        "source_app": row.get("source_app") or "",
        "source_device_id_hash": _hash_text(row.get("source_device_id")),
        "pos_config": _relation_label(row.get("pos_config_id")),
        "pilot_attention_state": row.get("pilot_attention_state") or "",
        "pilot_failure_bucket": row.get("pilot_failure_bucket") or "",
        "pilot_queue_age_minutes": _float_or_none(row.get("pilot_queue_age_minutes")),
        "replay_attempts": _int_or_zero(row.get("replay_attempts")),
        "replay_latency_minutes": _float_or_none(row.get("replay_latency_minutes")),
        "review_action": row.get("review_action") or "",
        "amount_total": _float_or_none(row.get("amount_total")),
    }


def _metrics(status_payload, queue_rows):
    status_counts = _count_mapping(status_payload.get("counts") or status_payload.get("state_counts") or {})
    state_counts = {name: status_counts.get(name, 0) for name in STATE_NAMES}
    row_state_counts = {name: 0 for name in STATE_NAMES}
    attention_counts = {name: 0 for name in ATTENTION_NAMES}
    ages = []
    for row in queue_rows:
        state = str(row.get("state") or "")
        if state in state_counts:
            row_state_counts[state] += 1
        attention = str(row.get("pilot_attention_state") or "")
        if attention in attention_counts:
            attention_counts[attention] += 1
        age = _float_or_none(row.get("pilot_queue_age_minutes"))
        if age is not None:
            ages.append(max(age, 0.0))
    for name, count in row_state_counts.items():
        if count:
            state_counts[name] = max(state_counts.get(name, 0), count)
    failed_count = state_counts.get("failed", 0)
    conflict_count = state_counts.get("conflict", 0)
    replay_success_count = state_counts.get("replayed", 0)
    duplicate_count = state_counts.get("duplicate", 0)
    merged_count = state_counts.get("merged", 0)
    cancelled_count = state_counts.get("cancelled", 0)
    blocked_count = attention_counts.get("blocked") or failed_count + conflict_count
    watch_count = attention_counts.get("watch", 0)
    resolved_count = (
        attention_counts.get("resolved")
        or replay_success_count + duplicate_count + merged_count + cancelled_count
    )
    unresolved_count = (
        state_counts.get("queued", 0)
        + state_counts.get("validated", 0)
        + failed_count
        + conflict_count
    )
    return {
        "state_counts": state_counts,
        "attention_counts": attention_counts,
        "metrics": {
            "max_queue_age_minutes": max(ages) if ages else None,
            "replay_success_count": replay_success_count,
            "replay_failure_count": failed_count,
            "duplicate_count": duplicate_count,
            "conflict_count": conflict_count,
            "failed_count": failed_count,
            "blocked_count": blocked_count,
            "watch_count": watch_count,
            "resolved_count": resolved_count,
            "unresolved_count": unresolved_count,
            "queue_sample_count": len(queue_rows),
        },
    }


def _summary(context, rows, blockers, warnings):
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Offline Queue Snapshot

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Probe enabled: {context["probe_enabled"]}
- Base URL: {context["base_url"]}
- Source device hash: {context["source_device_id_hash"] or "unset"}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Offline queue snapshot: offline-queue-snapshot.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context, metadata):
    lines = [
        "run_id=%s" % context["run_id"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "probe_enabled=%s" % int(context["probe_enabled"]),
        "require_probe=%s" % int(context["require_probe"]),
        "strict=%s" % int(context["strict"]),
        "fail_on_warning=%s" % int(context["fail_on_warning"]),
        "base_url=%s" % context["base_url"],
        "database=%s" % context["database"],
        "username=%s" % context["username"],
        "password=%s" % context["password"],
        "source_device_id_hash=%s" % (context["source_device_id_hash"] or "<unset>"),
        "pos_config_id=%s" % (context["pos_config_id"] or "<unset>"),
        "outage_ref=%s" % (context["outage_ref"] or "<unset>"),
        "limit=%s" % context["limit"],
        "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
    ]
    return "\n".join(lines)


def _add_block_or_warning(rows, blockers, warnings, strict, name, message, source=""):
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message, source))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message, source))


def main():
    parser = argparse.ArgumentParser(description="Collect protected offline POS queue snapshot evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_OUTPUT", ""))
    parser.add_argument("--base-url", default=os.environ.get("ODOO_BASE_URL") or os.environ.get("TIJARA_BASE_URL", ""))
    parser.add_argument("--database", default=os.environ.get("ODOO_DATABASE", ""))
    parser.add_argument("--username", default=os.environ.get("ODOO_USERNAME") or os.environ.get("TIJARA_E2E_LOGIN", ""))
    parser.add_argument("--password", default=os.environ.get("ODOO_PASSWORD") or os.environ.get("TIJARA_E2E_PASSWORD", ""))
    parser.add_argument("--source-device-id", default=os.environ.get("TIJARA_OFFLINE_PILOT_SOURCE_DEVICE_ID", ""))
    parser.add_argument("--pos-config-id", default=os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_POS_CONFIG_ID", ""))
    parser.add_argument("--outage-ref", default=os.environ.get("TIJARA_OFFLINE_PILOT_OUTAGE_REF", ""))
    parser.add_argument("--state", action="append", default=[])
    parser.add_argument("--limit", type=int, default=int(os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_LIMIT", "250")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_TIMEOUT", "8")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--probe", action="store_true", default=_truthy(os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_PROBE", "0")))
    parser.add_argument("--require-probe", action="store_true", default=_truthy(os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_REQUIRE_PROBE", "0")))
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_FAIL_ON_WARNING", "0")))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_OFFLINE_QUEUE_SNAPSHOT_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-offline-pilot" / args.run_id / "queue-snapshot"
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

    auth_result = {}
    status_result = {}
    search_result = {}
    queue_rows = []
    status_payload = {}
    if not args.probe:
        message = "Offline queue snapshot probe is disabled."
        if args.require_probe and strict:
            blockers.append(message)
            rows.append(_row("snapshot-probe", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("snapshot-probe", "warning", message))
    else:
        rows.append(_row("snapshot-probe", "passed", "Offline queue snapshot probe is enabled."))
        missing = [
            name
            for name, value in [
                ("ODOO_BASE_URL", args.base_url),
                ("ODOO_DATABASE", args.database),
                ("ODOO_USERNAME", args.username),
                ("ODOO_PASSWORD", args.password),
            ]
            if not _present(value)
        ]
        if missing:
            _add_block_or_warning(
                rows,
                blockers,
                warnings,
                strict or args.require_probe,
                "snapshot-credentials",
                "Offline queue snapshot credentials missing: %s" % ", ".join(missing),
            )
        else:
            rows.append(_row("snapshot-credentials", "passed", "Odoo credentials are configured."))
            cookie_jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
            auth_result = _authenticate(opener, args.base_url, args.database, args.username, args.password, args.timeout)
            if auth_result.get("authenticated"):
                rows.append(_row("odoo-authenticate", "passed", "Odoo session authentication succeeded.", auth_result.get("url", "")))
                status_result = _status_route(opener, args.base_url, args.timeout, args.source_device_id)
                status_payload = status_result.get("payload") or {}
                if status_result.get("ok") and status_payload.get("status") in {"ok", None, ""}:
                    rows.append(_row("offline-status-route", "passed", "Offline status route returned JSON.", status_result.get("url", "")))
                else:
                    _add_block_or_warning(
                        rows,
                        blockers,
                        warnings,
                        strict or args.require_probe,
                        "offline-status-route",
                        "Offline status route failed: %s" % (status_result.get("error") or status_result.get("status_code")),
                        status_result.get("url", ""),
                    )
                domain = _domain(args)
                search_result = _call_kw(
                    opener,
                    args.base_url,
                    args.timeout,
                    "tijara.offline.pos.queue",
                    "search_read",
                    args=[domain],
                    kwargs={
                        "fields": QUEUE_FIELDS,
                        "limit": max(args.limit, 1),
                        "order": "queued_at desc, id desc",
                    },
                )
                search_payload = search_result.get("payload") or {}
                result_rows = search_payload.get("result")
                if search_result.get("ok") and isinstance(result_rows, list):
                    queue_rows = [row for row in result_rows if isinstance(row, dict)]
                    rows.append(
                        _row(
                            "offline-queue-search",
                            "passed",
                            "%s offline queue row(s) collected." % len(queue_rows),
                            search_result.get("url", ""),
                        )
                    )
                else:
                    _add_block_or_warning(
                        rows,
                        blockers,
                        warnings,
                        strict or args.require_probe,
                        "offline-queue-search",
                        "Offline queue search_read failed: %s" % (search_result.get("error") or search_result.get("status_code")),
                        search_result.get("url", ""),
                    )
            else:
                _add_block_or_warning(
                    rows,
                    blockers,
                    warnings,
                    strict or args.require_probe,
                    "odoo-authenticate",
                    "Odoo session authentication failed: %s" % (auth_result.get("error") or auth_result.get("status_code")),
                    auth_result.get("url", ""),
                )

    metric_payload = _metrics(status_payload, queue_rows)
    metrics = metric_payload["metrics"]
    if metrics.get("max_queue_age_minutes") is None and args.probe and not blockers:
        message = "No queue-age values were collected from offline queue rows."
        if strict:
            blockers.append(message)
            rows.append(_row("offline-queue-age", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("offline-queue-age", "warning", message))
    elif metrics.get("max_queue_age_minutes") is not None:
        rows.append(_row("offline-queue-age", "passed", "Maximum queue age was collected."))

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    if args.fail_on_warning and warnings:
        blockers.extend("Warning treated as blocker: %s" % warning for warning in warnings)
        blockers = _dedupe(blockers)
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
        "decision": decision,
        "probe_enabled": bool(args.probe),
        "require_probe": bool(args.require_probe),
        "strict": strict,
        "fail_on_warning": bool(args.fail_on_warning),
        "base_url": _redact_url(args.base_url),
        "database": _safe_env("ODOO_DATABASE", args.database),
        "username": _safe_env("ODOO_USERNAME", args.username),
        "password": _safe_env("ODOO_PASSWORD", args.password),
        "source_device_id_hash": _hash_text(args.source_device_id),
        "pos_config_id": args.pos_config_id,
        "outage_ref": args.outage_ref,
        "limit": args.limit,
        "domain": _domain(args),
    }
    snapshot = {
        "context": context,
        "status": "ok" if decision in {"passed", "warning"} else "failed",
        "decision": decision,
        "ci_status": ci_status,
        "state_counts": metric_payload["state_counts"],
        "attention_counts": metric_payload["attention_counts"],
        "metrics": metrics,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
        "auth_probe": auth_result,
        "status_probe": {
            key: value
            for key, value in status_result.items()
            if key not in {"payload"}
        },
        "search_probe": {
            key: value
            for key, value in search_result.items()
            if key not in {"payload"}
        },
        "queue_samples": [_queue_sample(row) for row in queue_rows[:50]],
        "metadata": metadata,
    }
    _write(output / "offline-queue-snapshot.json", json.dumps(snapshot, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, metadata))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Protected offline queue snapshot written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
