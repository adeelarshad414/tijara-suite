#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
SOURCE_CONTRACTS = [
    {
        "name": "offline-pilot-model-fields",
        "path": "addons/tijara_pos_experience/models/offline_pos_queue.py",
        "tokens": [
            "pilot_outage_reference",
            "pilot_recovery_owner_id",
            "pilot_attention_state",
            "pilot_queue_age_minutes",
            "action_retry_replay",
            "action_mark_duplicate",
            "action_merge_duplicate",
        ],
    },
    {
        "name": "offline-pilot-replay-contract",
        "path": "addons/tijara_pos_experience/models/offline_pos_queue.py",
        "tokens": [
            "tijara_capture_from_browser",
            "tijara_replay_pending",
            "source_device_id",
            "source_order_uid",
            "payload_hash",
        ],
    },
    {
        "name": "offline-pilot-review-views",
        "path": "addons/tijara_pos_experience/views/offline_pos_queue_views.xml",
        "tokens": [
            "Offline Conflict Review",
            "Offline Replay Audit",
            "Offline Pilot Dashboard",
            "Pilot Operations",
            "pilot_attention_state",
        ],
    },
    {
        "name": "offline-pilot-status-route",
        "path": "addons/tijara_pos_experience/controllers/display_routes.py",
        "tokens": [
            "/tijara/offline-pos/status",
            "source_device_id",
            "read_group",
            "counts",
        ],
    },
]
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


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _dedupe(items):
    clean = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            clean.append(value)
    return clean


def _resolve(path):
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _read_json(path):
    if not path or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


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


def _present(value):
    return bool(str(value or "").strip())


def _int_or_none(value):
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _float_or_none(value):
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _count_mapping(value):
    if not isinstance(value, dict):
        return {}
    counts = {}
    for key, raw in value.items():
        count = _int_or_none(raw)
        if count is not None:
            counts[str(key)] = max(count, 0)
    return counts


def _first_number(sources, keys, parser):
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in keys:
            if key in source:
                value = parser(source.get(key))
                if value is not None:
                    return value
    return None


def _status_from_payload(payload):
    decision = str(payload.get("decision") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in {"failed", "blocked"} or ci_status == "fail":
        return "failed"
    if decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        return "warning"
    if decision or ci_status:
        return "passed"
    return "unknown"


def _checks_by_name(payload):
    checks = payload.get("checks") if isinstance(payload, dict) else []
    result = {}
    if not isinstance(checks, list):
        return result
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "").strip()
        if name:
            result[name] = check
    return result


def _offline_replay_review(path):
    payload = _read_json(path)
    if not payload:
        return {
            "path": str(path),
            "present": False,
            "decision": "",
            "ci_status": "",
            "status": "missing",
            "runtime_proof": False,
            "duplicate_contract_proof": False,
            "blockers": [],
            "warnings": [],
        }
    checks = _checks_by_name(payload)
    source_reviews = payload.get("source_reviews") or []
    runtime_check = checks.get("offline-runtime-proof") or {}
    playwright_review = payload.get("playwright_review") or {}
    runtime_proof = str(runtime_check.get("status") or "").lower() == "passed" or (
        _int_or_none(playwright_review.get("offline_passed_count")) or 0
    ) > 0
    duplicate_contract_proof = False
    for review in source_reviews:
        if not isinstance(review, dict):
            continue
        name = str(review.get("name") or "")
        if name in {"browser-offline-enterprise-spec", "odoo-offline-transaction-tests"}:
            duplicate_contract_proof = duplicate_contract_proof or not review.get("missing_tokens")
    return {
        "path": _repo_relative(path),
        "present": True,
        "decision": payload.get("decision", ""),
        "ci_status": payload.get("ci_status", ""),
        "status": _status_from_payload(payload),
        "runtime_proof": bool(runtime_proof),
        "duplicate_contract_proof": bool(duplicate_contract_proof),
        "blockers": payload.get("blockers") or [],
        "warnings": payload.get("warnings") or [],
    }


