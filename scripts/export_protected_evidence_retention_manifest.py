#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_STATUSES = {"approved", "ready", "passed", "pass", "success", "ok"}
WARNING_STATUSES = {"warning", "warn", "pass_with_warnings", "skipped"}
FAILING_STATUSES = {"blocked", "failed", "fail", "error"}
DEFAULT_REQUIRED_COMPONENTS = [
    "protected-run-decision",
    "signoff-package",
    "release-readiness",
    "certification-result-matrix",
    "github-artifact-metadata",
    "protected-artifact-summary",
    "release-retention-evidence",
]
DEFAULT_COMPONENT_PATHS = {
    "protected-run-decision": "deploy/runtime/protected-run-decision/{run_id}",
    "signoff-package": "deploy/runtime/signoff-packages/{run_id}",
    "release-readiness": "deploy/runtime/signoff-packages/{run_id}/release-readiness.json",
    "certification-result-matrix": "deploy/runtime/certification-evidence/{run_id}/result-matrix/certification-result-matrix.json",
    "github-artifact-metadata": "deploy/runtime/github-artifact-metadata/{run_id}/github-artifact-metadata.json",
    "protected-artifact-summary": "deploy/runtime/protected-artifact-summary/{run_id}/protected-artifact-summary.json",
    "release-retention-evidence": "deploy/runtime/release-retention-evidence/{run_id}/release-retention-evidence.json",
}
PREFERRED_DECISION_JSON = {
    "protected-run-decision": "protected-run-decision.json",
    "signoff-package": "release-readiness.json",
    "release-readiness": "release-readiness.json",
    "certification-result-matrix": "certification-result-matrix.json",
    "github-artifact-metadata": "github-artifact-metadata.json",
    "protected-artifact-summary": "protected-artifact-summary.json",
    "release-retention-evidence": "release-retention-evidence.json",
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


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_hash(files):
    payload = json.dumps(files, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _decision_state(decision, ci_status):
    decision_value = str(decision or "").strip().lower()
    ci_value = str(ci_status or "").strip().lower()
    if decision_value in FAILING_STATUSES or ci_value in FAILING_STATUSES:
        return "failed"
    if decision_value in WARNING_STATUSES or ci_value in WARNING_STATUSES:
        return "warning"
    if decision_value in PASS_STATUSES or ci_value in PASS_STATUSES:
        return "passed"
    return "missing"


def _iter_files(path):
    if path.is_file():
        yield path
    elif path.is_dir():
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file():
                yield candidate


def _fingerprint_path(path):
    files = []
    total_bytes = 0
    for file_path in _iter_files(path):
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        files.append(
            {
                "path": _repo_relative(file_path),
                "size_bytes": size,
                "sha256": _hash_file(file_path),
            }
        )
    return files, total_bytes


def _component_review(name, path, required):
    files, total_bytes = _fingerprint_path(path)
    primary_json = path if path.is_file() and path.suffix.lower() == ".json" else None
    if primary_json is None and path.is_dir():
        preferred = PREFERRED_DECISION_JSON.get(name, "")
        preferred_path = path / preferred if preferred else None
        if preferred_path and preferred_path.is_file():
            primary_json = preferred_path
        json_candidates = sorted(candidate for candidate in path.glob("*.json") if candidate.is_file())
        if primary_json is None:
            for candidate in json_candidates:
                payload, read_status = _read_json(candidate)
                if read_status == "ok" and any(key in payload for key in ("decision", "status", "ci_status")):
                    primary_json = candidate
                    break
        if primary_json is None:
            primary_json = json_candidates[0] if json_candidates else None
    payload, read_status = _read_json(primary_json) if primary_json else ({}, "missing")
    decision, ci_status = _decision_fields(payload)
    state = _decision_state(decision, ci_status)
    blockers = []
    warnings = []

    if not path.exists():
        if required:
            blockers.append("%s evidence path is missing." % name)
            status = "failed"
            message = "Required retention evidence path is missing."
        else:
            status = "skipped"
            message = "Optional retention evidence path is not attached."
    elif not files:
        if required:
            blockers.append("%s evidence path contains no files." % name)
            status = "failed"
            message = "Required retention evidence path contains no files."
        else:
            warnings.append("%s evidence path contains no files." % name)
            status = "warning"
            message = "Optional retention evidence path contains no files."
    elif read_status.startswith("read_error:"):
        blockers.append("%s primary JSON could not be read." % name)
        status = "failed"
        message = read_status
    elif primary_json and state == "failed":
        blockers.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        status = "failed"
        message = "Primary JSON decision is failing."
    elif primary_json and state == "warning":
        warnings.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        status = "warning"
        message = "Primary JSON decision has warnings."
    elif primary_json and state == "passed":
        status = "passed"
        message = "Retention evidence is fingerprinted and passing."
    elif required:
        warnings.append("%s has no primary decision JSON." % name)
        status = "warning"
        message = "Evidence fingerprinted; no primary decision JSON found."
    else:
        status = "passed"
        message = "Optional evidence is fingerprinted."

    blockers.extend("%s: %s" % (name, item) for item in payload.get("blockers") or [])
    warnings.extend("%s: %s" % (name, item) for item in payload.get("warnings") or [])
    return {
        "name": name,
        "path": _repo_relative(path),
        "required": bool(required),
        "exists": path.exists(),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "manifest_sha256": _manifest_hash(files) if files else "",
        "files": files,
        "primary_json": _repo_relative(primary_json) if primary_json else "",
        "decision": decision,
        "ci_status": ci_status,
        "state": state,
        "status": status,
        "message": message,
        "blockers": blockers,
        "warnings": warnings,
        "payload": payload,
    }


def _artifact_from_metadata(component):
    payload = component.get("payload") or {}
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return {
        "name": artifact.get("name", ""),
        "id": artifact.get("id", ""),
        "artifact_url": artifact.get("artifact_url", ""),
        "api_url": artifact.get("api_url", ""),
        "archive_download_url": artifact.get("archive_download_url", ""),
        "digest": artifact.get("digest", ""),
        "retention_days": artifact.get("retention_days", ""),
        "expires_at": artifact.get("expires_at", ""),
        "references": artifact.get("references") or [],
        "workflow_run_url": context.get("workflow_run_url", ""),
        "stage": context.get("stage", ""),
    }


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    lines.extend(
        "%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source") or "")
        for row in rows
    )
    return "\n".join(lines)


