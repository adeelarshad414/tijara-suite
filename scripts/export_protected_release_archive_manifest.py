#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_STATUSES = {"approved", "ready", "passed", "pass", "success", "ok", "promotion_ready"}
WARNING_STATUSES = {"warning", "warn", "watch", "pass_with_warnings"}
FAILING_STATUSES = {"blocked", "failed", "fail", "error"}
VALID_CLOSURE_DECISIONS = {"promotion_ready", "watch", "blocked"}
DEFAULT_REQUIRED_COMPONENTS = [
    "github-artifact-metadata",
    "protected-evidence-retention",
    "protected-sidecar-verification",
    "protected-evidence-replay",
    "protected-release-evidence-index",
    "protected-release-closure",
    "protected-closure-result-verification",
    "release-retention-evidence",
]
DEFAULT_COMPONENT_PATHS = {
    "github-artifact-metadata": "deploy/runtime/github-artifact-metadata/{run_id}/github-artifact-metadata.json",
    "protected-evidence-retention": "deploy/runtime/protected-evidence-retention/{run_id}/protected-evidence-retention-manifest.json",
    "protected-sidecar-verification": "deploy/runtime/protected-sidecar-verification/{run_id}/protected-sidecar-verification.json",
    "protected-evidence-replay": "deploy/runtime/protected-evidence-replay/{run_id}/protected-evidence-replay-report.json",
    "protected-release-evidence-index": "deploy/runtime/protected-release-evidence-index/{run_id}/protected-release-evidence-index.json",
    "protected-release-closure": "deploy/runtime/protected-release-closure/{run_id}/protected-release-closure-decision.json",
    "protected-closure-result-verification": "deploy/runtime/protected-closure-result-verification/{run_id}/protected-closure-result-verification.json",
    "release-retention-evidence": "deploy/runtime/release-retention-evidence/{run_id}/release-retention-evidence.json",
}


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


def _component_overrides(items):
    overrides = {}
    for raw in items or []:
        if "=" not in raw:
            raise ValueError("Component override must use name=path format: %s" % raw)
        name, value = raw.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            raise ValueError("Component override name and path are required: %s" % raw)
        overrides[name] = value
    return overrides


def _component_path(name, run_id, overrides):
    raw = overrides.get(name) or DEFAULT_COMPONENT_PATHS.get(name)
    if not raw:
        raw = "deploy/runtime/%s/%s/%s.json" % (name, run_id, name)
    return _resolve(raw.format(run_id=run_id))


def _read_json(path):
    if not path.is_file():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, "read_error:%s" % error
    return payload if isinstance(payload, dict) else {}, "ok"


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _decision_fields(payload):
    decision = str(payload.get("decision") or payload.get("closure_decision") or payload.get("status") or "").strip()
    ci_status = str(payload.get("ci_status") or "").strip()
    if not decision and ci_status:
        decision = ci_status
    return decision, ci_status


def _decision_state(decision, ci_status):
    decision_value = str(decision or "").lower()
    ci_value = str(ci_status or "").lower()
    if decision_value in FAILING_STATUSES or ci_value in FAILING_STATUSES:
        return "failed"
    if decision_value in WARNING_STATUSES or ci_value in WARNING_STATUSES:
        return "warning"
    if decision_value in PASS_STATUSES or ci_value in PASS_STATUSES:
        return "passed"
    return "missing"


def _component_review(name, path, required):
    payload, read_status = _read_json(path)
    decision, ci_status = _decision_fields(payload)
    state = _decision_state(decision, ci_status)
    blockers = []
    warnings = []
    if read_status == "missing":
        if required:
            blockers.append("%s archive source is missing." % name)
            status = "failed"
            message = "Required archive source is missing."
        else:
            status = "skipped"
            message = "Optional archive source is missing."
    elif read_status.startswith("read_error:"):
        blockers.append("%s archive source could not be read." % name)
        status = "failed"
        message = read_status
    elif state == "failed" and name != "protected-release-closure":
        blockers.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        status = "failed"
        message = "Archive source decision is failing."
    elif state == "failed":
        status = "passed"
        message = "Closure source is archived even when the release is blocked."
    elif state == "warning":
        warnings.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        status = "warning"
        message = "Archive source decision has warnings."
    elif state == "passed":
        status = "passed"
        message = "Archive source decision is passing."
    else:
        warnings.append("%s decision is missing." % name)
        status = "warning"
        message = "Archive source decision is missing."
    return {
        "name": name,
        "path": _repo_relative(path),
        "required": bool(required),
        "read_status": read_status,
        "status": status,
        "message": message,
        "decision": decision,
        "ci_status": ci_status,
        "payload": payload,
        "blockers": blockers,
        "warnings": warnings,
    }