def _snapshot_metrics(path):
    payload = _read_json(path)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    state_counts = _count_mapping(
        payload.get("state_counts")
        or payload.get("counts")
        or metrics.get("state_counts")
        or metrics.get("counts")
        or {}
    )
    attention_counts = _count_mapping(
        payload.get("attention_counts")
        or payload.get("pilot_attention_counts")
        or payload.get("pilot_attention")
        or metrics.get("attention_counts")
        or metrics.get("pilot_attention_counts")
        or {}
    )
    sources = [payload, metrics]
    duplicate_count = _first_number(sources, ["duplicate_count", "duplicates"], _int_or_none)
    conflict_count = _first_number(sources, ["conflict_count", "conflicts"], _int_or_none)
    failed_count = _first_number(sources, ["failed_count", "failures"], _int_or_none)
    replay_success_count = _first_number(
        sources,
        ["replay_success_count", "replayed_count", "replay_successes"],
        _int_or_none,
    )
    replay_failure_count = _first_number(
        sources,
        ["replay_failure_count", "replay_failed_count", "replay_failures"],
        _int_or_none,
    )
    blocked_count = _first_number(sources, ["blocked_count", "pilot_blocked_count"], _int_or_none)
    watch_count = _first_number(sources, ["watch_count", "pilot_watch_count"], _int_or_none)
    resolved_count = _first_number(sources, ["resolved_count", "pilot_resolved_count"], _int_or_none)
    max_age = _first_number(
        sources,
        ["max_queue_age_minutes", "pilot_max_queue_age_minutes", "max_age_minutes"],
        _float_or_none,
    )
    queued_count = _first_number(sources, ["queued_count"], _int_or_none)
    validated_count = _first_number(sources, ["validated_count"], _int_or_none)
    cancelled_count = _first_number(sources, ["cancelled_count"], _int_or_none)
    merged_count = _first_number(sources, ["merged_count"], _int_or_none)

    duplicate_count = duplicate_count if duplicate_count is not None else state_counts.get("duplicate", 0)
    merged_count = merged_count if merged_count is not None else state_counts.get("merged", 0)
    conflict_count = conflict_count if conflict_count is not None else state_counts.get("conflict", 0)
    failed_count = failed_count if failed_count is not None else state_counts.get("failed", 0)
    replay_success_count = (
        replay_success_count if replay_success_count is not None else state_counts.get("replayed", 0)
    )
    replay_failure_count = replay_failure_count if replay_failure_count is not None else failed_count
    queued_count = queued_count if queued_count is not None else state_counts.get("queued", 0)
    validated_count = validated_count if validated_count is not None else state_counts.get("validated", 0)
    cancelled_count = cancelled_count if cancelled_count is not None else state_counts.get("cancelled", 0)
    blocked_count = (
        blocked_count
        if blocked_count is not None
        else attention_counts.get("blocked", failed_count + conflict_count)
    )
    watch_count = watch_count if watch_count is not None else attention_counts.get("watch", 0)
    resolved_count = (
        resolved_count
        if resolved_count is not None
        else attention_counts.get(
            "resolved",
            replay_success_count + duplicate_count + merged_count + cancelled_count,
        )
    )
    unresolved_count = _first_number(sources, ["unresolved_count"], _int_or_none)
    if unresolved_count is None:
        unresolved_count = queued_count + validated_count + failed_count + conflict_count

    return {
        "snapshot_present": bool(payload),
        "snapshot_path": _repo_relative(path) if path else "",
        "state_counts": {name: state_counts.get(name, 0) for name in STATE_NAMES},
        "attention_counts": {name: attention_counts.get(name, 0) for name in ATTENTION_NAMES},
        "queued_count": queued_count,
        "validated_count": validated_count,
        "replayed_count": replay_success_count,
        "duplicate_count": duplicate_count,
        "merged_count": merged_count,
        "cancelled_count": cancelled_count,
        "conflict_count": conflict_count,
        "failed_count": failed_count,
        "replay_success_count": replay_success_count,
        "replay_failure_count": replay_failure_count,
        "blocked_count": blocked_count,
        "watch_count": watch_count,
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "max_queue_age_minutes": max_age,
    }


