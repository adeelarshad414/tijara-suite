#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
DEFAULT_ARTIFACTS = [
    "protected-runbook-handoff",
    "protected-first-run",
    "protected-runner-preflight",
    "protected-service-checks",
    "release-evidence",
    "protected-e2e",
    "ops-tool-evidence",
    "certification-evidence",
    "release-retention-evidence",
    "secret-manager-evidence",
    "production-ops-readiness",
    "signoff-packages",
    "protected-post-run-verification",
    "github-artifact-metadata",
    "protected-artifact-summary",
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
    seen = set()
    clean = []
    for item in items:
        item = str(item or "").strip()
        if item and item not in seen:
            seen.add(item)
            clean.append(item)
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


def _present(value):
    return bool(str(value or "").strip())


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
    message = "%s is required for the first protected run." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _add_label_check(rows, blockers, warnings, strict, labels, required_labels):
    required = set(required_labels)
    actual = {label.strip() for label in labels if label.strip()}
    missing = sorted(required - actual)
    if not missing:
        rows.append(_row("runner-labels", "passed", "Required protected runner labels are recorded."))
        return
    message = "Protected runner labels missing: %s" % ", ".join(missing)
    if strict:
        blockers.append(message)
        rows.append(_row("runner-labels", "failed", message))
    else:
        warnings.append(message)
        rows.append(_row("runner-labels", "warning", message))


def _add_artifact_check(rows, blockers, warnings, strict, artifacts):
    actual = set(artifacts)
    missing = [artifact for artifact in DEFAULT_ARTIFACTS if artifact not in actual]
    if not missing:
        rows.append(_row("expected-artifacts", "passed", "All default protected artifacts are expected."))
        return
    message = "Expected artifact group(s) missing from checklist: %s" % ", ".join(missing)
    if strict:
        blockers.append(message)
        rows.append(_row("expected-artifacts", "failed", message))
    else:
        warnings.append(message)
        rows.append(_row("expected-artifacts", "warning", message))


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected First Run Checklist

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

- First run checklist manifest: protected-first-run-checklist.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara protected first-run checklist evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_FIRST_RUN_OUTPUT", ""))
    parser.add_argument("--github-environment", default=os.environ.get("TIJARA_FIRST_RUN_GITHUB_ENVIRONMENT", ""))
    parser.add_argument("--runner-labels", default=os.environ.get("TIJARA_FIRST_RUN_RUNNER_LABELS", ""))
    parser.add_argument("--required-runner-label", action="append", default=[])
    parser.add_argument(
        "--required-runner-labels",
        default=os.environ.get("TIJARA_FIRST_RUN_REQUIRED_RUNNER_LABELS", "self-hosted,tijara-protected"),
    )
    parser.add_argument("--release-owner", default=os.environ.get("TIJARA_FIRST_RUN_RELEASE_OWNER", ""))
    parser.add_argument("--devops-owner", default=os.environ.get("TIJARA_FIRST_RUN_DEVOPS_OWNER", ""))
    parser.add_argument("--qa-owner", default=os.environ.get("TIJARA_FIRST_RUN_QA_OWNER", ""))
    parser.add_argument("--business-owner", default=os.environ.get("TIJARA_FIRST_RUN_BUSINESS_OWNER", ""))
    parser.add_argument("--security-owner", default=os.environ.get("TIJARA_FIRST_RUN_SECURITY_OWNER", ""))
    parser.add_argument("--support-owner", default=os.environ.get("TIJARA_FIRST_RUN_SUPPORT_OWNER", ""))
    parser.add_argument("--finance-owner", default=os.environ.get("TIJARA_FIRST_RUN_FINANCE_OWNER", ""))
    parser.add_argument("--tax-owner", default=os.environ.get("TIJARA_FIRST_RUN_TAX_OWNER", ""))
    parser.add_argument("--hardware-owner", default=os.environ.get("TIJARA_FIRST_RUN_HARDWARE_OWNER", ""))
    parser.add_argument("--staging-url", default=os.environ.get("TIJARA_FIRST_RUN_STAGING_URL", ""))
    parser.add_argument("--change-ticket-ref", default=os.environ.get("TIJARA_FIRST_RUN_CHANGE_TICKET_REF", ""))
    parser.add_argument("--rollback-plan-ref", default=os.environ.get("TIJARA_FIRST_RUN_ROLLBACK_PLAN_REF", ""))
    parser.add_argument("--incident-channel-ref", default=os.environ.get("TIJARA_FIRST_RUN_INCIDENT_CHANNEL_REF", ""))
    parser.add_argument("--backup-ref", default=os.environ.get("TIJARA_FIRST_RUN_BACKUP_REF", ""))
    parser.add_argument("--protected-workflow-ref", default=os.environ.get("TIJARA_FIRST_RUN_PROTECTED_WORKFLOW_REF", ""))
    parser.add_argument("--expected-artifact", action="append", default=[])
    parser.add_argument("--expected-artifacts", default=os.environ.get("TIJARA_FIRST_RUN_EXPECTED_ARTIFACTS", ",".join(DEFAULT_ARTIFACTS)))
    parser.add_argument("--certification-groups", default=os.environ.get("TIJARA_PROTECTED_CERTIFICATION_GROUPS", ""))
    parser.add_argument("--require-certifications", action="store_true", default=_truthy(os.environ.get("TIJARA_FIRST_RUN_REQUIRE_CERTIFICATIONS")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_FIRST_RUN_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-first-run" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    certification_groups = [item.lower() for item in _csv_items(args.certification_groups)]
    expected_artifacts = _dedupe(_csv_items(args.expected_artifacts) + args.expected_artifact)
    required_runner_labels = _dedupe(
        _csv_items(args.required_runner_labels) + args.required_runner_label
    )
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

    for name, value, label in [
        ("github-environment", args.github_environment, "GitHub protected environment"),
        ("release-owner", args.release_owner, "Release owner"),
        ("devops-owner", args.devops_owner, "DevOps owner"),
        ("qa-owner", args.qa_owner, "QA owner"),
        ("business-owner", args.business_owner, "Business owner"),
        ("security-owner", args.security_owner, "Security owner"),
        ("support-owner", args.support_owner, "Support owner"),
        ("staging-url", args.staging_url, "Staging URL"),
        ("change-ticket", args.change_ticket_ref, "Change ticket reference"),
        ("rollback-plan", args.rollback_plan_ref, "Rollback plan reference"),
        ("incident-channel", args.incident_channel_ref, "Incident channel reference"),
        ("backup-reference", args.backup_ref, "Backup reference"),
        ("protected-workflow", args.protected_workflow_ref, "Protected workflow reference"),
    ]:
        _add_required(rows, blockers, warnings, strict, name, value, label)

    _add_label_check(rows, blockers, warnings, strict, _csv_items(args.runner_labels), required_runner_labels)
    _add_artifact_check(rows, blockers, warnings, strict, expected_artifacts)

    if args.require_certifications and not certification_groups:
        message = "Certification groups are required for this first protected run."
        if strict:
            blockers.append(message)
            rows.append(_row("certification-groups", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("certification-groups", "warning", message))
    else:
        rows.append(_row("certification-groups", "passed", "Certification groups: %s." % (",".join(certification_groups) or "none")))

    conditional_owners = [
        ("psp", "finance-owner", args.finance_owner, "Finance owner"),
        ("fbr", "tax-owner", args.tax_owner, "Tax owner"),
        ("hardware", "hardware-owner", args.hardware_owner, "Hardware owner"),
    ]
    for group, name, value, label in conditional_owners:
        if group in certification_groups:
            _add_required(rows, blockers, warnings, strict, name, value, label)
        elif _present(value):
            rows.append(_row(name, "passed", "%s is recorded." % label))
        else:
            rows.append(_row(name, "passed", "%s is optional for this run." % label))

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
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "owners": {
            "release": args.release_owner,
            "devops": args.devops_owner,
            "qa": args.qa_owner,
            "business": args.business_owner,
            "security": args.security_owner,
            "support": args.support_owner,
            "finance": args.finance_owner,
            "tax": args.tax_owner,
            "hardware": args.hardware_owner,
        },
        "references": {
            "github_environment": args.github_environment,
            "runner_labels": _csv_items(args.runner_labels),
            "required_runner_labels": required_runner_labels,
            "staging_url": args.staging_url,
            "change_ticket": args.change_ticket_ref,
            "rollback_plan": args.rollback_plan_ref,
            "incident_channel": args.incident_channel_ref,
            "backup": args.backup_ref,
            "protected_workflow": args.protected_workflow_ref,
            "expected_artifacts": expected_artifacts,
            "certification_groups": certification_groups,
        },
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "github_environment=%s" % (args.github_environment or "<unset>"),
            "runner_labels=%s" % (args.runner_labels or "<unset>"),
            "required_runner_labels=%s" % (",".join(required_runner_labels) or "<unset>"),
            "certification_groups=%s" % (",".join(certification_groups) or "<none>"),
            "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
            "strict=%s" % int(strict),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-first-run-checklist.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Protected first-run checklist written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
