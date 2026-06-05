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


def _resolve(path):
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _load_json(path):
    target = _resolve(path)
    if not target:
        return {}, ""
    if not target.is_file():
        raise RuntimeError("Evidence JSON not found: %s" % target)
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not read evidence JSON %s: %s" % (target, error)) from error


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _decision_row(name, payload, source, good, warn):
    if not payload:
        return _row(name, "warning", "%s evidence is not attached." % name, source)
    decision = str(payload.get("decision") or payload.get("status") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in good and ci_status in {"", "pass"}:
        return _row(name, "passed", "%s decision is %s." % (name, decision), source)
    if decision in warn or ci_status == "pass_with_warnings":
        return _row(name, "warning", "%s decision is %s." % (name, decision or ci_status), source)
    return _row(name, "failed", "%s decision is %s/%s." % (name, decision or "empty", ci_status or "empty"), source)


def _endpoint_items(args):
    items = []
    if args.prometheus_url:
        items.append(("prometheus-ready", "%s/-/ready" % args.prometheus_url.rstrip("/")))
    if args.alertmanager_url:
        items.append(("alertmanager-ready", "%s/-/ready" % args.alertmanager_url.rstrip("/")))
    if args.grafana_url:
        items.append(("grafana-health", "%s/api/health" % args.grafana_url.rstrip("/")))
    for raw in args.url:
        if "=" in raw:
            name, url = raw.split("=", 1)
        else:
            name, url = "monitoring-%s" % (len(items) + 1), raw
        name = name.strip()
        url = url.strip()
        if name and url:
            items.append((name, url))
    return items


def _check_url(name, url, timeout):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "TijaraMonitoringEvidence/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.getcode() or 200
            body = response.read(1024)
        status = "passed" if 200 <= status_code < 400 else "failed"
        return {
            "name": name,
            "status": status,
            "status_code": status_code,
            "url": url,
            "message": "Fetched %s bytes." % len(body),
        }
    except urllib.error.HTTPError as error:
        status = "passed" if 200 <= error.code < 400 else "failed"
        return {
            "name": name,
            "status": status,
            "status_code": error.code,
            "url": url,
            "message": "HTTP status %s." % error.code,
        }
    except Exception as error:
        return {
            "name": name,
            "status": "failed",
            "status_code": 0,
            "url": url,
            "message": str(error),
        }


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    lines.extend(
        "%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source") or "")
        for row in rows
    )
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Monitoring Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Monitoring evidence manifest: monitoring-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara monitoring evidence for release sign-off.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_MONITORING_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_MONITORING_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_MONITORING_OUTPUT", ""))
    parser.add_argument("--smoke-decision", default=os.environ.get("TIJARA_MONITORING_SMOKE_DECISION", ""))
    parser.add_argument("--deployment-decision", default=os.environ.get("TIJARA_MONITORING_DEPLOYMENT_DECISION", ""))
    parser.add_argument("--rollback-decision", default=os.environ.get("TIJARA_MONITORING_ROLLBACK_DECISION", ""))
    parser.add_argument("--prometheus-url", default=os.environ.get("TIJARA_PROMETHEUS_URL", ""))
    parser.add_argument("--alertmanager-url", default=os.environ.get("TIJARA_ALERTMANAGER_URL", ""))
    parser.add_argument("--grafana-url", default=os.environ.get("TIJARA_GRAFANA_URL", ""))
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_MONITORING_TIMEOUT", "8")))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_MONITORING_NON_STRICT")))
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/monitoring-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    try:
        smoke_decision, smoke_path = _load_json(args.smoke_decision)
        deployment_decision, deployment_path = _load_json(args.deployment_decision)
        rollback_decision, rollback_path = _load_json(args.rollback_decision)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    rows = [
        _decision_row(
            "production-smoke",
            smoke_decision,
            smoke_path,
            {"passed"},
            {"warning"},
        ),
        _decision_row(
            "deployment-gate",
            deployment_decision,
            deployment_path,
            {"ready"},
            {"warning"},
        ),
        _decision_row(
            "rollback-evidence",
            rollback_decision,
            rollback_path,
            {"dry-run", "executed"},
            set(),
        ),
    ]

    endpoint_checks = [_check_url(name, url, args.timeout) for name, url in _endpoint_items(args)]
    if not endpoint_checks:
        rows.append(_row("monitoring-endpoints", "warning", "No monitoring endpoints configured."))
    for check in endpoint_checks:
        rows.append(
            _row(
                check["name"],
                check["status"],
                "%s (%s)." % (check["message"], check["status_code"]),
                check["url"],
            )
        )

    blockers = []
    warnings = []
    for row in rows:
        if row["status"] == "failed":
            if args.non_strict:
                warnings.append("%s: %s" % (row["name"], row["message"]))
            else:
                blockers.append("%s: %s" % (row["name"], row["message"]))
        elif row["status"] in {"warning", "skipped"}:
            warnings.append("%s: %s" % (row["name"], row["message"]))

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
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "evidence_refs": {
            "smoke_decision": smoke_path,
            "deployment_decision": deployment_path,
            "rollback_decision": rollback_path,
        },
        "checks": rows,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "smoke_decision=%s" % (smoke_path or "<unset>"),
            "deployment_decision=%s" % (deployment_path or "<unset>"),
            "rollback_decision=%s" % (rollback_path or "<unset>"),
            "prometheus_url=%s" % (args.prometheus_url or "<unset>"),
            "alertmanager_url=%s" % (args.alertmanager_url or "<unset>"),
            "grafana_url=%s" % (args.grafana_url or "<unset>"),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "monitoring-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Monitoring evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