def _apply_metric_overrides(metrics, args):
    overrides = {
        "queued_count": _int_or_none(args.queued_count),
        "validated_count": _int_or_none(args.validated_count),
        "replayed_count": _int_or_none(args.replayed_count),
        "duplicate_count": _int_or_none(args.duplicate_count),
        "merged_count": _int_or_none(args.merged_count),
        "cancelled_count": _int_or_none(args.cancelled_count),
        "conflict_count": _int_or_none(args.conflict_count),
        "failed_count": _int_or_none(args.failed_count),
        "replay_success_count": _int_or_none(args.replay_success_count),
        "replay_failure_count": _int_or_none(args.replay_failure_count),
        "blocked_count": _int_or_none(args.blocked_count),
        "watch_count": _int_or_none(args.watch_count),
        "resolved_count": _int_or_none(args.resolved_count),
        "unresolved_count": _int_or_none(args.unresolved_count),
        "max_queue_age_minutes": _float_or_none(args.pilot_max_queue_age_minutes),
    }
    applied = {}
    for key, value in overrides.items():
        if value is not None:
            metrics[key] = value
            applied[key] = value
    metrics["state_counts"].update(
        {
            "queued": metrics["queued_count"],
            "validated": metrics["validated_count"],
            "replayed": metrics["replayed_count"],
            "conflict": metrics["conflict_count"],
            "failed": metrics["failed_count"],
            "duplicate": metrics["duplicate_count"],
            "merged": metrics["merged_count"],
            "cancelled": metrics["cancelled_count"],
        }
    )
    metrics["attention_counts"].update(
        {
            "blocked": metrics["blocked_count"],
            "watch": metrics["watch_count"],
            "resolved": metrics["resolved_count"],
        }
    )
    return applied