def _artifact_from(payload, key):
    artifact = payload.get(key) if isinstance(payload.get(key), dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _artifact_from_links(payload, key):
    links = payload.get("artifact_links") if isinstance(payload.get("artifact_links"), dict) else {}
    artifact = links.get(key) if isinstance(links.get(key), dict) else {}
    return artifact


def _artifact_record(label, artifact, source):
    return {
        "label": label,
        "name": str(artifact.get("name") or ""),
        "id": str(artifact.get("id") or ""),
        "artifact_url": str(artifact.get("artifact_url") or ""),
        "api_url": str(artifact.get("api_url") or ""),
        "archive_download_url": str(artifact.get("archive_download_url") or ""),
        "digest": str(artifact.get("digest") or ""),
        "retention_days": str(artifact.get("retention_days") or ""),
        "expires_at": str(artifact.get("expires_at") or ""),
        "source": source,
    }


def _collect_artifacts(by_name):
    metadata = by_name.get("github-artifact-metadata", {}).get("payload", {})
    retention = by_name.get("protected-evidence-retention", {}).get("payload", {})
    sidecar = by_name.get("protected-sidecar-verification", {}).get("payload", {})
    replay = by_name.get("protected-evidence-replay", {}).get("payload", {})
    evidence_index = by_name.get("protected-release-evidence-index", {}).get("payload", {})
    closure_result = by_name.get("protected-closure-result-verification", {}).get("payload", {})
    artifacts = [
        _artifact_record("primary-release-evidence", _artifact_from(metadata, "artifact"), "github-artifact-metadata"),
        _artifact_record("retained-primary-release-evidence", _artifact_from(retention, "uploaded_artifact"), "protected-evidence-retention"),
        _artifact_record("sidecar-primary-reference", _artifact_from(sidecar, "primary_artifact"), "protected-sidecar-verification"),
        _artifact_record("replay-primary-reference", _artifact_from(replay, "primary_artifact"), "protected-evidence-replay"),
        _artifact_record("indexed-primary-reference", _artifact_from_links(evidence_index, "primary_artifact"), "protected-release-evidence-index"),
        _artifact_record("metadata-sidecar", _artifact_from(sidecar, "sidecar_artifact"), "protected-sidecar-verification"),
        _artifact_record("replay-sidecar-reference", _artifact_from(replay, "sidecar_artifact"), "protected-evidence-replay"),
        _artifact_record("indexed-sidecar-reference", _artifact_from_links(evidence_index, "sidecar_artifact"), "protected-release-evidence-index"),
        _artifact_record("final-closure-result", _artifact_from(closure_result, "final_artifact"), "protected-closure-result-verification"),
    ]
    clean = []
    seen = set()
    for artifact in artifacts:
        identity = (artifact["label"], artifact["id"], artifact["artifact_url"])
        if identity not in seen:
            seen.add(identity)
            clean.append(artifact)
    return clean


def _closure_summary(by_name):
    closure = by_name.get("protected-release-closure", {}).get("payload", {})
    closure_result = by_name.get("protected-closure-result-verification", {}).get("payload", {})
    closure_context = closure.get("context") if isinstance(closure.get("context"), dict) else {}
    result_context = closure_result.get("context") if isinstance(closure_result.get("context"), dict) else {}
    closure_pointer = closure_result.get("closure_pointer") if isinstance(closure_result.get("closure_pointer"), dict) else {}
    return {
        "closure_decision": str(closure.get("closure_decision") or closure.get("decision") or ""),
        "closure_ci_status": str(closure.get("ci_status") or ""),
        "closure_result_decision": str(closure_result.get("decision") or ""),
        "closure_result_ci_status": str(closure_result.get("ci_status") or ""),
        "closure_result_closure_decision": str(
            closure_result.get("closure_decision") or result_context.get("closure_decision") or ""
        ),
        "closure_decision_file": closure_pointer.get("closure_decision") or "",
        "promotion_checklist": closure_pointer.get("promotion_checklist") or "",
        "evidence_index": closure_pointer.get("evidence_index") or closure_context.get("evidence_index") or "",
        "release_owner_decision": str(closure.get("closure_decision") or closure.get("decision") or ""),
    }


def _retention_summary(by_name):
    release_retention = by_name.get("release-retention-evidence", {}).get("payload", {})
    context = release_retention.get("context") if isinstance(release_retention.get("context"), dict) else {}
    return {
        "artifact_retention_policy_ref": release_retention.get("artifact_retention_policy_ref") or context.get("artifact_retention_policy_ref") or "",
        "ci_artifact_retention_days": release_retention.get("ci_artifact_retention_days") or context.get("ci_artifact_retention_days") or "",
        "release_evidence_retention_days": release_retention.get("release_evidence_retention_days") or context.get("release_evidence_retention_days") or "",
        "certification_evidence_retention_days": release_retention.get("certification_evidence_retention_days") or context.get("certification_evidence_retention_days") or "",
    }


def _review_artifacts(rows, blockers, warnings, strict, artifacts, minimum_retention_days):
    for artifact in artifacts:
        label = artifact["label"]
        if artifact["id"] and artifact["artifact_url"]:
            rows.append(_row("artifact-%s" % label, "passed", "Artifact ID and URL are archived.", artifact["artifact_url"]))
        elif strict:
            message = "%s artifact ID and URL are required." % label
            blockers.append(message)
            rows.append(_row("artifact-%s" % label, "failed", message))
        else:
            message = "%s artifact ID or URL is missing." % label
            warnings.append(message)
            rows.append(_row("artifact-%s" % label, "warning", message))
        if artifact["digest"]:
            rows.append(_row("artifact-%s-digest" % label, "passed", "Artifact digest is archived."))
        else:
            warnings.append("%s artifact digest is missing." % label)
            rows.append(_row("artifact-%s-digest" % label, "warning", "Artifact digest is missing."))
        if artifact["retention_days"] or artifact["expires_at"]:
            rows.append(_row("artifact-%s-retention" % label, "passed", "Artifact retention metadata is archived."))
        else:
            warnings.append("%s artifact retention metadata is missing." % label)
            rows.append(_row("artifact-%s-retention" % label, "warning", "Artifact retention metadata is missing."))
        retention_days = _as_int(artifact["retention_days"])
        if retention_days is None and artifact["retention_days"]:
            warnings.append("%s artifact retention days are not numeric." % label)
            rows.append(_row("artifact-%s-retention-days" % label, "warning", "Artifact retention days are not numeric."))
        elif retention_days is not None and retention_days < minimum_retention_days:
            message = "%s artifact retention days %s are below required minimum %s." % (
                label,
                retention_days,
                minimum_retention_days,
            )
            blockers.append(message)
            rows.append(_row("artifact-%s-retention-days" % label, "failed", message))
        elif retention_days is not None:
            rows.append(_row("artifact-%s-retention-days" % label, "passed", "Artifact retention days meet policy."))


def _artifact_by_label(artifacts, label):
    return next((artifact for artifact in artifacts if artifact.get("label") == label), {})


def _match_check(rows, blockers, warnings, check_name, left, right, field, required=True):
    left_value = str(left.get(field) or "")
    right_value = str(right.get(field) or "")
    if left_value and right_value and left_value == right_value:
        rows.append(_row(check_name, "passed", "Artifact %s matches." % field))
    elif left_value and right_value:
        message = "%s mismatch: %s does not match %s." % (check_name, left_value, right_value)
        blockers.append(message)
        rows.append(_row(check_name, "failed", message))
    elif required:
        message = "%s cannot be verified because artifact %s is missing." % (check_name, field)
        blockers.append(message)
        rows.append(_row(check_name, "failed", message))
    else:
        message = "%s is incomplete because artifact %s is missing." % (check_name, field)
        warnings.append(message)
        rows.append(_row(check_name, "warning", message))


def _review_artifact_chain(rows, blockers, warnings, artifacts, strict):
    primary = _artifact_by_label(artifacts, "primary-release-evidence")
    retained = _artifact_by_label(artifacts, "retained-primary-release-evidence")
    sidecar_primary = _artifact_by_label(artifacts, "sidecar-primary-reference")
    replay_primary = _artifact_by_label(artifacts, "replay-primary-reference")
    indexed_primary = _artifact_by_label(artifacts, "indexed-primary-reference")
    sidecar = _artifact_by_label(artifacts, "metadata-sidecar")
    replay_sidecar = _artifact_by_label(artifacts, "replay-sidecar-reference")
    indexed_sidecar = _artifact_by_label(artifacts, "indexed-sidecar-reference")
    for label, artifact in [
        ("retention", retained),
        ("sidecar", sidecar_primary),
        ("replay", replay_primary),
        ("index", indexed_primary),
    ]:
        _match_check(rows, blockers, warnings, "primary-id-%s-match" % label, primary, artifact, "id", required=strict)
        _match_check(rows, blockers, warnings, "primary-url-%s-match" % label, primary, artifact, "artifact_url", required=strict)
        _match_check(rows, blockers, warnings, "primary-digest-%s-match" % label, primary, artifact, "digest", required=False)
    for label, artifact in [
        ("replay", replay_sidecar),
        ("index", indexed_sidecar),
    ]:
        _match_check(rows, blockers, warnings, "sidecar-id-%s-match" % label, sidecar, artifact, "id", required=strict)
        _match_check(rows, blockers, warnings, "sidecar-url-%s-match" % label, sidecar, artifact, "artifact_url", required=strict)
        _match_check(rows, blockers, warnings, "sidecar-digest-%s-match" % label, sidecar, artifact, "digest", required=False)


def _review_retention_policy(rows, blockers, warnings, retention, minimum_retention_days, strict):
    for key, label in [
        ("ci_artifact_retention_days", "CI artifact retention"),
        ("release_evidence_retention_days", "Release evidence retention"),
        ("certification_evidence_retention_days", "Certification evidence retention"),
    ]:
        value = retention.get(key)
        days = _as_int(value)
        if days is None and value:
            warnings.append("%s days are not numeric." % label)
            rows.append(_row("retention-policy-%s" % key.replace("_", "-"), "warning", "%s days are not numeric." % label))
        elif days is None:
            message = "%s days are missing." % label
            if strict:
                blockers.append(message)
                rows.append(_row("retention-policy-%s" % key.replace("_", "-"), "failed", message))
            else:
                warnings.append(message)
                rows.append(_row("retention-policy-%s" % key.replace("_", "-"), "warning", message))
        elif days < minimum_retention_days:
            message = "%s days %s are below required minimum %s." % (label, days, minimum_retention_days)
            blockers.append(message)
            rows.append(_row("retention-policy-%s" % key.replace("_", "-"), "failed", message))
        else:
            rows.append(_row("retention-policy-%s" % key.replace("_", "-"), "passed", "%s days meet policy." % label))


def _archive_index(context, closure, retention, artifacts, components, blockers, warnings):
    artifact_rows = [
        "| Label | ID | URL | Digest | Retention | Expires |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for artifact in artifacts:
        artifact_rows.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                artifact["label"],
                artifact["id"] or "missing",
                artifact["artifact_url"] or "missing",
                artifact["digest"] or "missing",
                artifact["retention_days"] or "missing",
                artifact["expires_at"] or "missing",
            )
        )
    component_lines = []
    for component in components:
        component_lines.append(
            "- `%s`: %s, decision=%s/%s, source=`%s`"
            % (
                component["name"],
                component["status"],
                component["decision"] or "unknown",
                component["ci_status"] or "unknown",
                component["path"],
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Evidence Archive

- Status: {context["decision"]}
- Archive ID: `{context["archive_id"]}`
- Run ID: `{context["run_id"]}`
- Target environment: `{context["target_environment"]}`
- Generated: `{context["generated_at"]}`
- Closure decision: `{closure["closure_decision"] or "unknown"}`
- Closure result verification: `{closure["closure_result_decision"] or "unknown"}` / `{closure["closure_result_ci_status"] or "unknown"}`
- Artifact retention policy: `{retention["artifact_retention_policy_ref"] or "missing"}`
- Release evidence retention days: `{retention["release_evidence_retention_days"] or "missing"}`

## Uploaded Artifacts

{chr(10).join(artifact_rows)}

## Archive Components

{chr(10).join(component_lines)}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}
"""


def _summary(context, closure, artifacts, blockers, warnings):
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Archive Manifest

- Status: {context["decision"]}
- Archive ID: {context["archive_id"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Closure decision: {closure["closure_decision"] or "unknown"}
- Closure result closure decision: {closure["closure_result_closure_decision"] or "unknown"}
- Minimum retention days: {context["minimum_retention_days"]}
- Archived artifacts: {len(artifacts)}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Archive manifest: protected-release-archive-manifest.json
- Archive index: archive-index.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context, closure, artifacts):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "archive_id=%s" % context["archive_id"],
            "target_environment=%s" % context["target_environment"],
            "closure_decision=%s" % (closure["closure_decision"] or "<missing>"),
            "closure_result_closure_decision=%s" % (closure["closure_result_closure_decision"] or "<missing>"),
            "closure_result_decision=%s" % (closure["closure_result_decision"] or "<missing>"),
            "artifact_count=%s" % len(artifacts),
            "minimum_retention_days=%s" % context["minimum_retention_days"],
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Export protected release long-term archive manifest.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_OUTPUT", ""))
    parser.add_argument(
        "--required-components",
        default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_REQUIRED_COMPONENTS", ",".join(DEFAULT_REQUIRED_COMPONENTS)),
    )
    parser.add_argument("--required-component", action="append", default=[])
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--minimum-retention-days",
        default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_MIN_RETENTION_DAYS", "30"),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_ARCHIVE_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_ARCHIVE_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict
    minimum_retention_days = _as_int(args.minimum_retention_days) or 0

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-release-archive" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    try:
        overrides = _component_overrides(args.component)
        rows.append(_row("component-overrides", "passed", "%s override(s) parsed." % len(overrides)))
    except ValueError as error:
        overrides = {}
        blockers.append(str(error))
        rows.append(_row("component-overrides", "failed", str(error)))
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

    required_components = _dedupe(_csv_items(args.required_components) + args.required_component)
    components = []
    for name in required_components:
        component = _component_review(name, _component_path(name, args.run_id, overrides), required=True)
        components.append(component)
        rows.append(_row("component-%s" % name, component["status"], component["message"], component["path"]))
        blockers.extend(component["blockers"])
        warnings.extend(component["warnings"])

    by_name = {component["name"]: component for component in components}
    artifacts = _collect_artifacts(by_name)
    closure = _closure_summary(by_name)
    retention = _retention_summary(by_name)
    if closure["closure_decision"] not in VALID_CLOSURE_DECISIONS:
        blockers.append("Closure decision is missing or invalid for archive: %s" % (closure["closure_decision"] or "empty"))
        rows.append(_row("closure-decision", "failed", "Closure decision is missing or invalid."))
    else:
        rows.append(_row("closure-decision", "passed", "Closure decision is archived: %s." % closure["closure_decision"]))
    if closure["closure_result_closure_decision"] not in VALID_CLOSURE_DECISIONS:
        blockers.append(
            "Closure result verifier did not archive a valid release closure decision: %s"
            % (closure["closure_result_closure_decision"] or "empty")
        )
        rows.append(_row("closure-result-decision", "failed", "Closure result closure decision is missing or invalid."))
    elif closure["closure_decision"] != closure["closure_result_closure_decision"]:
        message = "Closure gate decision %s does not match closure result verifier decision %s." % (
            closure["closure_decision"] or "empty",
            closure["closure_result_closure_decision"],
        )
        blockers.append(message)
        rows.append(_row("closure-result-decision-match", "failed", message))
    else:
        rows.append(_row("closure-result-decision-match", "passed", "Closure gate and result verifier decisions match."))
    if closure["closure_result_decision"] not in {"passed", "warning"}:
        blockers.append("Closure result verification is not archived as passed/warning.")
        rows.append(_row("closure-result-verification", "failed", "Closure result verification is not passed/warning."))
    else:
        rows.append(_row("closure-result-verification", "passed", "Closure result verification is archived."))
    for pointer_key in ["closure_decision_file", "promotion_checklist", "evidence_index"]:
        if closure.get(pointer_key):
            rows.append(_row("closure-pointer-%s" % pointer_key.replace("_", "-"), "passed", "Closure pointer is archived.", closure[pointer_key]))
        else:
            message = "Closure pointer is missing from archive: %s" % pointer_key
            blockers.append(message)
            rows.append(_row("closure-pointer-%s" % pointer_key.replace("_", "-"), "failed", message))
    _review_retention_policy(rows, blockers, warnings, retention, minimum_retention_days, strict)
    _review_artifacts(rows, blockers, warnings, strict, artifacts, minimum_retention_days)
    _review_artifact_chain(rows, blockers, warnings, artifacts, strict)

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    if args.fail_on_warning and warnings:
        blockers.extend("Warning treated as blocker: %s" % warning for warning in warnings)
        blockers = _dedupe(blockers)
    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"
    if not strict and blockers and all("missing" in blocker.lower() for blocker in blockers):
        warnings.extend(blockers)
        blockers = []
        decision = "warning"
        ci_status = "pass_with_warnings"

    context = {
        "run_id": args.run_id,
        "archive_id": "tijara-protected-archive-%s" % args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "required_components": required_components,
        "minimum_retention_days": minimum_retention_days,
        "fail_on_warning": bool(args.fail_on_warning),
        "strict": strict,
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "closure": closure,
        "retention": retention,
        "artifacts": artifacts,
        "components": [{key: value for key, value in component.items() if key != "payload"} for component in components],
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-release-archive-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "archive-index.md", _archive_index(context, closure, retention, artifacts, components, blockers, warnings))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, closure, artifacts))
    _write(output / "summary.md", _summary(context, closure, artifacts, blockers, warnings))
    print("Protected release archive manifest written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
