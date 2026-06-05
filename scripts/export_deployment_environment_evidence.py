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


def _present(value):
    return bool(str(value or "").strip())


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


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
# Deployment Environment Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Platform: {context["platform"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Deployment environment manifest: deployment-environment-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _add_required(rows, blockers, warnings, strict, name, value, label):
    if _present(value):
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is required for deployment environment protection." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _add_approver_check(rows, blockers, warnings, strict, approvers, minimum):
    count = len(approvers)
    if count >= minimum:
        rows.append(_row("required-approvers", "passed", "%s approver(s) recorded." % count))
        return
    message = "At least %s deployment approver(s) are required; %s recorded." % (minimum, count)
    if strict:
        blockers.append(message)
        rows.append(_row("required-approvers", "failed", message))
    else:
        warnings.append(message)
        rows.append(_row("required-approvers", "warning", message))


def main():
    parser = argparse.ArgumentParser(
        description="Export Tijara deployment environment protection evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_ENV_PROTECTION_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_ENV_PROTECTION_TARGET", "production"),
    )
    parser.add_argument("--platform", default=os.environ.get("TIJARA_ENV_PROTECTION_PLATFORM", "github-actions"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_ENV_PROTECTION_OUTPUT", ""))
    parser.add_argument(
        "--environment-name",
        default=os.environ.get("TIJARA_DEPLOYMENT_ENVIRONMENT_NAME", ""),
    )
    parser.add_argument("--branch-policy-ref", default=os.environ.get("TIJARA_BRANCH_POLICY_REF", ""))
    parser.add_argument("--approver", action="append", default=[])
    parser.add_argument("--approver-group-ref", default=os.environ.get("TIJARA_APPROVER_GROUP_REF", ""))
    parser.add_argument("--minimum-approvers", type=int, default=int(os.environ.get("TIJARA_MINIMUM_APPROVERS", "1")))
    parser.add_argument("--promotion-runbook-ref", default=os.environ.get("TIJARA_PROMOTION_RUNBOOK_REF", ""))
    parser.add_argument("--rollback-runbook-ref", default=os.environ.get("TIJARA_ROLLBACK_RUNBOOK_REF", ""))
    parser.add_argument("--deployment-gate-ref", default=os.environ.get("TIJARA_DEPLOYMENT_GATE_REF", ""))
    parser.add_argument("--incident-runbook-ref", default=os.environ.get("TIJARA_ENV_INCIDENT_RUNBOOK_REF", ""))
    parser.add_argument("--backup-policy-ref", default=os.environ.get("TIJARA_ENV_BACKUP_POLICY_REF", ""))
    parser.add_argument("--monitoring-ref", default=os.environ.get("TIJARA_ENV_MONITORING_REF", ""))
    parser.add_argument("--change-ticket-ref", default=os.environ.get("TIJARA_CHANGE_TICKET_REF", ""))
    parser.add_argument("--freeze-window-ref", default=os.environ.get("TIJARA_FREEZE_WINDOW_REF", ""))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_ENV_PROTECTION_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when environment protection evidence is missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    approvers = list(dict.fromkeys(args.approver + _csv_items(os.environ.get("TIJARA_DEPLOYMENT_APPROVERS"))))

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/deployment-environments" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

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

    _add_required(rows, blockers, warnings, strict, "environment-name", args.environment_name, "Environment name")
    _add_required(rows, blockers, warnings, strict, "branch-policy", args.branch_policy_ref, "Branch/deployment policy")
    _add_required(rows, blockers, warnings, strict, "approver-group", args.approver_group_ref, "Approver group")
    _add_approver_check(rows, blockers, warnings, strict, approvers, max(args.minimum_approvers, 1))
    _add_required(rows, blockers, warnings, strict, "promotion-runbook", args.promotion_runbook_ref, "Promotion runbook")
    _add_required(rows, blockers, warnings, strict, "rollback-runbook", args.rollback_runbook_ref, "Rollback runbook")
    _add_required(rows, blockers, warnings, strict, "deployment-gate", args.deployment_gate_ref, "Deployment gate reference")
    _add_required(rows, blockers, warnings, strict, "incident-runbook", args.incident_runbook_ref, "Incident runbook")
    _add_required(rows, blockers, warnings, strict, "backup-policy", args.backup_policy_ref, "Backup policy")
    _add_required(rows, blockers, warnings, strict, "monitoring", args.monitoring_ref, "Monitoring reference")
    _add_required(rows, blockers, warnings, strict, "change-ticket", args.change_ticket_ref, "Change ticket")
    _add_required(rows, blockers, warnings, strict, "freeze-window", args.freeze_window_ref, "Release/freeze window")

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
        "platform": args.platform,
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "environment": {
            "name": args.environment_name,
            "platform": args.platform,
            "branch_policy_ref_present": _present(args.branch_policy_ref),
            "approver_group_ref_present": _present(args.approver_group_ref),
            "minimum_approvers": max(args.minimum_approvers, 1),
            "approver_count": len(approvers),
            "promotion_runbook_ref_present": _present(args.promotion_runbook_ref),
            "rollback_runbook_ref_present": _present(args.rollback_runbook_ref),
            "deployment_gate_ref_present": _present(args.deployment_gate_ref),
            "incident_runbook_ref_present": _present(args.incident_runbook_ref),
            "backup_policy_ref_present": _present(args.backup_policy_ref),
            "monitoring_ref_present": _present(args.monitoring_ref),
            "change_ticket_ref_present": _present(args.change_ticket_ref),
            "freeze_window_ref_present": _present(args.freeze_window_ref),
        },
        "approvers": approvers,
        "metadata": metadata,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "platform=%s" % args.platform,
            "environment_name=%s" % (args.environment_name or "<unset>"),
            "branch_policy_ref_present=%s" % int(_present(args.branch_policy_ref)),
            "approver_count=%s" % len(approvers),
            "minimum_approvers=%s" % max(args.minimum_approvers, 1),
            "approver_group_ref_present=%s" % int(_present(args.approver_group_ref)),
            "promotion_runbook_ref_present=%s" % int(_present(args.promotion_runbook_ref)),
            "rollback_runbook_ref_present=%s" % int(_present(args.rollback_runbook_ref)),
            "deployment_gate_ref_present=%s" % int(_present(args.deployment_gate_ref)),
            "incident_runbook_ref_present=%s" % int(_present(args.incident_runbook_ref)),
            "backup_policy_ref_present=%s" % int(_present(args.backup_policy_ref)),
            "monitoring_ref_present=%s" % int(_present(args.monitoring_ref)),
            "change_ticket_ref_present=%s" % int(_present(args.change_ticket_ref)),
            "freeze_window_ref_present=%s" % int(_present(args.freeze_window_ref)),
            "non_strict=%s" % int(args.non_strict),
        ]
    )

    _write(output / "deployment-environment-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Deployment environment evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
