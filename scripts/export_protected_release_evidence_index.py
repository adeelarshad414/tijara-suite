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
    "protected-evidence-retention",
    "protected-sidecar-verification",
    "protected-evidence-replay",
    "signoff-package",
    "certification-result-matrix",
    "github-artifact-metadata",
]
DEFAULT_OPTIONAL_COMPONENTS = [
    "protected-artifact-summary",
    "release-retention-evidence",
]
DEFAULT_COMPONENT_PATHS = {
    "release-readiness": "deploy/runtime/signoff-packages/{run_id}/release-readiness.json",
    "protected-run-decision": "deploy/runtime/protected-run-decision/{run_id}/protected-run-decision.json",
    "protected-evidence-retention": "deploy/runtime/protected-evidence-retention/{run_id}/protected-evidence-retention-manifest.json",
    "protected-sidecar-verification": "deploy/runtime/protected-sidecar-verification/{run_id}/protected-sidecar-verification.json",
    "protected-evidence-replay": "deploy/runtime/protected-evidence-replay/{run_id}/protected-evidence-replay-report.json",
    "signoff-package": "deploy/runtime/signoff-packages/{run_id}",
    "certification-result-matrix": "deploy/runtime/certification-evidence/{run_id}/result-matrix/certification-result-matrix.json",
    "github-artifact-metadata": "deploy/runtime/github-artifact-metadata/{run_id}/github-artifact-metadata.json",
    "protected-artifact-summary": "deploy/runtime/protected-artifact-summary/{run_id}/protected-artifact-summary.json",
    "release-retention-evidence": "deploy/runtime/release-retention-evidence/{run_id}/release-retention-evidence.json",
}
PREFERRED_DECISION_JSON = {
    "release-readiness": "release-readiness.json",
    "protected-run-decision": "protected-run-decision.json",
    "protected-evidence-retention": "protected-evidence-retention-manifest.json",
    "protected-sidecar-verification": "protected-sidecar-verification.json",
    "protected-evidence-replay": "protected-evidence-replay-report.json",
    "signoff-package": "release-readiness.json",
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
    if not path or not path.is_file():
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


def _iter_files(path):
    if path.is_file():
        yield path
    elif path.is_dir():
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file():
                yield candidate


def _primary_json(name, path):
    if path.is_file() and path.suffix.lower() == ".json":
        return path
    if not path.is_dir():
        return None
    preferred = PREFERRED_DECISION_JSON.get(name, "")
    preferred_path = path / preferred if preferred else None
    if preferred_path and preferred_path.is_file():
        return preferred_path
    json_candidates = sorted(candidate for candidate in path.glob("*.json") if candidate.is_file())
    for candidate in json_candidates:
        payload, read_status = _read_json(candidate)
        if read_status == "ok" and any(key in payload for key in ("decision", "status", "ci_status")):
            return candidate
    return json_candidates[0] if json_candidates else None


def _component_review(name, path, required):
    files = list(_iter_files(path))
    total_bytes = 0
    for file_path in files:
        try:
            total_bytes += file_path.stat().st_size
        except OSError:
            pass
    primary_json = _primary_json(name, path)
    payload, read_status = _read_json(primary_json)
    state, decision, ci_status = _decision_state(payload)
    blockers = []
    warnings = []
    if not path.exists():
        if required:
            blockers.append("%s evidence path is missing." % name)
            status = "failed"
            message = "Required evidence path is missing."
        else:
            status = "skipped"
            message = "Optional evidence path is missing."
    elif not files:
        if required:
            blockers.append("%s evidence path contains no files." % name)
            status = "failed"
            message = "Required evidence path contains no files."
        else:
            warnings.append("%s evidence path contains no files." % name)
            status = "warning"
            message = "Optional evidence path contains no files."
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
        message = "Primary JSON decision is passing."
    elif primary_json:
        warnings.append("%s decision is missing." % name)
        status = "warning"
        message = "Primary JSON decision is missing."
    elif required:
        blockers.append("%s primary JSON is missing." % name)
        status = "failed"
        message = "Required primary JSON is missing."
    else:
        warnings.append("%s primary JSON is missing." % name)
        status = "warning"
        message = "Optional primary JSON is missing."
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return {
        "name": name,
        "path": _repo_relative(path),
        "required": required,
        "exists": path.exists(),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "primary_json": _repo_relative(primary_json) if primary_json else "",
        "read_status": read_status,
        "status": status,
        "message": message,
        "decision": decision,
        "ci_status": ci_status,
        "generated_at": str(context.get("generated_at") or ""),
        "payload": payload,
        "blockers": blockers,
        "warnings": warnings,
    }


def _artifact_from_metadata(payload):
    artifact = payload.get("artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _artifact_from_retention(payload):
    artifact = payload.get("uploaded_artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _sidecar_artifact_from_verification(payload):
    artifact = payload.get("sidecar_artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _artifact_from_replay(payload, name):
    artifact = payload.get(name) if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _workflow_url(payload):
    context = payload.get("context") if isinstance(payload, dict) else {}
    if not isinstance(context, dict):
        return ""
    value = context.get("workflow_run_url") or ""
    if value:
        return str(value)
    github = context.get("github") if isinstance(context.get("github"), dict) else {}
    repository = github.get("repository")
    run_id = github.get("run_id")
    if repository and run_id:
        return "https://github.com/%s/actions/runs/%s" % (repository, run_id)
    return ""


def _artifact_links(metadata_payload, retention_payload, sidecar_payload, replay_payload):
    primary = _artifact_from_metadata(metadata_payload)
    retained_primary = _artifact_from_retention(retention_payload)
    replay_primary = _artifact_from_replay(replay_payload, "primary_artifact")
    sidecar = _sidecar_artifact_from_verification(sidecar_payload)
    replay_sidecar = _artifact_from_replay(replay_payload, "sidecar_artifact")
    workflow_url = _workflow_url(metadata_payload)
    return {
        "workflow_run_url": workflow_url,
        "primary_artifact": {
            "name": primary.get("name") or retained_primary.get("name") or replay_primary.get("name") or "",
            "id": primary.get("id") or retained_primary.get("id") or replay_primary.get("id") or "",
            "artifact_url": primary.get("artifact_url") or retained_primary.get("artifact_url") or replay_primary.get("artifact_url") or "",
            "digest": primary.get("digest") or retained_primary.get("digest") or replay_primary.get("digest") or "",
            "retention_days": primary.get("retention_days") or retained_primary.get("retention_days") or replay_primary.get("retention_days") or "",
            "expires_at": primary.get("expires_at") or retained_primary.get("expires_at") or replay_primary.get("expires_at") or "",
        },
        "sidecar_artifact": {
            "name": sidecar.get("name") or replay_sidecar.get("name") or "",
            "id": sidecar.get("id") or replay_sidecar.get("id") or "",
            "artifact_url": sidecar.get("artifact_url") or replay_sidecar.get("artifact_url") or "",
            "digest": sidecar.get("digest") or replay_sidecar.get("digest") or "",
            "retention_days": sidecar.get("retention_days") or replay_sidecar.get("retention_days") or "",
            "expires_at": sidecar.get("expires_at") or replay_sidecar.get("expires_at") or "",
        },
    }


def _add_link_checks(rows, blockers, warnings, strict, links):
    for artifact_key, label in [
        ("primary_artifact", "Primary release artifact"),
        ("sidecar_artifact", "Protected metadata sidecar artifact"),
    ]:
        artifact = links.get(artifact_key) or {}
        for field in ["id", "artifact_url"]:
            if artifact.get(field):
                rows.append(_row("%s-%s" % (artifact_key, field.replace("_", "-")), "passed", "%s %s is recorded." % (label, field)))
            else:
                message = "%s %s is missing." % (label, field)
                if strict:
                    blockers.append(message)
                    rows.append(_row("%s-%s" % (artifact_key, field.replace("_", "-")), "failed", message))
                else:
                    warnings.append(message)
                    rows.append(_row("%s-%s" % (artifact_key, field.replace("_", "-")), "warning", message))
        if artifact.get("digest"):
            rows.append(_row("%s-digest" % artifact_key, "passed", "%s digest is recorded." % label))
        else:
            warnings.append("%s digest is missing." % label)
            rows.append(_row("%s-digest" % artifact_key, "warning", "%s digest is missing." % label))
    if links.get("workflow_run_url"):
        rows.append(_row("workflow-run-url", "passed", "Workflow run URL is recorded."))
    else:
        warnings.append("Workflow run URL is missing.")
        rows.append(_row("workflow-run-url", "warning", "Workflow run URL is missing."))


def _markdown_link(label, url):
    return "[%s](%s)" % (label, url) if url else "`missing`"


def _operator_index(context, components, links, blockers, warnings):
    component_rows = [
        "| Component | Status | Decision | CI | Files | Source |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for component in components:
        component_rows.append(
            "| %s | %s | %s | %s | %s | `%s` |"
            % (
                component["name"],
                component["status"],
                component["decision"] or "unknown",
                component["ci_status"] or "unknown",
                component["file_count"],
                component["primary_json"] or component["path"],
            )
        )
    primary = links["primary_artifact"]
    sidecar = links["sidecar_artifact"]
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Evidence Index

- Status: {context["decision"]}
- Run ID: `{context["run_id"]}`
- Target environment: `{context["target_environment"]}`
- Generated: `{context["generated_at"]}`
- Workflow run: {_markdown_link("GitHub Actions run", links.get("workflow_run_url"))}
- Primary release artifact: {_markdown_link(primary.get("name") or "release evidence", primary.get("artifact_url"))}
- Protected metadata sidecar: {_markdown_link(sidecar.get("name") or "metadata sidecar", sidecar.get("artifact_url"))}

## Component Index

{chr(10).join(component_rows)}

## Operator Review

- Start with `protected-run-decision.json`.
- Review `release-readiness.json` and the sign-off package before promotion.
- Use `protected-evidence-retention-manifest.json` for retained file fingerprints.
- Use `protected-sidecar-verification.json` to confirm the metadata sidecar upload.
- Use `audit-replay.md` to replay the final evidence chain.
- Review `certification-result-matrix.json` before provider or hardware go-live.

## Blockers

{blocker_lines}

## Warnings

{warning_lines}
"""


def _summary(context, links, blockers, warnings):
    primary = links["primary_artifact"]
    sidecar = links["sidecar_artifact"]
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Evidence Index Summary

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Primary artifact ID: {primary.get("id") or "<missing>"}
- Primary artifact URL: {primary.get("artifact_url") or "<missing>"}
- Sidecar artifact ID: {sidecar.get("id") or "<missing>"}
- Sidecar artifact URL: {sidecar.get("artifact_url") or "<missing>"}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Evidence index manifest: protected-release-evidence-index.json
- Operator index: operator-index.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context, links):
    primary = links["primary_artifact"]
    sidecar = links["sidecar_artifact"]
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "workflow_run_url=%s" % (links.get("workflow_run_url") or "<missing>"),
            "primary_artifact_id=%s" % (primary.get("id") or "<missing>"),
            "primary_artifact_url=%s" % (primary.get("artifact_url") or "<missing>"),
            "sidecar_artifact_id=%s" % (sidecar.get("id") or "<missing>"),
            "sidecar_artifact_url=%s" % (sidecar.get("artifact_url") or "<missing>"),
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Export protected release evidence operator index.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_INDEX_OUTPUT", ""))
    parser.add_argument(
        "--required-components",
        default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_INDEX_REQUIRED_COMPONENTS", ",".join(DEFAULT_REQUIRED_COMPONENTS)),
    )
    parser.add_argument("--required-component", action="append", default=[])
    parser.add_argument(
        "--optional-components",
        default=os.environ.get("TIJARA_PROTECTED_EVIDENCE_INDEX_OPTIONAL_COMPONENTS", ",".join(DEFAULT_OPTIONAL_COMPONENTS)),
    )
    parser.add_argument("--optional-component", action="append", default=[])
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_EVIDENCE_INDEX_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_EVIDENCE_INDEX_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-release-evidence-index" / args.run_id
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
        rows.append(_row("component-%s" % name, component["status"], component["message"], component["primary_json"] or component["path"]))
        blockers.extend(component["blockers"])
        warnings.extend(component["warnings"])

    by_name = {component["name"]: component for component in components}
    links = _artifact_links(
        by_name.get("github-artifact-metadata", {}).get("payload", {}),
        by_name.get("protected-evidence-retention", {}).get("payload", {}),
        by_name.get("protected-sidecar-verification", {}).get("payload", {}),
        by_name.get("protected-evidence-replay", {}).get("payload", {}),
    )
    _add_link_checks(rows, blockers, warnings, strict, links)

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
        "artifact_links": links,
        "operator_review_files": {
            "run_decision": by_name.get("protected-run-decision", {}).get("primary_json", ""),
            "release_readiness": by_name.get("release-readiness", {}).get("primary_json", ""),
            "signoff_package": by_name.get("signoff-package", {}).get("path", ""),
            "retention_manifest": by_name.get("protected-evidence-retention", {}).get("primary_json", ""),
            "sidecar_verification": by_name.get("protected-sidecar-verification", {}).get("primary_json", ""),
            "evidence_replay": by_name.get("protected-evidence-replay", {}).get("primary_json", ""),
            "certification_matrix": by_name.get("certification-result-matrix", {}).get("primary_json", ""),
        },
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-release-evidence-index.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "operator-index.md", _operator_index(context, components, links, blockers, warnings))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, links))
    _write(output / "summary.md", _summary(context, links, blockers, warnings))
    print("Protected release evidence index written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
