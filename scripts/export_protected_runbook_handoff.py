#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
DEFAULT_REVIEW_ORDER = [
    "protected-runbook-handoff",
    "protected-first-run",
    "protected-runner-preflight",
    "protected-runner-bootstrap-verification",
    "protected-service-checks",
    "protected-provider-readiness",
    "protected-payment-lifecycle",
    "protected-offline-replay",
    "protected-offline-pilot",
    "protected-artifact-summary",
    "protected-run-decision",
    "protected-evidence-retention",
    "protected-sidecar-verification",
    "protected-evidence-replay",
    "protected-release-evidence-index",
    "protected-release-closure",
    "protected-closure-result-verification",
    "release-evidence",
    "protected-e2e",
    "e2e-execution",
    "ops-tool-evidence",
    "operations-release-bundle",
    "monitoring-evidence",
    "incident-runbook-evidence",
    "secret-runtime-evidence",
    "deployment-environment-evidence",
    "tenant-ops-evidence",
    "certification-evidence",
    "release-retention-evidence",
    "secret-manager-evidence",
    "production-ops-readiness",
    "signoff-packages",
]
DEFAULT_GO_NO_GO = [
    "First-run checklist has no failed rows.",
    "Protected runner preflight has no failed rows.",
    "Protected service, provider, payment lifecycle, offline replay, and offline pilot evidence have no failed rows.",
    "Release-candidate gate passed or approved exception is recorded.",
    "Protected Browser E2E evidence is passed or approved exception is recorded.",
    "Operations tool evidence has no unapproved critical/high blockers.",
    "Monitoring, incident, deployment environment, tenant operations, and runtime secret evidence are attached.",
    "Certification evidence is present for every required PSP/FBR/hardware group.",
    "Release retention and secret-manager evidence passed.",
    "Production operations readiness passed or approved exception is recorded with expiry and audit reference.",
    "Release-readiness JSON is ready/pass.",
    "Rollback owner and incident channel are staffed during the release window.",
]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


def _parse_expiry(value):
    text = str(value or "").strip()
    if not text:
        return None, "Expiry is missing."
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        if "T" in normalized or "+" in normalized:
            parsed = dt.datetime.fromisoformat(normalized)
        else:
            parsed_date = dt.date.fromisoformat(normalized)
            parsed = dt.datetime.combine(parsed_date, dt.time.max, tzinfo=dt.timezone.utc)
    except ValueError:
        return None, "Expiry must use YYYY-MM-DD or ISO-8601 datetime."
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc), ""


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


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _add_required(rows, blockers, warnings, strict, name, value, label):
    if _present(value):
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is required for protected runbook handoff." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _warning_exception(args):
    enabled = bool(args.allow_warning_exception)
    expires_at, expiry_error = _parse_expiry(args.warning_exception_expires_at) if enabled else (None, "")
    issues = []
    if enabled:
        if not _present(args.warning_exception_ref):
            issues.append("Warning exception reference is required.")
        if not _present(args.warning_exception_approved_by):
            issues.append("Warning exception approver is required.")
        if not _present(args.warning_exception_reason):
            issues.append("Warning exception reason is required.")
        if not _present(args.warning_exception_audit_ref):
            issues.append("Warning exception audit reference is required.")
        if expiry_error:
            issues.append(expiry_error)
        elif expires_at and expires_at < dt.datetime.now(dt.timezone.utc):
            issues.append("Warning exception is expired.")
    status = "disabled"
    if enabled and issues:
        status = "invalid"
    elif enabled:
        status = "ready"
    return {
        "enabled": enabled,
        "status": status,
        "reference": args.warning_exception_ref,
        "approved_by": args.warning_exception_approved_by,
        "reason": args.warning_exception_reason,
        "expires_at": args.warning_exception_expires_at,
        "expires_at_utc": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ") if expires_at else "",
        "audit_ref": args.warning_exception_audit_ref,
        "issues": issues,
    }


