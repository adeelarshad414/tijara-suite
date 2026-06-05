#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
DEFAULT_REQUIRED_ENV = [
    "ODOO_BASE_URL",
    "ODOO_DATABASE",
    "ODOO_USERNAME",
    "ODOO_PASSWORD",
    "TIJARA_POS_CONFIG_ID",
    "TIJARA_E2E_PRODUCT_ID",
    "TIJARA_E2E_PAYMENT_METHOD_ID",
    "TIJARA_E2E_REFUND_REASON_ID",
    "TIJARA_OFFLINE_QUEUE_ACTION_URL",
]
SOURCE_CONTRACTS = [
    {
        "name": "offline-capture-route",
        "path": "addons/tijara_pos_experience/controllers/display_routes.py",
        "tokens": ["/tijara/offline-pos/capture", "tijara_capture_from_browser"],
    },
    {
        "name": "offline-replay-route",
        "path": "addons/tijara_pos_experience/controllers/display_routes.py",
        "tokens": ["/tijara/offline-pos/replay", "tijara_replay_pending"],
    },
    {
        "name": "offline-status-route",
        "path": "addons/tijara_pos_experience/controllers/display_routes.py",
        "tokens": ["/tijara/offline-pos/status", "counts"],
    },
    {
        "name": "offline-queue-model",
        "path": "addons/tijara_pos_experience/models/offline_pos_queue.py",
        "tokens": [
            '_name = "tijara.offline.pos.queue"',
            "payload_hash",
            "action_replay_to_pos",
            "action_mark_duplicate",
            "action_merge_duplicate",
        ],
    },
    {
        "name": "cashier-offline-frontend",
        "path": "addons/tijara_pos_experience/static/src/app/offline_pos/offline_pos_queue.js",
        "tokens": [
            "localStorage",
            "tijaraReplayOfflineQueue",
            "/tijara/offline-pos/capture",
            "navigator.onLine",
        ],
    },
    {
        "name": "offline-review-views",
        "path": "addons/tijara_pos_experience/views/offline_pos_queue_views.xml",
        "tokens": [
            "Offline Conflict Review",
            "Offline Replay Audit",
            "Offline Pilot Dashboard",
        ],
    },
    {
        "name": "odoo-offline-transaction-tests",
        "path": "addons/tijara_pos_experience/tests/test_display_routes.py",
        "tokens": [
            "test_offline_pos_retry_replays_failed_valid_order",
            "test_offline_pos_capture_replays_to_paid_pos_order",
            "test_offline_pos_capture_deduplicates_replayed_source_order",
        ],
    },
    {
        "name": "browser-offline-enterprise-spec",
        "path": "tests/e2e/pos-enterprise-journey.spec.mjs",
        "tokens": [
            "capture and replay a paid browser order into POS",
            "/tijara/offline-pos/capture",
            'toBe("duplicate")',
            "/tijara/offline-pos/status",
        ],
    },
]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


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


def _read_json(path):
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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


def _redacted_env(name):
    value = os.environ.get(name, "")
    present = bool(value)
    secret_like = any(part in name.lower() for part in SECRET_KEY_PARTS)
    if not present:
        preview = "<missing>"
    elif secret_like:
        preview = "<set>"
    elif len(value) > 96:
        preview = value[:48] + "...<redacted>"
    else:
        preview = value
    return {"name": name, "present": present, "value": preview}