def _add_required(rows, blockers, warnings, strict, name, value, label):
    if _present(value):
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is required for offline POS pilot evidence." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _add_max_check(rows, blockers, warnings, strict, name, value, threshold, label):
    if value is None:
        message = "%s is missing." % label
        if strict:
            blockers.append(message)
            rows.append(_row(name, "failed", message))
        else:
            warnings.append(message)
            rows.append(_row(name, "warning", message))
        return
    if value <= threshold:
        rows.append(_row(name, "passed", "%s is within threshold: %s <= %s." % (label, value, threshold)))
        return
    message = "%s exceeds threshold: %s > %s." % (label, value, threshold)
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _add_min_check(rows, blockers, warnings, strict, name, value, threshold, label):
    if value is None:
        message = "%s is missing." % label
        if strict:
            blockers.append(message)
            rows.append(_row(name, "failed", message))
        else:
            warnings.append(message)
            rows.append(_row(name, "warning", message))
        return
    if value >= threshold:
        rows.append(_row(name, "passed", "%s meets minimum: %s >= %s." % (label, value, threshold)))
        return
    message = "%s is below minimum: %s < %s." % (label, value, threshold)
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _summary(context, rows, blockers, warnings):
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    pilot = context["pilot"]
    return f"""
# Protected Offline POS Pilot Evidence

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Outage reference: {pilot["outage_ref"] or "unset"}
- Recovery owner: {pilot["recovery_owner"] or "unset"}
- Store/register/device: {pilot["store_ref"] or "unset"} / {pilot["register_ref"] or "unset"} / {pilot["source_device_id"] or "unset"}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Offline POS pilot manifest: offline-pos-pilot-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context):
    pilot = context["pilot"]
    threshold = context["thresholds"]
    lines = [
        "run_id=%s" % context["run_id"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "strict=%s" % int(context["strict"]),
        "fail_on_warning=%s" % int(context["fail_on_warning"]),
        "require_offline_replay_pass=%s" % int(context["require_offline_replay_pass"]),
        "require_runtime_proof=%s" % int(context["require_runtime_proof"]),
        "require_duplicate_proof=%s" % int(context["require_duplicate_proof"]),
        "outage_ref=%s" % (pilot["outage_ref"] or "<unset>"),
        "recovery_owner=%s" % (pilot["recovery_owner"] or "<unset>"),
        "store_ref=%s" % (pilot["store_ref"] or "<unset>"),
        "register_ref=%s" % (pilot["register_ref"] or "<unset>"),
        "source_device_id=%s" % (pilot["source_device_id"] or "<unset>"),
        "offline_replay_evidence=%s" % context["evidence"]["offline_replay_evidence"],
        "queue_status_json=%s" % (context["evidence"]["queue_status_json"] or "<unset>"),
    ]
    for key, value in sorted(threshold.items()):
        lines.append("%s=%s" % (key, value))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export protected offline POS pilot evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_OFFLINE_PILOT_OUTPUT", ""))
    parser.add_argument("--offline-replay-evidence", default=os.environ.get("TIJARA_OFFLINE_PILOT_REPLAY_EVIDENCE", ""))
    parser.add_argument("--queue-status-json", default=os.environ.get("TIJARA_OFFLINE_PILOT_QUEUE_STATUS_JSON", ""))
    parser.add_argument("--outage-ref", default=os.environ.get("TIJARA_OFFLINE_PILOT_OUTAGE_REF", ""))
    parser.add_argument("--recovery-owner", default=os.environ.get("TIJARA_OFFLINE_PILOT_RECOVERY_OWNER", ""))
    parser.add_argument("--store-ref", default=os.environ.get("TIJARA_OFFLINE_PILOT_STORE_REF", ""))
    parser.add_argument("--register-ref", default=os.environ.get("TIJARA_OFFLINE_PILOT_REGISTER_REF", ""))
    parser.add_argument("--source-device-id", default=os.environ.get("TIJARA_OFFLINE_PILOT_SOURCE_DEVICE_ID", ""))
    parser.add_argument("--queued-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_QUEUED_COUNT", ""))
    parser.add_argument("--validated-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_VALIDATED_COUNT", ""))
    parser.add_argument("--replayed-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_REPLAYED_COUNT", ""))
    parser.add_argument("--duplicate-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_DUPLICATE_COUNT", ""))
    parser.add_argument("--merged-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_MERGED_COUNT", ""))
    parser.add_argument("--cancelled-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_CANCELLED_COUNT", ""))
    parser.add_argument("--conflict-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_CONFLICT_COUNT", ""))
    parser.add_argument("--failed-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_FAILED_COUNT", ""))
    parser.add_argument("--replay-success-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_REPLAY_SUCCESS_COUNT", ""))
    parser.add_argument("--replay-failure-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_REPLAY_FAILURE_COUNT", ""))
    parser.add_argument("--blocked-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_BLOCKED_COUNT", ""))
    parser.add_argument("--watch-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_WATCH_COUNT", ""))
    parser.add_argument("--resolved-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_RESOLVED_COUNT", ""))
    parser.add_argument("--unresolved-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_UNRESOLVED_COUNT", ""))
    parser.add_argument("--pilot-max-queue-age-minutes", default=os.environ.get("TIJARA_OFFLINE_PILOT_MAX_QUEUE_AGE_MINUTES", ""))
    parser.add_argument("--max-unresolved-blocked", default=os.environ.get("TIJARA_OFFLINE_PILOT_MAX_UNRESOLVED_BLOCKED", "0"))
    parser.add_argument("--max-unresolved-watch", default=os.environ.get("TIJARA_OFFLINE_PILOT_MAX_UNRESOLVED_WATCH", "0"))
    parser.add_argument("--max-conflict-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_MAX_CONFLICT_COUNT", "0"))
    parser.add_argument("--max-failed-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_MAX_FAILED_COUNT", "0"))
    parser.add_argument(
        "--max-queue-age-threshold-minutes",
        default=os.environ.get("TIJARA_OFFLINE_PILOT_MAX_QUEUE_AGE_THRESHOLD_MINUTES", "30"),
    )
    parser.add_argument("--minimum-replayed-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_MINIMUM_REPLAYED_COUNT", "1"))
    parser.add_argument("--minimum-duplicate-count", default=os.environ.get("TIJARA_OFFLINE_PILOT_MINIMUM_DUPLICATE_COUNT", "1"))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--require-offline-replay-pass",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_PILOT_REQUIRE_REPLAY_PASS")),
    )
    parser.add_argument(
        "--require-runtime-proof",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_PILOT_REQUIRE_RUNTIME_PROOF")),
    )
    parser.add_argument(
        "--require-duplicate-proof",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_PILOT_REQUIRE_DUPLICATE_PROOF")),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_PILOT_FAIL_ON_WARNING")),
    )
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_OFFLINE_PILOT_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-offline-pilot" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    offline_replay_evidence = (
        _resolve(args.offline_replay_evidence)
        if args.offline_replay_evidence
        else ROOT_DIR / "deploy/runtime/protected-offline-replay" / args.run_id / "protected-offline-replay-evidence.json"
    )
    queue_status_json = _resolve(args.queue_status_json) if args.queue_status_json else Path("")
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

    source_reviews = []
    for contract in SOURCE_CONTRACTS:
        path = ROOT_DIR / contract["path"]
        content = _read_text(path)
        missing = [token for token in contract["tokens"] if token not in content]
        if missing:
            message = "Missing source contract token(s): %s" % ", ".join(missing)
            blockers.append("%s: %s" % (contract["name"], message))
            rows.append(_row(contract["name"], "failed", message, contract["path"]))
        else:
            rows.append(_row(contract["name"], "passed", "Source contract is present.", contract["path"]))
        source_reviews.append(
            {
                "name": contract["name"],
                "path": contract["path"],
                "missing_tokens": missing,
                "token_count": len(contract["tokens"]),
            }
        )

    _add_required(rows, blockers, warnings, strict, "pilot-outage-ref", args.outage_ref, "Outage reference")
    _add_required(rows, blockers, warnings, strict, "pilot-recovery-owner", args.recovery_owner, "Recovery owner")
    _add_required(rows, blockers, warnings, strict, "pilot-store-ref", args.store_ref, "Pilot store reference")
    _add_required(rows, blockers, warnings, strict, "pilot-register-ref", args.register_ref, "Pilot register reference")
    _add_required(rows, blockers, warnings, strict, "pilot-source-device-id", args.source_device_id, "Pilot source device id")

    offline_replay = _offline_replay_review(offline_replay_evidence)
    if not offline_replay["present"]:
        message = "Protected offline replay evidence is missing."
        if strict or args.require_offline_replay_pass:
            blockers.append(message)
            rows.append(_row("offline-replay-evidence", "failed", message, str(offline_replay_evidence)))
        else:
            warnings.append(message)
            rows.append(_row("offline-replay-evidence", "warning", message, str(offline_replay_evidence)))
    else:
        status = offline_replay["status"]
        rows.append(
            _row(
                "offline-replay-evidence",
                status if status != "unknown" else "warning",
                "Offline replay evidence is %s/%s."
                % (offline_replay["decision"] or "unknown", offline_replay["ci_status"] or "unknown"),
                offline_replay["path"],
            )
        )
        if status == "failed" or (args.require_offline_replay_pass and status != "passed"):
            blockers.append(
                "Offline replay evidence is %s/%s."
                % (offline_replay["decision"] or "unknown", offline_replay["ci_status"] or "unknown")
            )
        elif status in {"warning", "unknown"}:
            warnings.append(
                "Offline replay evidence is %s/%s."
                % (offline_replay["decision"] or "unknown", offline_replay["ci_status"] or "unknown")
            )

    if offline_replay["runtime_proof"]:
        rows.append(_row("offline-runtime-proof", "passed", "Offline replay runtime proof is present.", offline_replay["path"]))
    else:
        message = "Offline replay runtime proof is missing."
        if strict or args.require_runtime_proof:
            blockers.append(message)
            rows.append(_row("offline-runtime-proof", "failed", message, offline_replay["path"]))
        else:
            warnings.append(message)
            rows.append(_row("offline-runtime-proof", "warning", message, offline_replay["path"]))

    metrics = _snapshot_metrics(queue_status_json) if args.queue_status_json else _snapshot_metrics(Path(""))
    metric_overrides = _apply_metric_overrides(metrics, args)
    if metrics["snapshot_present"]:
        rows.append(_row("queue-status-snapshot", "passed", "Offline queue status snapshot is present.", metrics["snapshot_path"]))
    elif metric_overrides:
        rows.append(_row("queue-status-snapshot", "passed", "Offline queue metrics supplied through CLI/env overrides."))
    else:
        message = "Offline queue status snapshot or CLI/env metrics are missing."
        if strict:
            blockers.append(message)
            rows.append(_row("queue-status-snapshot", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("queue-status-snapshot", "warning", message))

    thresholds = {
        "max_unresolved_blocked": _int_or_none(args.max_unresolved_blocked) or 0,
        "max_unresolved_watch": _int_or_none(args.max_unresolved_watch) or 0,
        "max_conflict_count": _int_or_none(args.max_conflict_count) or 0,
        "max_failed_count": _int_or_none(args.max_failed_count) or 0,
        "max_queue_age_threshold_minutes": _float_or_none(args.max_queue_age_threshold_minutes) or 30.0,
        "minimum_replayed_count": _int_or_none(args.minimum_replayed_count) or 1,
        "minimum_duplicate_count": _int_or_none(args.minimum_duplicate_count) or 1,
    }
    _add_min_check(
        rows,
        blockers,
        warnings,
        strict,
        "pilot-replay-success",
        metrics.get("replay_success_count"),
        thresholds["minimum_replayed_count"],
        "Replay success count",
    )
    _add_max_check(
        rows,
        blockers,
        warnings,
        strict,
        "pilot-blocked-threshold",
        metrics.get("blocked_count"),
        thresholds["max_unresolved_blocked"],
        "Blocked offline queue count",
    )
    _add_max_check(
        rows,
        blockers,
        warnings,
        strict,
        "pilot-watch-threshold",
        metrics.get("watch_count"),
        thresholds["max_unresolved_watch"],
        "Watch offline queue count",
    )
    _add_max_check(
        rows,
        blockers,
        warnings,
        strict,
        "pilot-conflict-threshold",
        metrics.get("conflict_count"),
        thresholds["max_conflict_count"],
        "Conflict offline queue count",
    )
    _add_max_check(
        rows,
        blockers,
        warnings,
        strict,
        "pilot-failed-threshold",
        metrics.get("failed_count"),
        thresholds["max_failed_count"],
        "Failed offline queue count",
    )
    _add_max_check(
        rows,
        blockers,
        warnings,
        strict,
        "pilot-queue-age-threshold",
        metrics.get("max_queue_age_minutes"),
        thresholds["max_queue_age_threshold_minutes"],
        "Maximum offline queue age in minutes",
    )

    if args.require_duplicate_proof:
        _add_min_check(
            rows,
            blockers,
            warnings,
            strict,
            "pilot-duplicate-proof",
            metrics.get("duplicate_count"),
            thresholds["minimum_duplicate_count"],
            "Duplicate replay proof count",
        )
    elif metrics.get("duplicate_count", 0) or offline_replay["duplicate_contract_proof"]:
        rows.append(_row("pilot-duplicate-proof", "passed", "Duplicate handling proof is present."))
    else:
        message = "Duplicate handling proof is not present in pilot metrics."
        warnings.append(message)
        rows.append(_row("pilot-duplicate-proof", "warning", message))

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
        "strict": strict,
        "fail_on_warning": bool(args.fail_on_warning),
        "require_offline_replay_pass": bool(args.require_offline_replay_pass),
        "require_runtime_proof": bool(args.require_runtime_proof),
        "require_duplicate_proof": bool(args.require_duplicate_proof),
        "pilot": {
            "outage_ref": args.outage_ref,
            "recovery_owner": args.recovery_owner,
            "store_ref": args.store_ref,
            "register_ref": args.register_ref,
            "source_device_id": args.source_device_id,
        },
        "thresholds": thresholds,
        "evidence": {
            "offline_replay_evidence": _repo_relative(offline_replay_evidence),
            "queue_status_json": _repo_relative(queue_status_json) if args.queue_status_json else "",
        },
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
        "metadata": metadata,
        "source_reviews": source_reviews,
        "offline_replay": offline_replay,
        "queue_metrics": metrics,
        "metric_overrides": metric_overrides,
    }
    _write(output / "offline-pos-pilot-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Protected offline POS pilot evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
