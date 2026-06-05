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


def _required_flag(value, default):
    if value in (None, ""):
        return default
    return _truthy(value)


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _status_row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _check_required(name, value, required, label):
    if value:
        return _status_row(name, "passed", "%s recorded: %s" % (label, value))
    if required:
        return _status_row(name, "failed", "%s is required." % label)
    return _status_row(name, "skipped", "%s is not required for this gate." % label)


def _check_readiness(readiness):
    decision = str(readiness.get("decision") or "").strip().lower()
    ci_status = str(readiness.get("ci_status") or "").strip().lower()
    if decision == "blocked" or ci_status == "fail":
        return _status_row("release-readiness", "failed", "Release readiness is blocked.")
    if decision == "warning" or ci_status == "pass_with_warnings":
        return _status_row("release-readiness", "warning", "Release readiness has warnings.")
    if decision == "ready" and ci_status in {"pass", ""}:
        return _status_row("release-readiness", "passed", "Release readiness is ready.")
    return _status_row(
        "release-readiness",
        "failed",
        "Release readiness decision is unknown: %s / %s" % (decision or "empty", ci_status or "empty"),
    )


def _decision(rows, readiness, fail_on_warning):
    blockers = []
    warnings = []
    for row in rows:
        if row["status"] == "failed":
            blockers.append("%s: %s" % (row["name"], row["message"]))
        elif row["status"] in {"warning", "skipped"}:
            warnings.append("%s: %s" % (row["name"], row["message"]))
    for warning in readiness.get("warnings") or []:
        warnings.append("release-readiness: %s" % warning)
    for blocker in readiness.get("blockers") or []:
        blockers.append("release-readiness: %s" % blocker)
    if warnings and fail_on_warning:
        blockers.extend("warning-policy: %s" % warning for warning in warnings)
        warnings = []
    if blockers:
        return "blocked", "fail", blockers, warnings
    if warnings:
        return "warning", "pass_with_warnings", blockers, warnings
    return "ready", "pass", blockers, warnings


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _checklist(items):
    return "\n".join("- [ ] %s" % item for item in items)


def _pre_cutover_checklist(args, readiness):
    return f"""
# Production Pre-Cutover Checklist

- Deployment run ID: {args.run_id}
- Target environment: {args.target_environment}
- Readiness package: {readiness.get("package_id") or ""}
- Git head: {readiness.get("git_head") or ""}

{_checklist([
    "Release-readiness decision reviewed by release owner.",
    "Sign-off package and evidence manifest reviewed.",
    "Database backup reference verified and restore drill evidence attached.",
    "Rollback reference verified and previous build/package can be restored.",
    "Monitoring, alerting, logs, and on-call routing verified.",
    "Tenant provisioning, subscription billing, POS, inventory, reporting, and display smoke tests assigned.",
    "PSP/FBR/hardware exceptions reviewed and approved or blocked.",
    "Customer communication and support escalation plan ready.",
])}
"""


def _rollback_checklist(args):
    return f"""
# Production Rollback Checklist

- Deployment run ID: {args.run_id}
- Target environment: {args.target_environment}
- Rollback reference: {args.rollback_ref or ""}
- Backup reference: {args.backup_ref or ""}

{_checklist([
    "Stop rollout and freeze additional module/schema changes.",
    "Notify release owner, support owner, DevOps owner, and business owner.",
    "Capture failing logs, readiness decision, and incident timestamp.",
    "Restore previous code/image reference or previous deployment package.",
    "Restore database backup only after data-loss risk review and owner approval.",
    "Run login, POS checkout, receipt, refund, inventory, reporting, and customer-display smoke tests.",
    "Confirm monitoring has returned to normal thresholds.",
    "Record incident summary, root-cause owner, and follow-up due date.",
])}
"""


def _summary(args, rows, decision, ci_status, blockers, warnings, readiness_file, output):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Production Deployment Gate

