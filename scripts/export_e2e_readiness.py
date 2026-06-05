#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _secret_like(name):
    normalized = str(name or "").lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _safe_value(name, value):
    if not value:
        return "<missing>"
    if _secret_like(name):
        return "<set>"
    return str(value)


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    lines.extend(
        "%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source") or "")
        for row in rows
    )
    return "\n".join(lines)


def _summary(context, rows, blockers, warnings):
    status = "blocked" if blockers else "warning" if warnings else "passed"
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Authenticated POS E2E Readiness

- Status: {status}
- Run ID: {context["run_id"]}
- Scope: {context["scope"]}
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

- Readiness manifest: e2e-readiness.json
- Status table: status.tsv
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara staging browser E2E readiness evidence.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--started-at", default="")
    parser.add_argument("--required-var", action="append", default=[])
    parser.add_argument("--spec", action="append", default=[])
    parser.add_argument("--optional-flag", action="append", default=[])
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    variables = []
    for name in args.required_var:
        value = os.environ.get(name, "")
        present = bool(str(value).strip())
        variables.append(
            {
                "name": name,
                "present": present,
                "safe_value": _safe_value(name, value),
                "secret_like": _secret_like(name),
            }
        )
        if present:
            rows.append(_row("env:%s" % name, "passed", "%s is present." % name))
        else:
            message = "%s is required for %s E2E scope." % (name, args.scope)
            blockers.append(message)
            rows.append(_row("env:%s" % name, "failed", message))

    if not args.spec:
        warnings.append("No Playwright specs were selected.")
        rows.append(_row("selected-specs", "warning", "No Playwright specs were selected."))
    else:
        rows.append(_row("selected-specs", "passed", "%s Playwright spec(s) selected." % len(args.spec)))

    optional_flags = []
    for flag in args.optional_flag:
        value = os.environ.get(flag, "")
        optional_flags.append({"name": flag, "enabled": _truthy(value), "safe_value": _safe_value(flag, value)})

    if blockers:
        decision = "blocked"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "ready"
        ci_status = "pass"

    context = {
        "run_id": args.run_id,
        "scope": args.scope,
        "base_url": args.base_url,
        "started_at": args.started_at,
        "generated_at": _utc_now(),
        "output": str(output),
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "required_variables": variables,
        "optional_flags": optional_flags,
        "specs": args.spec,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    _write(output / "e2e-readiness.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "e2e-readiness-summary.md", _summary(context, rows, blockers, warnings))
    print("E2E readiness evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
