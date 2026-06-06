#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_STATUSES = {"approved", "ready", "passed", "pass", "success", "ok"}
WARNING_STATUSES = {"warning", "warn", "pass_with_warnings", "skipped"}
FAILING_STATUSES = {"blocked", "failed", "fail", "error"}
DEFAULT_REQUIRED_COMPONENTS = [
    "release-readiness",
    "protected-run-decision",
    "github-artifact-metadata",
    "protected-evidence-retention",
    "protected-sidecar-verification",
]
DEFAULT_COMPONENT_PATHS = {
    "release-readiness": "deploy/runtime/signoff-packages/{run_id}/release-readiness.json",
    "protected-run-decision": "deploy/runtime/protected-run-decision/{run_id}/protected-run-decision.json",
    "github-artifact-metadata": "deploy/runtime/github-artifact-metadata/{run_id}/github-artifact-metadata.json",
    "protected-evidence-retention": "deploy/runtime/protected-evidence-retention/{run_id}/protected-evidence-retention-manifest.json",
    "protected-sidecar-verification": "deploy/runtime/protected-sidecar-verification/{run_id}/protected-sidecar-verification.json",
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
        raw = "deploy/runtime/%s/%s" % (name, run_id)
    return _resolve(raw.format(run_id=run_id))


def _read_json(path):
    if not path.is_file():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, "read_error:%s" % error
    return payload if isinstance(payload, dict) else {}, "ok"


def _decision_fields(payload):
    decision = str(payload.get("decision") or payload.get("status") or "").strip()
    ci_status = str(payload.get("ci_status") or "").strip()
    if not decision and ci_status:
        decision = ci_status
    return decision, ci_status


def _decision_state(payload):
    decision, ci_status = _decision_fields(payload)
    decision_value = decision.lower()
    ci_value = ci_status.lower()
    if decision_value in FAILING_STATUSES or ci_value in FAILING_STATUSES:
        return "failed", decision, ci_status
    if decision_value in WARNING_STATUSES or ci_value in WARNING_STATUSES:
        return "warning", decision, ci_status
    if decision_value in PASS_STATUSES or ci_value in PASS_STATUSES:
        return "passed", decision, ci_status
    return "missing", decision, ci_status


def _artifact_from_metadata(payload):
    artifact = payload.get("artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _uploaded_artifact_from_retention(payload):
    artifact = payload.get("uploaded_artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _sidecar_artifact_from_verification(payload):
    artifact = payload.get("sidecar_artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _primary_artifact_from_verification(payload):
    artifact = payload.get("primary_artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _component_review(name, path, required):
    payload, read_status = _read_json(path)
    state, decision, ci_status = _decision_state(payload)
    blockers = []
    warnings = []
    if read_status == "missing":
        if required:
            blockers.append("%s evidence JSON is missing." % name)
            status = "failed"
            message = "Required evidence JSON is missing."
        else:
            status = "skipped"
            message = "Optional evidence JSON is missing."
    elif read_status.startswith("read_error:"):
        blockers.append("%s evidence JSON could not be read." % name)
        status = "failed"
        message = read_status
    elif state == "failed":
        blockers.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        status = "failed"
        message = "Decision is failing."
    elif state == "warning":
        warnings.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        status = "warning"
        message = "Decision has warnings."
    elif state == "passed":
        status = "passed"
        message = "Decision is passing."
    else:
        warnings.append("%s decision is missing." % name)
        status = "warning"
        message = "Decision is missing."
    generated_at = ""
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    if context:
        generated_at = str(context.get("generated_at") or "")
    return {
        "name": name,
        "path": _repo_relative(path),
        "required": required,
        "read_status": read_status,
        "status": status,
        "message": message,
        "decision": decision,
        "ci_status": ci_status,
        "generated_at": generated_at,
        "payload": payload,
        "blockers": blockers,
        "warnings": warnings,
    }


def _match_check(rows, blockers, warnings, label, left, right, key, warn_when_missing=False):
    left_value = str(left.get(key) or "")
    right_value = str(right.get(key) or "")
    if left_value and right_value and left_value == right_value:
        rows.append(_row(label, "passed", "%s matches." % key))
        return
    if left_value and right_value:
        message = "%s mismatch: %s != %s." % (key, left_value, right_value)
        blockers.append(message)
        rows.append(_row(label, "failed", message))
        return
    message = "%s is missing on one side of replay check." % key
    if warn_when_missing:
        warnings.append(message)
        rows.append(_row(label, "warning", message))
    else:
        blockers.append(message)
        rows.append(_row(label, "failed", message))


def _summary(context, components, primary_artifact, sidecar_artifact, blockers, warnings):
    component_lines = []
    for component in components:
        component_lines.append(
            "- `%s`: %s, decision=%s, ci=%s, source=%s"
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
# Protected Evidence Replay Report

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Primary artifact ID: {primary_artifact.get("id") or "<missing>"}
- Primary artifact URL: {primary_artifact.get("artifact_url") or "<missing>"}
- Sidecar artifact ID: {sidecar_artifact.get("id") or "<missing>"}
- Sidecar artifact URL: {sidecar_artifact.get("artifact_url") or "<missing>"}

## Replay Components

{chr(10).join(component_lines) or "- No components were reviewed."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Replay manifest: protected-evidence-replay-report.json
- Replay markdown: audit-replay.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _audit_replay(context, components, primary_artifact, sidecar_artifact, chain_rows):
    lines = [
        "# Protected Evidence Audit Replay",
        "",
        "- Run ID: `%s`" % context["run_id"],
        "- Target environment: `%s`" % context["target_environment"],
        "- Replay decision: `%s`" % context["decision"],
        "- CI status: `%s`" % context["ci_status"],
        "",
        "## Decision Chain",
        "",
    ]
    for component in components:
        lines.append(
            "- `%s` -> `%s` / `%s` from `%s`"
            % (component["name"], component["decision"] or "unknown", component["ci_status"] or "unknown", component["path"])
        )
    lines.extend(
        [
            "",
            "## Upload Chain",
            "",
            "- Primary artifact: `%s`, id `%s`, digest `%s`"
            % (
                primary_artifact.get("name") or "<unset>",
                primary_artifact.get("id") or "<missing>",
                primary_artifact.get("digest") or "<missing>",
            ),
            "- Sidecar artifact: `%s`, id `%s`, digest `%s`"
            % (
                sidecar_artifact.get("name") or "<unset>",
                sidecar_artifact.get("id") or "<missing>",
                sidecar_artifact.get("digest") or "<missing>",
            ),
            "",
            "## Replay Checks",
            "",
        ]
    )
    for row in chain_rows:
        lines.append("- `%s`: %s - %s" % (row["name"], row["status"], row["message"]))
    lines.append("")
    return "\n".join(lines)


def _env_summary(context, primary_artifact, sidecar_artifact):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "primary_artifact_id=%s" % (primary_artifact.get("id") or "<missing>"),
            "primary_artifact_url=%s" % (primary_artifact.get("artifact_url") or "<missing>"),
            "sidecar_artifact_id=%s" % (sidecar_artifact.get("id") or "<missing>"),
            "sidecar_artifact_url=%s" % (sidecar_artifact.get("artifact_url") or "<missing>"),
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Export protected evidence audit replay report.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_REPLAY_OUTPUT", ""))
    parser.add_argument(
        "--required-components",
        default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_REPLAY_REQUIRED_COMPONENTS", ",".join(DEFAULT_REQUIRED_COMPONENTS)),
    )
    parser.add_argument("--required-component", action="append", default=[])
    parser.add_argument("--optional-components", default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_REPLAY_OPTIONAL_COMPONENTS", ""))
    parser.add_argument("--optional-component", action="append", default=[])
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_EVIDENCE_REPLAY_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_EVIDENCE_REPLAY_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-evidence-replay" / args.run_id
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
    optional_components = [
        item for item in _dedupe(_csv_items(args.optional_components) + args.optional_component) if item not in required_components
    ]
    component_names = _dedupe(required_components + optional_components + list(overrides))
    components = []
    for name in component_names:
        component = _component_review(
            name,
            _component_path(name, args.run_id, overrides),
            required=name in required_components,
        )
        components.append(component)
        rows.append(_row("component-%s" % name, component["status"], component["message"], component["path"]))
        blockers.extend(component["blockers"])
        warnings.extend(component["warnings"])

    by_name = {component["name"]: component for component in components}
    metadata_payload = by_name.get("github-artifact-metadata", {}).get("payload", {})
    retention_payload = by_name.get("protected-evidence-retention", {}).get("payload", {})
    sidecar_payload = by_name.get("protected-sidecar-verification", {}).get("payload", {})
    primary_artifact = _artifact_from_metadata(metadata_payload)
    retained_artifact = _uploaded_artifact_from_retention(retention_payload)
    sidecar_artifact = _sidecar_artifact_from_verification(sidecar_payload)
    sidecar_primary_artifact = _primary_artifact_from_verification(sidecar_payload)

    _match_check(rows, blockers, warnings, "primary-id-retention-match", primary_artifact, retained_artifact, "id")
    _match_check(rows, blockers, warnings, "primary-url-retention-match", primary_artifact, retained_artifact, "artifact_url")
    _match_check(rows, blockers, warnings, "primary-digest-retention-match", primary_artifact, retained_artifact, "digest", warn_when_missing=True)
    _match_check(rows, blockers, warnings, "primary-id-sidecar-match", primary_artifact, sidecar_primary_artifact, "id")
    _match_check(rows, blockers, warnings, "primary-url-sidecar-match", primary_artifact, sidecar_primary_artifact, "artifact_url")
    _match_check(rows, blockers, warnings, "primary-digest-sidecar-match", primary_artifact, sidecar_primary_artifact, "digest", warn_when_missing=True)

    for key, label in [
        ("id", "Primary artifact ID"),
        ("artifact_url", "Primary artifact URL"),
    ]:
        if primary_artifact.get(key):
            rows.append(_row("primary-%s" % key.replace("_", "-"), "passed", "%s is recorded." % label))
        else:
            message = "%s is missing." % label
            blockers.append(message)
            rows.append(_row("primary-%s" % key.replace("_", "-"), "failed", message))
    if sidecar_artifact.get("id"):
        rows.append(_row("sidecar-artifact-id", "passed", "Sidecar artifact ID is recorded."))
    else:
        message = "Sidecar artifact ID is missing."
        blockers.append(message)
        rows.append(_row("sidecar-artifact-id", "failed", message))
    if sidecar_artifact.get("artifact_url"):
        rows.append(_row("sidecar-artifact-url", "passed", "Sidecar artifact URL is recorded."))
    else:
        message = "Sidecar artifact URL is missing."
        blockers.append(message)
        rows.append(_row("sidecar-artifact-url", "failed", message))
    if not primary_artifact.get("digest"):
        warnings.append("Primary artifact digest is missing.")
        rows.append(_row("primary-artifact-digest", "warning", "Primary artifact digest is missing."))
    if not sidecar_artifact.get("digest"):
        warnings.append("Sidecar artifact digest is missing.")
        rows.append(_row("sidecar-artifact-digest", "warning", "Sidecar artifact digest is missing."))

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
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "required_components": required_components,
        "optional_components": optional_components,
        "fail_on_warning": bool(args.fail_on_warning),
        "strict": strict,
        "decision": decision,
        "ci_status": ci_status,
    }
    component_public = [{key: value for key, value in component.items() if key != "payload"} for component in components]
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "components": component_public,
        "primary_artifact": primary_artifact,
        "retained_primary_artifact": retained_artifact,
        "sidecar_primary_artifact": sidecar_primary_artifact,
        "sidecar_artifact": sidecar_artifact,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-evidence-replay-report.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "audit-replay.md", _audit_replay(context, components, primary_artifact, sidecar_artifact, rows))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, primary_artifact, sidecar_artifact))
    _write(output / "summary.md", _summary(context, components, primary_artifact, sidecar_artifact, blockers, warnings))
    print("Protected evidence replay report written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