def _add_warning_exception_checks(rows, blockers, warnings, strict, exception):
    if not exception["enabled"]:
        rows.append(
            _row(
                "warning-exception-runbook",
                "passed",
                "Production-ops warning exception is disabled for this handoff.",
            )
        )
        return
    if exception["issues"]:
        message = "Production-ops warning exception issue(s): %s" % "; ".join(exception["issues"])
        if strict:
            blockers.append(message)
            rows.append(_row("warning-exception-runbook", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("warning-exception-runbook", "warning", message))
        return
    rows.append(
        _row(
            "warning-exception-runbook",
            "passed",
            "Production-ops warning exception has reference, approver, reason, future expiry, and audit reference.",
        )
    )


def _workflow_checks(workflow_file):
    checks = []
    path = Path(workflow_file)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if not path.is_file():
        return path, ["Workflow file is missing: %s" % path]
    content = path.read_text(encoding="utf-8", errors="replace")
    for token in ["protected-release-evidence", "protected_release", "target_environment"]:
        if token not in content:
            checks.append("Workflow file does not contain %s." % token)
    return path, checks


def _artifact_review_rows(review_order):
    files = {
        "protected-runbook-handoff": "summary.md, operator-runbook.md, warning-exception-runbook.md",
        "protected-first-run": "protected-first-run-checklist.json, status.tsv",
        "protected-runner-preflight": "protected-runner-preflight.json, status.tsv",
        "protected-runner-bootstrap-verification": "protected-runner-bootstrap-verification.json, tool-correlation.tsv",
        "protected-artifact-summary": "protected-artifact-summary.json, summary.md",
        "protected-run-decision": "protected-run-decision.json, summary.md",
        "protected-evidence-retention": "protected-evidence-retention-manifest.json, summary.md",
        "protected-sidecar-verification": "protected-sidecar-verification.json, summary.md",
        "protected-evidence-replay": "protected-evidence-replay-report.json, audit-replay.md",
        "protected-release-evidence-index": "protected-release-evidence-index.json, operator-index.md",
        "protected-release-closure": "protected-release-closure-decision.json, promotion-checklist.md",
        "protected-closure-result-verification": "protected-closure-result-verification.json, closure-result.md",
        "release-evidence": "release-candidate.json, status.tsv, summary.md",
        "protected-e2e": "summary.md, status.tsv, e2e execution artifacts",
        "protected-offline-pilot": "offline-pos-pilot-evidence.json, status.tsv",
        "e2e-execution": "e2e-execution-evidence.json, status.tsv",
        "ops-tool-evidence": "ops-tool-evidence.json, status.tsv",
        "operations-release-bundle": "operations-release-bundle.json, status.tsv",
        "monitoring-evidence": "monitoring-evidence.json, status.tsv",
        "incident-runbook-evidence": "incident-runbook-evidence.json, status.tsv",
        "secret-runtime-evidence": "secret-runtime-evidence.json, status.tsv",
        "deployment-environment-evidence": "deployment-environment-evidence.json, status.tsv",
        "tenant-ops-evidence": "tenant-ops-evidence.json, status.tsv",
        "certification-evidence": "psp/fbr/hardware certification-evidence.json files",
        "release-retention-evidence": "release-retention-evidence.json, status.tsv",
        "secret-manager-evidence": "secret-manager-evidence.json, status.tsv",
        "production-ops-readiness": "production-ops-readiness.json, status.tsv",
        "signoff-packages": "release-readiness.json, evidence-summary.md",
    }
    rows = []
    for index, item in enumerate(review_order, start=1):
        rows.append(
            {
                "order": index,
                "artifact": item,
                "primary_files": files.get(item, "summary.md, status.tsv"),
            }
        )
    return rows


def _commands(context):
    env = context["target_environment"]
    run_id = context["run_id"]
    return {
        "local_first_run_checklist": (
            "TIJARA_PROTECTED_RUN_ID=%s TIJARA_TARGET_ENVIRONMENT=%s "
            "make protected-first-run-checklist" % (run_id, env)
        ),
        "local_preflight": (
            "TIJARA_PROTECTED_RUN_ID=%s TIJARA_TARGET_ENVIRONMENT=%s "
            "make protected-runner-preflight" % (run_id, env)
        ),
        "github_cli_dispatch": (
            "gh workflow run tijara-ci.yml "
            "-f protected_release=true -f target_environment=%s -f run_id=%s" % (env, run_id)
        ),
        "readiness_check": (
            "make check-release-readiness READINESS=deploy/runtime/signoff-packages/%s/release-readiness.json"
            % run_id
        ),
        "artifact_summary": (
            "cat deploy/runtime/protected-artifact-summary/%s/summary.md" % run_id
        ),
    }


def _warning_exception_operator_lines(exception):
    if not exception["enabled"]:
        return """
- Exception enabled: no
- Action: keep `TIJARA_PROD_OPS_ALLOW_WARNING_EXCEPTION=0` for this run.
- Audit: verify production operations readiness has no unapproved warnings before go/no-go.
"""
    issue_lines = "\n".join("- %s" % issue for issue in exception["issues"]) or "- None"
    return f"""
- Exception enabled: yes
- Status: {exception["status"]}
- Reference: {exception["reference"] or "<unset>"}
- Approved by: {exception["approved_by"] or "<unset>"}
- Expires at: {exception["expires_at"] or "<unset>"}
- Audit reference: {exception["audit_ref"] or "<unset>"}
- Reason: {exception["reason"] or "<unset>"}

Exception validation issues:

{issue_lines}

Release-owner actions:

- [ ] Confirm the warning is non-critical, bounded, and does not affect customer money, fiscal compliance, or data integrity.
- [ ] Confirm the change/audit reference is visible in the protected GitHub Environment variables.
- [ ] Confirm `production-ops-readiness.json`, `summary.md`, and `evidence-summary.md` record the exception.
- [ ] Confirm a follow-up owner and due date exist before the expiry.
- [ ] Remove or reset exception variables after the approved run, or before expiry if the issue is resolved.
"""


def _operator_runbook(context, commands, review_rows, go_no_go, warning_exception):
    review_lines = "\n".join(
        "%s. `%s` - %s" % (row["order"], row["artifact"], row["primary_files"])
        for row in review_rows
    )
    checklist_lines = "\n".join("- [ ] %s" % item for item in go_no_go)
    return f"""
# Protected Live Staging Handoff Runbook

- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- GitHub environment: {context["github_environment"] or "<unset>"}
- Protected workflow: {context["protected_workflow_ref"] or "<unset>"}
- Staging URL: {context["staging_url"] or "<unset>"}
- Change ticket: {context["change_ticket_ref"] or "<unset>"}
- Rollback plan: {context["rollback_plan_ref"] or "<unset>"}
- Incident channel: {context["incident_channel_ref"] or "<unset>"}
- Backup reference: {context["backup_ref"] or "<unset>"}

## Operators

- Release owner: {context["owners"]["release"] or "<unset>"}
- DevOps owner: {context["owners"]["devops"] or "<unset>"}
- QA owner: {context["owners"]["qa"] or "<unset>"}
- Business owner: {context["owners"]["business"] or "<unset>"}
- Security owner: {context["owners"]["security"] or "<unset>"}
- Support owner: {context["owners"]["support"] or "<unset>"}

## Execution Commands

1. Local first-run checklist:
   `{commands["local_first_run_checklist"]}`
2. Local protected preflight:
   `{commands["local_preflight"]}`
3. GitHub protected workflow dispatch:
   `{commands["github_cli_dispatch"]}`
4. Release readiness gate:
   `{commands["readiness_check"]}`
5. Artifact summary review:
   `{commands["artifact_summary"]}`

## Artifact Review Order

{review_lines}

## Go/No-Go Checklist

{checklist_lines}

## Production Ops Warning Exception

{_warning_exception_operator_lines(warning_exception)}

## Decision Capture

- [ ] Go
- [ ] Go with approved exceptions
- [ ] No-go

Decision owner:

Approval or change-ticket reference:

Exceptions and follow-up owners:
"""


def _artifact_review_markdown(context, review_rows):
    lines = ["# Protected Artifact Review Order", ""]
    lines.append("- Run ID: %s" % context["run_id"])
    lines.append("- Target environment: %s" % context["target_environment"])
    lines.append("")
    for row in review_rows:
        lines.append("%s. `%s`: %s" % (row["order"], row["artifact"], row["primary_files"]))
    return "\n".join(lines)


def _go_no_go_markdown(context, go_no_go):
    lines = ["# Protected Go/No-Go Checklist", ""]
    lines.append("- Run ID: %s" % context["run_id"])
    lines.append("- Target environment: %s" % context["target_environment"])
    lines.append("")
    lines.extend("- [ ] %s" % item for item in go_no_go)
    return "\n".join(lines)


def _warning_exception_markdown(context, exception):
    lines = ["# Production Ops Warning Exception Runbook", ""]
    lines.append("- Run ID: %s" % context["run_id"])
    lines.append("- Target environment: %s" % context["target_environment"])
    lines.append("- Enabled: %s" % ("yes" if exception["enabled"] else "no"))
    lines.append("- Status: %s" % exception["status"])
    lines.append("- Reference: %s" % (exception["reference"] or "<unset>"))
    lines.append("- Approved by: %s" % (exception["approved_by"] or "<unset>"))
    lines.append("- Expires at: %s" % (exception["expires_at"] or "<unset>"))
    lines.append("- Expires at UTC: %s" % (exception["expires_at_utc"] or "<unset>"))
    lines.append("- Audit reference: %s" % (exception["audit_ref"] or "<unset>"))
    lines.append("- Reason: %s" % (exception["reason"] or "<unset>"))
    lines.append("")
    lines.append("## Approval Steps")
    lines.append("")
    lines.append("- [ ] Confirm the warning is not a blocker for payments, FBR, refunds, inventory integrity, security, or customer data.")
    lines.append("- [ ] Confirm the release owner approved the exact warning and reference.")
    lines.append("- [ ] Confirm the exception expiry is in the future and short enough for the risk.")
    lines.append("- [ ] Confirm `TIJARA_PROD_OPS_ALLOW_WARNING_EXCEPTION=1` is scoped to the protected environment and run.")
    lines.append("- [ ] Confirm production operations readiness records the exception as `warning`/`pass_with_warnings`.")
    lines.append("")
    lines.append("## Expiry Steps")
    lines.append("")
    lines.append("- [ ] Open the follow-up work item before the expiry date.")
    lines.append("- [ ] Remove or reset the protected exception variables once the warning is fixed.")
    lines.append("- [ ] Re-run protected production operations readiness without the exception.")
    lines.append("- [ ] If the exception must be extended, create a new reference, approver, reason, and expiry.")
    lines.append("")
    lines.append("## Audit Steps")
    lines.append("")
    lines.append("- [ ] Review `production-ops-readiness.json` warning_exception metadata.")
    lines.append("- [ ] Review sign-off `evidence-summary.md` warning exception line.")
    lines.append("- [ ] Confirm the audit reference links the release, warning, owner, expiry, and follow-up item.")
    lines.append("- [ ] Confirm the exception was not reused for another production run without a new approval.")
    lines.append("")
    lines.append("## Validation Issues")
    lines.append("")
    if exception["issues"]:
        lines.extend("- %s" % issue for issue in exception["issues"])
    else:
        lines.append("- None")
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Runbook Handoff

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

- Runbook manifest: protected-runbook-handoff.json
- Operator runbook: operator-runbook.md
- Warning exception runbook: warning-exception-runbook.md
- Artifact review order: artifact-review-order.md
- Go/no-go checklist: go-no-go-checklist.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara protected live runbook handoff evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_RUNBOOK_HANDOFF_OUTPUT", ""))
    parser.add_argument("--workflow-file", default=os.environ.get("TIJARA_RUNBOOK_WORKFLOW_FILE", ".github/workflows/tijara-ci.yml"))
    parser.add_argument("--github-environment", default=os.environ.get("TIJARA_FIRST_RUN_GITHUB_ENVIRONMENT", ""))
    parser.add_argument("--protected-workflow-ref", default=os.environ.get("TIJARA_FIRST_RUN_PROTECTED_WORKFLOW_REF", ""))
    parser.add_argument("--staging-url", default=os.environ.get("TIJARA_FIRST_RUN_STAGING_URL", os.environ.get("ODOO_BASE_URL", os.environ.get("TIJARA_BASE_URL", ""))))
    parser.add_argument("--change-ticket-ref", default=os.environ.get("TIJARA_FIRST_RUN_CHANGE_TICKET_REF", ""))
    parser.add_argument("--rollback-plan-ref", default=os.environ.get("TIJARA_FIRST_RUN_ROLLBACK_PLAN_REF", ""))
    parser.add_argument("--incident-channel-ref", default=os.environ.get("TIJARA_FIRST_RUN_INCIDENT_CHANNEL_REF", ""))
    parser.add_argument("--backup-ref", default=os.environ.get("TIJARA_FIRST_RUN_BACKUP_REF", os.environ.get("TIJARA_BACKUP_ARTIFACT_REF", "")))
    parser.add_argument("--release-owner", default=os.environ.get("TIJARA_FIRST_RUN_RELEASE_OWNER", ""))
    parser.add_argument("--devops-owner", default=os.environ.get("TIJARA_FIRST_RUN_DEVOPS_OWNER", ""))
    parser.add_argument("--qa-owner", default=os.environ.get("TIJARA_FIRST_RUN_QA_OWNER", ""))
    parser.add_argument("--business-owner", default=os.environ.get("TIJARA_FIRST_RUN_BUSINESS_OWNER", ""))
    parser.add_argument("--security-owner", default=os.environ.get("TIJARA_FIRST_RUN_SECURITY_OWNER", ""))
    parser.add_argument("--support-owner", default=os.environ.get("TIJARA_FIRST_RUN_SUPPORT_OWNER", ""))
    parser.add_argument("--allow-warning-exception", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_ALLOW_WARNING_EXCEPTION", "0")))
    parser.add_argument("--warning-exception-ref", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_REF", ""))
    parser.add_argument("--warning-exception-approved-by", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_APPROVED_BY", ""))
    parser.add_argument("--warning-exception-reason", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_REASON", ""))
    parser.add_argument("--warning-exception-expires-at", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_EXPIRES_AT", ""))
    parser.add_argument("--warning-exception-audit-ref", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_AUDIT_REF", ""))
    parser.add_argument("--artifact-review-order", default=os.environ.get("TIJARA_RUNBOOK_ARTIFACT_REVIEW_ORDER", ",".join(DEFAULT_REVIEW_ORDER)))
    parser.add_argument("--artifact-review-item", action="append", default=[])
    parser.add_argument("--go-no-go-item", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_RUNBOOK_HANDOFF_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-runbook-handoff" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    review_order = _dedupe(_csv_items(args.artifact_review_order) + args.artifact_review_item)
    go_no_go = _dedupe(DEFAULT_GO_NO_GO + args.go_no_go_item)

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

    workflow_path, workflow_errors = _workflow_checks(args.workflow_file)
    if workflow_errors:
        for error in workflow_errors:
            if strict:
                blockers.append(error)
                rows.append(_row("workflow-file", "failed", error))
            else:
                warnings.append(error)
                rows.append(_row("workflow-file", "warning", error))
    else:
        rows.append(_row("workflow-file", "passed", "Protected workflow dispatch surface is present."))

    for name, value, label in [
        ("github-environment", args.github_environment, "GitHub protected environment"),
        ("protected-workflow", args.protected_workflow_ref, "Protected workflow reference"),
        ("staging-url", args.staging_url, "Staging URL"),
        ("change-ticket", args.change_ticket_ref, "Change ticket reference"),
        ("rollback-plan", args.rollback_plan_ref, "Rollback plan reference"),
        ("incident-channel", args.incident_channel_ref, "Incident channel reference"),
        ("backup-reference", args.backup_ref, "Backup reference"),
        ("release-owner", args.release_owner, "Release owner"),
        ("devops-owner", args.devops_owner, "DevOps owner"),
        ("qa-owner", args.qa_owner, "QA owner"),
        ("business-owner", args.business_owner, "Business owner"),
        ("security-owner", args.security_owner, "Security owner"),
        ("support-owner", args.support_owner, "Support owner"),
    ]:
        _add_required(rows, blockers, warnings, strict, name, value, label)

    warning_exception = _warning_exception(args)
    _add_warning_exception_checks(rows, blockers, warnings, strict, warning_exception)

    required_artifacts = {
        "protected-runbook-handoff",
        "protected-first-run",
        "protected-artifact-summary",
        "protected-run-decision",
        "protected-evidence-retention",
        "protected-sidecar-verification",
        "protected-evidence-replay",
        "protected-release-evidence-index",
        "protected-release-closure",
        "protected-closure-result-verification",
        "signoff-packages",
    }
    missing_review = sorted(required_artifacts - set(review_order))
    if missing_review:
        message = "Artifact review order is missing: %s" % ", ".join(missing_review)
        if strict:
            blockers.append(message)
            rows.append(_row("artifact-review-order", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("artifact-review-order", "warning", message))
    else:
        rows.append(_row("artifact-review-order", "passed", "%s artifact group(s) listed." % len(review_order)))

    if len(go_no_go) < len(DEFAULT_GO_NO_GO):
        message = "Go/no-go checklist is shorter than the default checklist."
        if strict:
            blockers.append(message)
            rows.append(_row("go-no-go-checklist", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("go-no-go-checklist", "warning", message))
    else:
        rows.append(_row("go-no-go-checklist", "passed", "%s go/no-go item(s) listed." % len(go_no_go)))

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
        "strict": strict,
        "workflow_file": str(workflow_path),
        "github_environment": args.github_environment,
        "protected_workflow_ref": args.protected_workflow_ref,
        "staging_url": args.staging_url,
        "change_ticket_ref": args.change_ticket_ref,
        "rollback_plan_ref": args.rollback_plan_ref,
        "incident_channel_ref": args.incident_channel_ref,
        "backup_ref": args.backup_ref,
        "owners": {
            "release": args.release_owner,
            "devops": args.devops_owner,
            "qa": args.qa_owner,
            "business": args.business_owner,
            "security": args.security_owner,
            "support": args.support_owner,
        },
        "warning_exception": warning_exception,
    }
    commands = _commands(context)
    review_rows = _artifact_review_rows(review_order)
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "commands": commands,
        "artifact_review_order": review_rows,
        "go_no_go_checklist": go_no_go,
        "warning_exception": warning_exception,
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "github_environment=%s" % (args.github_environment or "<unset>"),
            "workflow_file=%s" % workflow_path,
            "artifact_review_order=%s" % ",".join(review_order),
            "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
            "allow_warning_exception=%s" % int(warning_exception["enabled"]),
            "warning_exception_status=%s" % warning_exception["status"],
            "warning_exception_ref=%s" % (warning_exception["reference"] or "<unset>"),
            "warning_exception_approved_by=%s" % (warning_exception["approved_by"] or "<unset>"),
            "warning_exception_expires_at=%s" % (warning_exception["expires_at"] or "<unset>"),
            "warning_exception_audit_ref=%s" % (warning_exception["audit_ref"] or "<unset>"),
            "strict=%s" % int(strict),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )

    _write(output / "protected-runbook-handoff.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "operator-runbook.md", _operator_runbook(context, commands, review_rows, go_no_go, warning_exception))
    _write(output / "warning-exception-runbook.md", _warning_exception_markdown(context, warning_exception))
    _write(output / "artifact-review-order.md", _artifact_review_markdown(context, review_rows))
    _write(output / "go-no-go-checklist.md", _go_no_go_markdown(context, go_no_go))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Protected runbook handoff written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
