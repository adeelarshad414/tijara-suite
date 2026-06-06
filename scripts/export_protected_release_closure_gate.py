#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_DECISIONS = {"approved", "ready", "passed", "pass", "success", "ok", "promotion_ready"}
WARNING_DECISIONS = {"warning", "warn", "pass_with_warnings"}
FAILING_DECISIONS = {"blocked", "failed", "fail", "error"}
DEFAULT_REQUIRED_ARTIFACTS = [
    "primary_artifact",
    "sidecar_artifact",
]
DEFAULT_REQUIRED_REVIEW_FILES = [
    "run_decision",
    "release_readiness",
    "signoff_package",
    "retention_manifest",
    "sidecar_verification",
    "evidence_replay",
    "certification_matrix",
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


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


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


def _secret_like_keys(value, prefix=""):
    flagged = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = "%s.%s" % (prefix, key) if prefix else str(key)
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in SECRET_KEY_PARTS):
                flagged.append(key_path)
            flagged.extend(_secret_like_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            flagged.extend(_secret_like_keys(child, "%s[%s]" % (prefix, index)))
    return flagged


def _read_json(path):
    target = _resolve(path)
    if not target.is_file():
        return {}, target, "missing"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, target, "read_error:%s" % error
    return payload if isinstance(payload, dict) else {}, target, "ok"


def _decision_fields(payload):
    decision = str(payload.get("decision") or payload.get("status") or "").strip()
    ci_status = str(payload.get("ci_status") or "").strip()
    if not decision and ci_status:
        decision = ci_status
    return decision, ci_status


def _decision_state(decision, ci_status):
    decision_value = str(decision or "").lower()
    ci_value = str(ci_status or "").lower()
    if decision_value in FAILING_DECISIONS or ci_value in FAILING_DECISIONS:
        return "failed"
    if decision_value in WARNING_DECISIONS or ci_value in WARNING_DECISIONS:
        return "warning"
    if decision_value in PASS_DECISIONS or ci_value in PASS_DECISIONS:
        return "passed"
    return "missing"


def _review_index(index_payload):
    components = []
    for component in index_payload.get("components") or []:
        if isinstance(component, dict):
            components.append(component)
    links = index_payload.get("artifact_links") if isinstance(index_payload.get("artifact_links"), dict) else {}
    review_files = (
        index_payload.get("operator_review_files")
        if isinstance(index_payload.get("operator_review_files"), dict)
        else {}
    )
    return components, links, review_files


def _artifact_present(artifact):
    return bool(artifact.get("id") and artifact.get("artifact_url"))


def _approval_items(args):
    return [
        ("release-owner", args.release_owner, "Release owner approval"),
        ("devops-owner", args.devops_owner, "DevOps owner approval"),
        ("qa-owner", args.qa_owner, "QA owner approval"),
        ("security-owner", args.security_owner, "Security owner approval"),
        ("business-owner", args.business_owner, "Business owner approval"),
    ]


def _add_approval_checks(rows, blockers, warnings, strict, require_approvals, approval_items):
    for name, value, label in approval_items:
        if value:
            rows.append(_row(name, "passed", "%s recorded: %s" % (label, value)))
        elif require_approvals and strict:
            message = "%s is required for protected release closure." % label
            blockers.append(message)
            rows.append(_row(name, "failed", message))
        elif require_approvals:
            message = "%s is missing." % label
            warnings.append(message)
            rows.append(_row(name, "warning", message))
        else:
            rows.append(_row(name, "skipped", "%s not required for this closure gate." % label))


def _add_required_ref(rows, blockers, warnings, strict, name, value, label):
    if value:
        rows.append(_row(name, "passed", "%s recorded: %s" % (label, value)))
    elif strict:
        message = "%s is required for protected release closure." % label
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        message = "%s is missing." % label
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _review_components(rows, blockers, warnings, components, required_components):
    by_name = {str(component.get("name") or ""): component for component in components}
    for name in required_components:
        component = by_name.get(name)
        if not component:
            message = "Evidence index component is missing: %s" % name
            blockers.append(message)
            rows.append(_row("component-%s" % name, "failed", message))
            continue
        status = str(component.get("status") or "").lower()
        decision = str(component.get("decision") or "").lower()
        ci_status = str(component.get("ci_status") or "").lower()
        if status in {"failed", "blocked", "error"} or decision in FAILING_DECISIONS or ci_status in FAILING_DECISIONS:
            message = "Evidence index component %s is failing: %s/%s/%s." % (
                name,
                status or "unknown",
                decision or "unknown",
                ci_status or "unknown",
            )
            blockers.append(message)
            rows.append(_row("component-%s" % name, "failed", message, component.get("primary_json") or component.get("path") or ""))
        elif status in {"warning", "warn", "skipped"} or decision in WARNING_DECISIONS or ci_status in WARNING_DECISIONS:
            message = "Evidence index component %s has warnings: %s/%s/%s." % (
                name,
                status or "unknown",
                decision or "unknown",
                ci_status or "unknown",
            )
            warnings.append(message)
            rows.append(_row("component-%s" % name, "warning", message, component.get("primary_json") or component.get("path") or ""))
        else:
            rows.append(_row("component-%s" % name, "passed", "Evidence index component is passing.", component.get("primary_json") or component.get("path") or ""))


def _review_artifacts(rows, blockers, warnings, strict, links, required_artifacts):
    for name in required_artifacts:
        artifact = links.get(name) if isinstance(links.get(name), dict) else {}
        if _artifact_present(artifact):
            rows.append(_row("artifact-%s" % name, "passed", "Artifact ID and URL are recorded.", artifact.get("artifact_url") or ""))
        else:
            message = "%s ID and URL are required." % name.replace("_", " ")
            if strict:
                blockers.append(message)
                rows.append(_row("artifact-%s" % name, "failed", message))
            else:
                warnings.append(message)
                rows.append(_row("artifact-%s" % name, "warning", message))
        if artifact.get("digest"):
            rows.append(_row("artifact-%s-digest" % name, "passed", "Artifact digest is recorded."))
        else:
            warnings.append("%s digest is missing." % name.replace("_", " "))
            rows.append(_row("artifact-%s-digest" % name, "warning", "Artifact digest is missing."))


def _review_files(rows, blockers, warnings, strict, review_files, required_files):
    for name in required_files:
        value = str(review_files.get(name) or "")
        if value:
            rows.append(_row("review-file-%s" % name, "passed", "Review file is indexed.", value))
        elif strict:
            message = "Operator review file is missing from evidence index: %s" % name
            blockers.append(message)
            rows.append(_row("review-file-%s" % name, "failed", message))
        else:
            message = "Operator review file is missing from evidence index: %s" % name
            warnings.append(message)
            rows.append(_row("review-file-%s" % name, "warning", message))


def _promotion_checklist(context, rows, approval_items, links, blockers, warnings):
    primary = links.get("primary_artifact") if isinstance(links.get("primary_artifact"), dict) else {}
    sidecar = links.get("sidecar_artifact") if isinstance(links.get("sidecar_artifact"), dict) else {}
    checklist_lines = []
    for row in rows:
        marker = "[x]" if row["status"] == "passed" else "[ ]"
        checklist_lines.append("- %s `%s`: %s" % (marker, row["name"], row["message"]))
    approval_lines = []
    for _, value, label in approval_items:
        approval_lines.append("- %s: `%s`" % (label, value or "missing"))
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Closure Checklist

- Closure decision: `{context["closure_decision"]}`
- CI status: `{context["ci_status"]}`
- Run ID: `{context["run_id"]}`
- Target environment: `{context["target_environment"]}`
- Generated: `{context["generated_at"]}`
- Primary release artifact: `{primary.get("id") or "missing"}` {primary.get("artifact_url") or ""}
- Protected metadata sidecar: `{sidecar.get("id") or "missing"}` {sidecar.get("artifact_url") or ""}

## Approvals

{chr(10).join(approval_lines)}

## Checklist

{chr(10).join(checklist_lines)}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}
"""


def _summary(context, blockers, warnings):
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Closure Gate

- Closure decision: {context["closure_decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Evidence index: {context["evidence_index"]}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Closure decision: protected-release-closure-decision.json
- Promotion checklist: promotion-checklist.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "evidence_index=%s" % context["evidence_index"],
            "closure_decision=%s" % context["closure_decision"],
            "ci_status=%s" % context["ci_status"],
            "require_approvals=%s" % int(context["require_approvals"]),
            "fail_on_warning=%s" % int(context["fail_on_warning"]),
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Export final protected release closure gate decision.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_CLOSURE_OUTPUT", ""))
    parser.add_argument(
        "--evidence-index",
        default=os.environ.get("TIJARA_PROTECTED_CLOSURE_EVIDENCE_INDEX", ""),
    )
    parser.add_argument(
        "--required-components",
        default=os.environ.get(
            "TIJARA_PROTECTED_CLOSURE_REQUIRED_COMPONENTS",
            "release-readiness,protected-run-decision,protected-evidence-retention,protected-sidecar-verification,protected-evidence-replay,signoff-package,certification-result-matrix,github-artifact-metadata",
        ),
    )
    parser.add_argument(
        "--required-artifacts",
        default=os.environ.get("TIJARA_PROTECTED_CLOSURE_REQUIRED_ARTIFACTS", ",".join(DEFAULT_REQUIRED_ARTIFACTS)),
    )
    parser.add_argument(
        "--required-review-files",
        default=os.environ.get("TIJARA_PROTECTED_CLOSURE_REQUIRED_REVIEW_FILES", ",".join(DEFAULT_REQUIRED_REVIEW_FILES)),
    )
    parser.add_argument("--release-owner", default=os.environ.get("TIJARA_CLOSURE_RELEASE_OWNER", os.environ.get("TIJARA_FIRST_RUN_RELEASE_OWNER", "")))
    parser.add_argument("--devops-owner", default=os.environ.get("TIJARA_CLOSURE_DEVOPS_OWNER", os.environ.get("TIJARA_FIRST_RUN_DEVOPS_OWNER", "")))
    parser.add_argument("--qa-owner", default=os.environ.get("TIJARA_CLOSURE_QA_OWNER", os.environ.get("TIJARA_FIRST_RUN_QA_OWNER", "")))
    parser.add_argument("--security-owner", default=os.environ.get("TIJARA_CLOSURE_SECURITY_OWNER", os.environ.get("TIJARA_FIRST_RUN_SECURITY_OWNER", "")))
    parser.add_argument("--business-owner", default=os.environ.get("TIJARA_CLOSURE_BUSINESS_OWNER", os.environ.get("TIJARA_FIRST_RUN_BUSINESS_OWNER", "")))
    parser.add_argument("--change-ticket-ref", default=os.environ.get("TIJARA_CLOSURE_CHANGE_TICKET_REF", os.environ.get("TIJARA_FIRST_RUN_CHANGE_TICKET_REF", "")))
    parser.add_argument("--rollback-plan-ref", default=os.environ.get("TIJARA_CLOSURE_ROLLBACK_PLAN_REF", os.environ.get("TIJARA_FIRST_RUN_ROLLBACK_PLAN_REF", "")))
    parser.add_argument("--incident-channel-ref", default=os.environ.get("TIJARA_CLOSURE_INCIDENT_CHANNEL_REF", os.environ.get("TIJARA_FIRST_RUN_INCIDENT_CHANNEL_REF", "")))
    parser.add_argument("--release-window-ref", default=os.environ.get("TIJARA_CLOSURE_RELEASE_WINDOW_REF", ""))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--require-approvals",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_CLOSURE_REQUIRE_APPROVALS", "1")),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_CLOSURE_FAIL_ON_WARNING", "1")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_CLOSURE_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-release-closure" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    evidence_index = args.evidence_index or "deploy/runtime/protected-release-evidence-index/%s/protected-release-evidence-index.json" % args.run_id
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

    index_payload, index_path, read_status = _read_json(evidence_index)
    if read_status == "ok":
        rows.append(_row("evidence-index", "passed", "Evidence index is readable.", _repo_relative(index_path)))
    elif strict:
        message = "Evidence index is %s." % read_status
        blockers.append(message)
        rows.append(_row("evidence-index", "failed", message, _repo_relative(index_path)))
    else:
        message = "Evidence index is %s." % read_status
        warnings.append(message)
        rows.append(_row("evidence-index", "warning", message, _repo_relative(index_path)))

    index_decision, index_ci_status = _decision_fields(index_payload)
    index_state = _decision_state(index_decision, index_ci_status)
    if index_state == "passed":
        rows.append(_row("evidence-index-decision", "passed", "Evidence index decision is passing."))
    elif index_state == "warning":
        message = "Evidence index decision has warnings: %s/%s." % (index_decision or "unknown", index_ci_status or "unknown")
        warnings.append(message)
        rows.append(_row("evidence-index-decision", "warning", message))
    else:
        message = "Evidence index decision is failing or missing: %s/%s." % (index_decision or "unknown", index_ci_status or "unknown")
        blockers.append(message)
        rows.append(_row("evidence-index-decision", "failed", message))

    for blocker in index_payload.get("blockers") or []:
        blockers.append("evidence-index: %s" % blocker)
    for warning in index_payload.get("warnings") or []:
        warnings.append("evidence-index: %s" % warning)

    components, links, review_files = _review_index(index_payload)
    _review_components(rows, blockers, warnings, components, _dedupe(_csv_items(args.required_components)))
    _review_artifacts(rows, blockers, warnings, strict, links, _dedupe(_csv_items(args.required_artifacts)))
    _review_files(rows, blockers, warnings, strict, review_files, _dedupe(_csv_items(args.required_review_files)))
    _add_approval_checks(rows, blockers, warnings, strict, args.require_approvals, _approval_items(args))
    _add_required_ref(rows, blockers, warnings, strict, "change-ticket-ref", args.change_ticket_ref, "Change ticket reference")
    _add_required_ref(rows, blockers, warnings, strict, "rollback-plan-ref", args.rollback_plan_ref, "Rollback plan reference")
    _add_required_ref(rows, blockers, warnings, strict, "incident-channel-ref", args.incident_channel_ref, "Incident channel reference")
    if args.release_window_ref:
        rows.append(_row("release-window-ref", "passed", "Release window reference recorded: %s" % args.release_window_ref))
    else:
        warnings.append("Release window reference is missing.")
        rows.append(_row("release-window-ref", "warning", "Release window reference is missing."))

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    if args.fail_on_warning and warnings:
        blockers.extend("Warning treated as blocker: %s" % warning for warning in warnings)
        blockers = _dedupe(blockers)
    if blockers:
        closure_decision = "blocked"
        ci_status = "fail"
    elif warnings:
        closure_decision = "watch"
        ci_status = "pass_with_warnings"
    else:
        closure_decision = "promotion_ready"
        ci_status = "pass"
    if not strict and blockers and all("missing" in blocker.lower() for blocker in blockers):
        warnings.extend(blockers)
        blockers = []
        closure_decision = "watch"
        ci_status = "pass_with_warnings"

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "evidence_index": _repo_relative(index_path),
        "closure_decision": closure_decision,
        "ci_status": ci_status,
        "require_approvals": bool(args.require_approvals),
        "fail_on_warning": bool(args.fail_on_warning),
        "strict": strict,
    }
    approval_refs = {
        name: value for name, value, _ in _approval_items(args)
    }
    manifest = {
        "context": context,
        "decision": closure_decision,
        "closure_decision": closure_decision,
        "ci_status": ci_status,
        "evidence_index": {
            "path": _repo_relative(index_path),
            "decision": index_decision,
            "ci_status": index_ci_status,
            "read_status": read_status,
        },
        "approval_refs": approval_refs,
        "operational_refs": {
            "change_ticket_ref": args.change_ticket_ref,
            "rollback_plan_ref": args.rollback_plan_ref,
            "incident_channel_ref": args.incident_channel_ref,
            "release_window_ref": args.release_window_ref,
        },
        "artifact_links": links,
        "review_files": review_files,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-release-closure-decision.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "promotion-checklist.md", _promotion_checklist(context, rows, _approval_items(args), links, blockers, warnings))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, blockers, warnings))
    print("Protected release closure gate written to %s" % output)
    print("decision=%s" % closure_decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