def _decision_status(payload):
    decision = str(payload.get("decision") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in {"failed", "blocked"} or ci_status == "fail":
        return "failed", decision, ci_status
    if decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        return "warning", decision, ci_status
    if decision or ci_status:
        return "passed", decision, ci_status
    return "unknown", decision, ci_status


def _playwright_stats(payload):
    stats = payload.get("stats") if isinstance(payload, dict) else {}
    counts = {
        "expected": int((stats or {}).get("expected") or 0),
        "unexpected": int((stats or {}).get("unexpected") or 0),
        "flaky": int((stats or {}).get("flaky") or 0),
        "skipped": int((stats or {}).get("skipped") or 0),
        "interrupted": int((stats or {}).get("interrupted") or 0),
    }
    return counts


def _playwright_tests(payload):
    tests = []

    def walk(node, current_file="", parent_titles=None):
        parent_titles = parent_titles or []
        if isinstance(node, list):
            for item in node:
                walk(item, current_file=current_file, parent_titles=parent_titles)
            return
        if not isinstance(node, dict):
            return
        file_name = node.get("file") or current_file
        title = node.get("title")
        suite_titles = parent_titles + ([title] if title and "tests" not in node else [])
        for test in node.get("tests") or []:
            test_title = " ".join(suite_titles + [str(test.get("title") or "")]).strip()
            statuses = [
                str(result.get("status") or "").lower()
                for result in test.get("results") or []
                if isinstance(result, dict)
            ]
            tests.append(
                {
                    "file": file_name,
                    "title": test_title,
                    "outcome": str(test.get("outcome") or "").lower(),
                    "statuses": statuses,
                }
            )
        for child in node.get("suites") or []:
            walk(child, current_file=file_name, parent_titles=suite_titles)

    if payload:
        walk(payload.get("suites") if isinstance(payload, dict) else payload)
    return tests


def _offline_test_runtime_result(playwright_payload):
    offline_tests = []
    for test in _playwright_tests(playwright_payload):
        haystack = "%s %s" % (test.get("file") or "", test.get("title") or "")
        if "pos-enterprise-journey.spec.mjs" in haystack or "offline" in haystack.lower():
            offline_tests.append(test)
    passed = []
    failed = []
    skipped = []
    for test in offline_tests:
        outcome = test.get("outcome")
        statuses = set(test.get("statuses") or [])
        if outcome in {"expected", "passed"} and not statuses.intersection({"failed", "timedout", "interrupted"}):
            passed.append(test)
        elif outcome == "skipped" or statuses == {"skipped"}:
            skipped.append(test)
        else:
            failed.append(test)
    return {
        "offline_tests": offline_tests,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def _orchestration_status(path):
    counts = {}
    failed = []
    if not path or not path.is_file():
        return counts, failed
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return counts, failed
    for index, line in enumerate(lines):
        if index == 0 and line.startswith("check\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, status = parts[0], parts[1]
        counts[status] = counts.get(status, 0) + 1
        if status in {"failed", "blocked", "error"}:
            failed.append(name)
    return counts, failed


def _summary(context, rows, blockers, warnings):
    status = "failed" if blockers else "warning" if warnings else "passed"
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    evidence_lines = "\n".join("- %s: %s" % (key, value or "<unset>") for key, value in context["evidence"].items())
    return f"""
# Protected Offline POS Replay Evidence

- Status: {status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Require E2E: {context["require_e2e"]}
- Require Playwright pass: {context["require_playwright_pass"]}
- Require duplicate proof: {context["require_duplicate_proof"]}

## Evidence Paths

{evidence_lines}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Offline replay manifest: protected-offline-replay-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context, env_state):
    lines = [
        "run_id=%s" % context["run_id"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "require_e2e=%s" % int(context["require_e2e"]),
        "require_playwright_pass=%s" % int(context["require_playwright_pass"]),
        "require_duplicate_proof=%s" % int(context["require_duplicate_proof"]),
        "fail_on_warning=%s" % int(context["fail_on_warning"]),
    ]
    for item in env_state:
        lines.append("%s=%s" % (item["name"], item["value"]))
    for key, value in context["evidence"].items():
        lines.append("%s=%s" % (key, value or "<unset>"))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export protected offline POS replay evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_OFFLINE_REPLAY_OUTPUT", ""))
    parser.add_argument("--e2e-evidence-dir", default=os.environ.get("TIJARA_OFFLINE_REPLAY_E2E_DIR", ""))
    parser.add_argument("--execution-evidence", default=os.environ.get("TIJARA_OFFLINE_REPLAY_EXECUTION_EVIDENCE", ""))
    parser.add_argument("--readiness-evidence", default=os.environ.get("TIJARA_OFFLINE_REPLAY_READINESS_EVIDENCE", ""))
    parser.add_argument("--playwright-json", default=os.environ.get("TIJARA_OFFLINE_REPLAY_PLAYWRIGHT_JSON", ""))
    parser.add_argument("--e2e-summary", default=os.environ.get("TIJARA_OFFLINE_REPLAY_E2E_SUMMARY", ""))
    parser.add_argument("--orchestration-status", default=os.environ.get("TIJARA_OFFLINE_REPLAY_ORCH_STATUS", ""))
    parser.add_argument("--required-env", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--require-e2e",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_REPLAY_REQUIRE_E2E")),
    )
    parser.add_argument(
        "--require-playwright-pass",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_REPLAY_REQUIRE_PLAYWRIGHT_PASS")),
    )
    parser.add_argument(
        "--require-duplicate-proof",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_REPLAY_REQUIRE_DUPLICATE_PROOF")),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_OFFLINE_REPLAY_FAIL_ON_WARNING")),
    )
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_OFFLINE_REPLAY_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-offline-replay" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    e2e_dir = _resolve(args.e2e_evidence_dir) if args.e2e_evidence_dir else ROOT_DIR / "deploy/runtime/e2e-evidence" / args.run_id
    execution_evidence = _resolve(args.execution_evidence) if args.execution_evidence else ROOT_DIR / "deploy/runtime/e2e-execution" / args.run_id / "e2e-execution-evidence.json"
    readiness_evidence = _resolve(args.readiness_evidence) if args.readiness_evidence else e2e_dir / "e2e-readiness.json"
    playwright_json = _resolve(args.playwright_json) if args.playwright_json else e2e_dir / "playwright-results.json"
    e2e_summary = _resolve(args.e2e_summary) if args.e2e_summary else e2e_dir / "summary.md"
    orchestration_status = _resolve(args.orchestration_status) if args.orchestration_status else ROOT_DIR / "deploy/runtime/protected-e2e" / args.run_id / "status.tsv"

    required_env = _dedupe(DEFAULT_REQUIRED_ENV + _csv_items(os.environ.get("TIJARA_OFFLINE_REPLAY_REQUIRED_ENV")) + args.required_env)
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

    env_state = [_redacted_env(name) for name in required_env]
    missing_env = [item["name"] for item in env_state if not item["present"]]
    if missing_env:
        message = "Offline replay E2E env missing: %s" % ", ".join(missing_env)
        if args.require_e2e:
            blockers.append(message)
            rows.append(_row("offline-replay-env", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("offline-replay-env", "warning", message))
    else:
        rows.append(_row("offline-replay-env", "passed", "Required offline replay E2E env is present."))

    readiness_payload = _read_json(readiness_evidence)
    if readiness_evidence.is_file():
        status, decision, ci_status = _decision_status(readiness_payload)
        rows.append(_row("e2e-readiness-evidence", status if status != "unknown" else "warning", "Readiness evidence is %s/%s." % (decision or "unknown", ci_status or "unknown"), str(readiness_evidence)))
        if status == "failed" and args.require_e2e:
            blockers.append("Readiness evidence is %s/%s." % (decision or "unknown", ci_status or "unknown"))
        elif status in {"failed", "warning", "unknown"}:
            warnings.append("Readiness evidence is %s/%s." % (decision or "unknown", ci_status or "unknown"))
    else:
        message = "E2E readiness evidence is missing."
        if args.require_e2e:
            blockers.append(message)
            rows.append(_row("e2e-readiness-evidence", "failed", message, str(readiness_evidence)))
        else:
            warnings.append(message)
            rows.append(_row("e2e-readiness-evidence", "warning", message, str(readiness_evidence)))

    execution_payload = _read_json(execution_evidence)
    if execution_evidence.is_file():
        status, decision, ci_status = _decision_status(execution_payload)
        rows.append(_row("e2e-execution-evidence", status if status != "unknown" else "warning", "Execution evidence is %s/%s." % (decision or "unknown", ci_status or "unknown"), str(execution_evidence)))
        if status == "failed" and args.require_e2e:
            blockers.append("Execution evidence is %s/%s." % (decision or "unknown", ci_status or "unknown"))
        elif status in {"failed", "warning", "unknown"}:
            warnings.append("Execution evidence is %s/%s." % (decision or "unknown", ci_status or "unknown"))
    else:
        message = "E2E execution evidence is missing."
        if args.require_e2e:
            blockers.append(message)
            rows.append(_row("e2e-execution-evidence", "failed", message, str(execution_evidence)))
        else:
            warnings.append(message)
            rows.append(_row("e2e-execution-evidence", "warning", message, str(execution_evidence)))

    if e2e_summary.is_file():
        rows.append(_row("e2e-summary", "passed", "Browser E2E summary is present.", str(e2e_summary)))
    else:
        message = "Browser E2E summary is missing."
        if args.require_e2e:
            blockers.append(message)
            rows.append(_row("e2e-summary", "failed", message, str(e2e_summary)))
        else:
            warnings.append(message)
            rows.append(_row("e2e-summary", "warning", message, str(e2e_summary)))

    playwright_payload = _read_json(playwright_json)
    playwright_review = {}
    if playwright_json.is_file():
        stats = _playwright_stats(playwright_payload)
        offline_runtime = _offline_test_runtime_result(playwright_payload)
        failed_count = stats["unexpected"] + stats["interrupted"]
        playwright_review = {
            "stats": stats,
            "offline_test_count": len(offline_runtime["offline_tests"]),
            "offline_passed_count": len(offline_runtime["passed"]),
            "offline_failed_count": len(offline_runtime["failed"]),
            "offline_skipped_count": len(offline_runtime["skipped"]),
        }
        if failed_count:
            message = "Playwright has %s unexpected/interrupted test(s)." % failed_count
            if args.require_playwright_pass or args.require_e2e:
                blockers.append(message)
                rows.append(_row("playwright-results", "failed", message, str(playwright_json)))
            else:
                warnings.append(message)
                rows.append(_row("playwright-results", "warning", message, str(playwright_json)))
        else:
            rows.append(_row("playwright-results", "passed", "Playwright JSON has no unexpected/interrupted tests.", str(playwright_json)))
        if offline_runtime["passed"]:
            rows.append(_row("offline-runtime-proof", "passed", "%s offline replay test(s) passed at runtime." % len(offline_runtime["passed"]), str(playwright_json)))
        else:
            message = "No passed offline replay browser test was found in Playwright JSON."
            if args.require_duplicate_proof or args.require_e2e:
                blockers.append(message)
                rows.append(_row("offline-runtime-proof", "failed", message, str(playwright_json)))
            else:
                warnings.append(message)
                rows.append(_row("offline-runtime-proof", "warning", message, str(playwright_json)))
    else:
        message = "Playwright JSON is missing."
        if args.require_playwright_pass or args.require_duplicate_proof or args.require_e2e:
            blockers.append(message)
            rows.append(_row("playwright-results", "failed", message, str(playwright_json)))
        else:
            warnings.append(message)
            rows.append(_row("playwright-results", "warning", message, str(playwright_json)))

    orch_counts, orch_failed = _orchestration_status(orchestration_status)
    if orchestration_status.is_file():
        if orch_failed:
            message = "Protected E2E orchestration failed step(s): %s" % ", ".join(orch_failed)
            if args.require_e2e:
                blockers.append(message)
                rows.append(_row("protected-e2e-orchestration", "failed", message, str(orchestration_status)))
            else:
                warnings.append(message)
                rows.append(_row("protected-e2e-orchestration", "warning", message, str(orchestration_status)))
        else:
            rows.append(_row("protected-e2e-orchestration", "passed", "Protected E2E orchestration has no failed rows.", str(orchestration_status)))
    else:
        message = "Protected E2E orchestration status is missing."
        if args.require_e2e:
            blockers.append(message)
            rows.append(_row("protected-e2e-orchestration", "failed", message, str(orchestration_status)))
        else:
            warnings.append(message)
            rows.append(_row("protected-e2e-orchestration", "warning", message, str(orchestration_status)))

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
        "require_e2e": bool(args.require_e2e),
        "require_playwright_pass": bool(args.require_playwright_pass),
        "require_duplicate_proof": bool(args.require_duplicate_proof),
        "fail_on_warning": bool(args.fail_on_warning),
        "evidence": {
            "e2e_evidence_dir": str(e2e_dir),
            "readiness_evidence": str(readiness_evidence),
            "execution_evidence": str(execution_evidence),
            "playwright_json": str(playwright_json),
            "e2e_summary": str(e2e_summary),
            "orchestration_status": str(orchestration_status),
        },
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
        "required_env": env_state,
        "source_reviews": source_reviews,
        "playwright_review": playwright_review,
        "orchestration_counts": orch_counts,
        "metadata": metadata,
    }
    _write(output / "protected-offline-replay-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, env_state))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Protected offline replay evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
