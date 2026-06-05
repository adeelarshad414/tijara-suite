#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve(path):
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _load_summary(path):
    target = _resolve(path)
    if not target:
        return {}, ""
    if not target.is_file():
        raise RuntimeError("k6 summary JSON not found: %s" % target)
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not read k6 summary JSON %s: %s" % (target, error)) from error


def _metric(summary, metric_name, value_name, default=None):
    metric = (summary.get("metrics") or {}).get(metric_name) or {}
    values = metric.get("values") or {}
    return values.get(value_name, default)


def _float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Load Test Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Base URL: {context["base_url"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Load evidence manifest: load-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara load-test evidence for release sign-off.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_LOAD_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_LOAD_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_LOAD_OUTPUT", ""))
    parser.add_argument("--summary-json", default=os.environ.get("TIJARA_LOAD_SUMMARY_JSON", ""))
    parser.add_argument("--base-url", default=os.environ.get("TIJARA_BASE_URL", ""))
    parser.add_argument("--vus", default=os.environ.get("TIJARA_LOAD_VUS", ""))
    parser.add_argument("--duration", default=os.environ.get("TIJARA_LOAD_DURATION", ""))
    parser.add_argument("--p95-ms", default=os.environ.get("TIJARA_LOAD_P95_MS", ""))
    parser.add_argument("--fail-rate", default=os.environ.get("TIJARA_LOAD_FAIL_RATE", ""))
    parser.add_argument("--checks-rate", default=os.environ.get("TIJARA_LOAD_CHECKS_RATE", ""))
    parser.add_argument("--max-p95-ms", type=float, default=float(os.environ.get("TIJARA_LOAD_MAX_P95_MS", "1000")))
    parser.add_argument("--max-fail-rate", type=float, default=float(os.environ.get("TIJARA_LOAD_MAX_FAIL_RATE", "0.05")))
    parser.add_argument("--min-checks-rate", type=float, default=float(os.environ.get("TIJARA_LOAD_MIN_CHECKS_RATE", "0.95")))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_LOAD_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true", help="Fail when required load metrics are missing or out of threshold.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/load-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    try:
        summary_json, summary_path = _load_summary(args.summary_json)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    p95_ms = _float(args.p95_ms, None)
    fail_rate = _float(args.fail_rate, None)
    checks_rate = _float(args.checks_rate, None)
    if summary_json:
        p95_ms = _float(_metric(summary_json, "http_req_duration", "p(95)", p95_ms), p95_ms)
        fail_rate = _float(_metric(summary_json, "http_req_failed", "rate", fail_rate), fail_rate)
        checks_rate = _float(_metric(summary_json, "checks", "rate", checks_rate), checks_rate)

    rows = []
    blockers = []
    warnings = []

    def add_metric(name, value, comparator, threshold, label):
        if value is None:
            message = "%s metric is missing." % label
            if args.non_strict:
                warnings.append(message)
                rows.append(_row(name, "warning", message))
            else:
                blockers.append(message)
                rows.append(_row(name, "failed", message))
            return
        passed = comparator(value, threshold)
        status = "passed" if passed else "failed"
        message = "%s is %.4f; threshold is %.4f." % (label, value, threshold)
        rows.append(_row(name, status, message))
        if not passed:
            if args.non_strict:
                warnings.append(message)
                rows[-1]["status"] = "warning"
            else:
                blockers.append(message)

    if args.base_url:
        rows.append(_row("base-url", "passed", "Base URL is recorded."))
    else:
        message = "Base URL is not recorded."
        warnings.append(message)
        rows.append(_row("base-url", "warning", message))

    if summary_json:
        rows.append(_row("summary-json", "passed", "k6 summary JSON is attached."))
    else:
        message = "k6 summary JSON is not attached; using supplied metrics only."
        warnings.append(message)
        rows.append(_row("summary-json", "warning", message))

    add_metric("p95-duration", p95_ms, lambda value, threshold: value <= threshold, args.max_p95_ms, "HTTP p95 duration ms")
    add_metric("failure-rate", fail_rate, lambda value, threshold: value <= threshold, args.max_fail_rate, "HTTP failure rate")
    add_metric("checks-rate", checks_rate, lambda value, threshold: value >= threshold, args.min_checks_rate, "k6 checks pass rate")

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
        "base_url": args.base_url or "<unset>",
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "summary_json": summary_path,
        "load_profile": {
            "vus": args.vus or "",
            "duration": args.duration or "",
        },
        "metrics": {
            "p95_ms": p95_ms,
            "fail_rate": fail_rate,
            "checks_rate": checks_rate,
            "max_p95_ms": args.max_p95_ms,
            "max_fail_rate": args.max_fail_rate,
            "min_checks_rate": args.min_checks_rate,
        },
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "base_url=%s" % (args.base_url or "<unset>"),
            "summary_json=%s" % (summary_path or "<unset>"),
            "vus=%s" % (args.vus or "<unset>"),
            "duration=%s" % (args.duration or "<unset>"),
            "max_p95_ms=%s" % args.max_p95_ms,
            "max_fail_rate=%s" % args.max_fail_rate,
            "min_checks_rate=%s" % args.min_checks_rate,
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "load-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Load evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