def _summary(context, components, artifact, blockers, warnings):
    component_lines = []
    for component in components:
        component_lines.append(
            "- `%s`: %s, required=%s, files=%s, sha256=%s"
            % (
                component["name"],
                component["status"],
                "yes" if component["required"] else "no",
                component["file_count"],
                component["manifest_sha256"] or "missing",
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Evidence Retention Manifest

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Uploaded artifact: {artifact["name"] or "<unset>"}
- Uploaded artifact ID: {artifact["id"] or "<unset>"}
- Uploaded artifact URL: {artifact["artifact_url"] or "<unset>"}
- Uploaded artifact digest: {artifact["digest"] or "<unset>"}

## Components

{chr(10).join(component_lines) or "- No retention components were evaluated."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Protected evidence retention manifest: protected-evidence-retention-manifest.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context, artifact):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "output=%s" % context["output"],
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
            "required_components=%s" % ",".join(context["required_components"]),
            "optional_components=%s" % (",".join(context["optional_components"]) or "<none>"),
            "fail_on_warning=%s" % int(context["fail_on_warning"]),
            "strict=%s" % int(context["strict"]),
            "artifact_name=%s" % (artifact["name"] or "<unset>"),
            "artifact_id=%s" % (artifact["id"] or "<unset>"),
            "artifact_url=%s" % (artifact["artifact_url"] or "<unset>"),
            "artifact_digest=%s" % (artifact["digest"] or "<unset>"),
            "artifact_retention_days=%s" % (artifact["retention_days"] or "<unset>"),
            "artifact_expires_at=%s" % (artifact["expires_at"] or "<unset>"),
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Export protected evidence retention manifest.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_RETENTION_OUTPUT", ""))
    parser.add_argument("--required-component", action="append", default=[])
    parser.add_argument(
        "--required-components",
        default=os.environ.get(
            "TIJARA_PROTECTED_EVIDENCE_RETENTION_REQUIRED_COMPONENTS",
            ",".join(DEFAULT_REQUIRED_COMPONENTS),
        ),
    )
    parser.add_argument("--optional-component", action="append", default=[])
    parser.add_argument(
        "--optional-components",
        default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_RETENTION_OPTIONAL_COMPONENTS", ""),
    )
    parser.add_argument("--component", action="append", default=[], help="Override component path as name=path.")
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_EVIDENCE_RETENTION_FAIL_ON_WARNING", "1")),
    )
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_EVIDENCE_RETENTION_NON_STRICT", "0")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-evidence-retention" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    blockers = []
    warnings = []
    rows = []
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

    artifact_component = next((item for item in components if item["name"] == "github-artifact-metadata"), {})
    artifact = _artifact_from_metadata(artifact_component)
    if not artifact.get("id"):
        message = "Uploaded artifact ID is missing from GitHub artifact metadata."
        if strict:
            blockers.append(message)
            rows.append(_row("uploaded-artifact-id", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("uploaded-artifact-id", "warning", message))
    else:
        rows.append(_row("uploaded-artifact-id", "passed", "Uploaded artifact ID is retained."))
    if not artifact.get("artifact_url"):
        message = "Uploaded artifact URL is missing from GitHub artifact metadata."
        if strict:
            blockers.append(message)
            rows.append(_row("uploaded-artifact-url", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("uploaded-artifact-url", "warning", message))
    else:
        rows.append(_row("uploaded-artifact-url", "passed", "Uploaded artifact URL is retained."))
    if not artifact.get("digest"):
        warnings.append("Uploaded artifact digest is not retained by GitHub metadata.")
        rows.append(_row("uploaded-artifact-digest", "warning", "Uploaded artifact digest is unset."))
    else:
        rows.append(_row("uploaded-artifact-digest", "passed", "Uploaded artifact digest is retained."))

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
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "components": [{key: value for key, value in component.items() if key != "payload"} for component in components],
        "uploaded_artifact": artifact,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-evidence-retention-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, artifact))
    _write(output / "summary.md", _summary(context, components, artifact, blockers, warnings))
    print("Protected evidence retention manifest written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