- Status: {decision}
- CI status: {ci_status}
- Run ID: {args.run_id}
- Target environment: {args.target_environment}
- Readiness file: {readiness_file}
- Output directory: {output}
- Generated: {_utc_now()}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Deployment decision: deployment-decision.json
- Status table: status.tsv
- Environment summary: env-summary.txt
- Pre-cutover checklist: pre-cutover-checklist.md
- Rollback checklist: rollback-checklist.md
"""


def main():
    parser = argparse.ArgumentParser(description="Generate Tijara production deployment gate evidence.")
    parser.add_argument(
        "readiness_file",
        nargs="?",
        default=os.environ.get("TIJARA_RELEASE_READINESS_FILE", ""),
        help="Path to release-readiness.json from the staging sign-off package.",
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_DEPLOYMENT_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_DEPLOYMENT_TARGET", "production"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_DEPLOYMENT_GATE_OUTPUT", ""))
    parser.add_argument("--backup-ref", default=os.environ.get("TIJARA_DEPLOYMENT_BACKUP_REF", ""))
    parser.add_argument("--rollback-ref", default=os.environ.get("TIJARA_DEPLOYMENT_ROLLBACK_REF", ""))
    parser.add_argument("--monitoring-ref", default=os.environ.get("TIJARA_DEPLOYMENT_MONITORING_REF", ""))
    parser.add_argument("--approver", default=os.environ.get("TIJARA_DEPLOYMENT_APPROVER", ""))
    parser.add_argument("--signoff-package", default=os.environ.get("TIJARA_DEPLOYMENT_SIGNOFF_PACKAGE", ""))
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_DEPLOYMENT_FAIL_ON_WARNING")),
    )
    args = parser.parse_args()

    if not args.readiness_file:
        print("Missing release-readiness.json path.", file=sys.stderr)
        return 2
    readiness_path = Path(args.readiness_file)
    if not readiness_path.is_absolute():
        readiness_path = ROOT_DIR / readiness_path
    if not readiness_path.is_file():
        print("Release readiness file not found: %s" % readiness_path, file=sys.stderr)
        return 2
    try:
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print("Could not read release readiness JSON: %s" % error, file=sys.stderr)
        return 2

    is_production = args.target_environment.strip().lower() == "production"
    require_backup = _required_flag(os.environ.get("TIJARA_DEPLOYMENT_REQUIRE_BACKUP"), is_production)
    require_rollback = _required_flag(os.environ.get("TIJARA_DEPLOYMENT_REQUIRE_ROLLBACK"), is_production)
    require_monitoring = _required_flag(os.environ.get("TIJARA_DEPLOYMENT_REQUIRE_MONITORING"), is_production)
    require_approver = _required_flag(os.environ.get("TIJARA_DEPLOYMENT_REQUIRE_APPROVER"), is_production)

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/deployment-gates" / args.run_id
    output.mkdir(parents=True, exist_ok=True)

    signoff_package = args.signoff_package or str(readiness_path.parent)
    rows = [
        _check_readiness(readiness),
        _check_required("backup-reference", args.backup_ref, require_backup, "Backup reference"),
        _check_required("rollback-reference", args.rollback_ref, require_rollback, "Rollback reference"),
        _check_required("monitoring-reference", args.monitoring_ref, require_monitoring, "Monitoring reference"),
        _check_required("release-approver", args.approver, require_approver, "Release approver"),
        _check_required("signoff-package", signoff_package, True, "Sign-off package"),
    ]
    decision, ci_status, blockers, warnings = _decision(rows, readiness, args.fail_on_warning)

    deployment_decision = {
        "run_id": args.run_id,
        "generated_at": _utc_now(),
        "target_environment": args.target_environment,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "readiness_file": str(readiness_path),
        "readiness_decision": readiness.get("decision"),
        "readiness_ci_status": readiness.get("ci_status"),
        "readiness_package_id": readiness.get("package_id"),
        "git_head": readiness.get("git_head"),
        "backup_ref": args.backup_ref,
        "rollback_ref": args.rollback_ref,
        "monitoring_ref": args.monitoring_ref,
        "approver": args.approver,
        "signoff_package": signoff_package,
        "checks": rows,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "readiness_file=%s" % readiness_path,
            "backup_ref=%s" % (args.backup_ref or "<missing>"),
            "rollback_ref=%s" % (args.rollback_ref or "<missing>"),
            "monitoring_ref=%s" % (args.monitoring_ref or "<missing>"),
            "approver=%s" % (args.approver or "<missing>"),
            "require_backup=%s" % int(require_backup),
            "require_rollback=%s" % int(require_rollback),
            "require_monitoring=%s" % int(require_monitoring),
            "require_approver=%s" % int(require_approver),
            "fail_on_warning=%s" % int(args.fail_on_warning),
        ]
    )

    _write(output / "deployment-decision.json", json.dumps(deployment_decision, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "pre-cutover-checklist.md", _pre_cutover_checklist(args, readiness))
    _write(output / "rollback-checklist.md", _rollback_checklist(args))
    _write(output / "summary.md", _summary(args, rows, decision, ci_status, blockers, warnings, readiness_path, output))

    print("Production deployment gate written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if decision == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
