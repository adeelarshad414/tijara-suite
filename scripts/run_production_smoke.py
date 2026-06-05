#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
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


def _load_json(path):
    if not path:
        return {}
    target = Path(path)
    if not target.is_absolute():
        target = ROOT_DIR / target
    if not target.is_file():
        raise RuntimeError("Decision file not found: %s" % target)
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not read decision JSON %s: %s" % (target, error)) from error


def _check_url(name, url, timeout):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "TijaraProductionSmoke/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.getcode() or 200
            body = response.read(2048)
        status = "passed" if 200 <= status_code < 400 else "failed"
        return {
            "name": name,
            "url": url,
            "status": status,
            "status_code": status_code,
            "message": "Fetched %s bytes." % len(body),
        }
    except urllib.error.HTTPError as error:
        status_code = error.code
        status = "passed" if 200 <= status_code < 400 else "failed"
        return {
            "name": name,
            "url": url,
            "status": status,
            "status_code": status_code,
            "message": "HTTP status %s." % status_code,
        }
    except Exception as error:
        return {
            "name": name,
            "url": url,
            "status": "failed",
            "status_code": 0,
            "message": str(error),
        }


def _endpoint_items(args):
    items = []
    if args.base_url:
        base = args.base_url.rstrip("/")
        items.extend(
            [
                ("web-root", base),
                ("web-login", "%s/web/login" % base),
            ]
        )
    for raw in args.url:
        if "=" in raw:
            name, url = raw.split("=", 1)
        else:
            name, url = "custom-%s" % (len(items) + 1), raw
        name = name.strip()
        url = url.strip()
        if name and url:
            items.append((name, url))
    return items


def _status_tsv(rows):
    lines = ["check\tstatus\tstatus_code\turl\tmessage"]
    lines.extend(
        "%s\t%s\t%s\t%s\t%s"
        % (row["name"], row["status"], row["status_code"], row["url"], row["message"])
        for row in rows
    )
    return "\n".join(lines)


def _summary(args, output, decision, ci_status, rows, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s (%s) - %s - %s"
        % (row["name"], row["status"], row["status_code"], row["url"], row["message"])
        for row in rows
    ) or "- No smoke endpoints configured."
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Production Smoke Evidence

- Status: {decision}
- CI status: {ci_status}
- Run ID: {args.run_id}
- Target environment: {args.target_environment}
- Output directory: {output}
- Generated: {_utc_now()}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Smoke decision: smoke-decision.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Run Tijara production post-deploy smoke checks.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_SMOKE_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_SMOKE_TARGET", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_SMOKE_OUTPUT", ""))
    parser.add_argument("--deployment-decision", default=os.environ.get("TIJARA_SMOKE_DEPLOYMENT_DECISION", ""))
    parser.add_argument("--rollback-decision", default=os.environ.get("TIJARA_SMOKE_ROLLBACK_DECISION", ""))
    parser.add_argument("--base-url", default=os.environ.get("TIJARA_SMOKE_BASE_URL", ""))
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Named smoke endpoint as name=url. Can be repeated.",
    )
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_SMOKE_TIMEOUT", "10")))
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_SMOKE_NON_STRICT")),
        help="Write warnings instead of failing when endpoints fail.",
    )
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/production-smoke" / args.run_id
    output.mkdir(parents=True, exist_ok=True)

    blockers = []
    warnings = []
    try:
        deployment_decision = _load_json(args.deployment_decision)
        rollback_decision = _load_json(args.rollback_decision)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    if deployment_decision and deployment_decision.get("decision") == "blocked":
        blockers.append("Deployment decision is blocked.")
    if rollback_decision and rollback_decision.get("decision") == "blocked":
        blockers.append("Rollback decision is blocked.")

    endpoints = _endpoint_items(args)
    if not endpoints:
        warnings.append("No smoke endpoints configured.")
    rows = [_check_url(name, url, args.timeout) for name, url in endpoints]
    for row in rows:
        if row["status"] == "failed":
            message = "%s failed: %s" % (row["name"], row["message"])
            if args.non_strict:
                warnings.append(message)
            else:
                blockers.append(message)

    if blockers:
        decision = "blocked"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    smoke_decision = {
        "run_id": args.run_id,
        "generated_at": _utc_now(),
        "target_environment": args.target_environment,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "deployment_decision": args.deployment_decision,
        "rollback_decision": args.rollback_decision,
        "checks": rows,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "base_url=%s" % (args.base_url or "<unset>"),
            "deployment_decision=%s" % (args.deployment_decision or "<unset>"),
            "rollback_decision=%s" % (args.rollback_decision or "<unset>"),
            "timeout=%s" % args.timeout,
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "smoke-decision.json", json.dumps(smoke_decision, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(args, output, decision, ci_status, rows, blockers, warnings))

    print("Production smoke evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
