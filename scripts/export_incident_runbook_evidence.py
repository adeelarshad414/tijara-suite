#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _present(value):
    return bool(str(value or "").strip())


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


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
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


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
# Incident Runbook Evidence

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

- Incident runbook manifest: incident-runbook-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara incident runbook readiness evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_INCIDENT_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_INCIDENT_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_INCIDENT_OUTPUT", ""))
    parser.add_argument("--release-owner", default=os.environ.get("TIJARA_RELEASE_OWNER", ""))
    parser.add_argument("--devops-owner", default=os.environ.get("TIJARA_DEVOPS_OWNER", ""))
    parser.add_argument("--support-owner", default=os.environ.get("TIJARA_SUPPORT_OWNER", ""))
    parser.add_argument("--business-owner", default=os.environ.get("TIJARA_BUSINESS_OWNER", ""))
    parser.add_argument("--oncall-contact", default=os.environ.get("TIJARA_ONCALL_CONTACT", ""))
    parser.add_argument("--alert-route", default=os.environ.get("TIJARA_ALERT_ROUTE", ""))
    parser.add_argument("--runbook-url", default=os.environ.get("TIJARA_INCIDENT_RUNBOOK_URL", ""))
    parser.add_argument("--backup-reference", default=os.environ.get("TIJARA_INCIDENT_BACKUP_REF", ""))
    parser.add_argument("--restore-drill-reference", default=os.environ.get("TIJARA_INCIDENT_RESTORE_DRILL_REF", ""))
    parser.add_argument("--rollback-reference", default=os.environ.get("TIJARA_INCIDENT_ROLLBACK_REF", ""))
    parser.add_argument("--monitoring-reference", default=os.environ.get("TIJARA_INCIDENT_MONITORING_REF", ""))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_INCIDENT_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true", help="Fail when required incident evidence is missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/incident-runbooks" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    def add_required(name, value, label):
        if _present(value):
            rows.append(_row(name, "passed", "%s is recorded." % label))
            return
        message = "%s is required for production incident readiness." % label
        if args.non_strict:
            warnings.append(message)
            rows.append(_row(name, "warning", message))
        else:
            blockers.append(message)
            rows.append(_row(name, "failed", message))

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

    add_required("release-owner", args.release_owner, "Release owner")
    add_required("devops-owner", args.devops_owner, "DevOps owner")
    add_required("support-owner", args.support_owner, "Support owner")
    add_required("business-owner", args.business_owner, "Business owner")
    add_required("oncall-contact", args.oncall_contact, "On-call contact")
    add_required("alert-route", args.alert_route, "Alert route")
    add_required("runbook-url", args.runbook_url, "Incident runbook URL")
    add_required("backup-reference", args.backup_reference, "Backup reference")
    add_required("restore-drill-reference", args.restore_drill_reference, "Restore drill reference")
    add_required("rollback-reference", args.rollback_reference, "Rollback reference")
    add_required("monitoring-reference", args.monitoring_reference, "Monitoring evidence reference")

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
        "owners": {
            "release_owner_present": _present(args.release_owner),
            "devops_owner_present": _present(args.devops_owner),
            "support_owner_present": _present(args.support_owner),
            "business_owner_present": _present(args.business_owner),
            "oncall_contact_present": _present(args.oncall_contact),
        },
        "references": {
            "alert_route_present": _present(args.alert_route),
            "runbook_url_present": _present(args.runbook_url),
            "backup_reference_present": _present(args.backup_reference),
            "restore_drill_reference_present": _present(args.restore_drill_reference),
            "rollback_reference_present": _present(args.rollback_reference),
            "monitoring_reference_present": _present(args.monitoring_reference),
        },
        "metadata": metadata,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "release_owner_present=%s" % int(_present(args.release_owner)),
            "devops_owner_present=%s" % int(_present(args.devops_owner)),
            "support_owner_present=%s" % int(_present(args.support_owner)),
            "business_owner_present=%s" % int(_present(args.business_owner)),
            "oncall_contact_present=%s" % int(_present(args.oncall_contact)),
            "alert_route_present=%s" % int(_present(args.alert_route)),
            "runbook_url_present=%s" % int(_present(args.runbook_url)),
            "backup_reference_present=%s" % int(_present(args.backup_reference)),
            "restore_drill_reference_present=%s" % int(_present(args.restore_drill_reference)),
            "rollback_reference_present=%s" % int(_present(args.rollback_reference)),
            "monitoring_reference_present=%s" % int(_present(args.monitoring_reference)),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "incident-runbook-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Incident runbook evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
