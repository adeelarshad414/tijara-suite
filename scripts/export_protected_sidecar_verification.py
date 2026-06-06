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
DEFAULT_EXPECTED_FILES = [
    "github-artifact-metadata.json",
    "protected-evidence-retention-manifest.json",
]
DEFAULT_SIDECAR_PATHS = [
    "deploy/runtime/github-artifact-metadata/{run_id}",
    "deploy/runtime/protected-evidence-retention/{run_id}",
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


def _path_files(path):
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    return []


def _sidecar_path_review(raw_path, run_id):
    path = _resolve(str(raw_path).format(run_id=run_id))
    files = _path_files(path)
    return {
        "path": _repo_relative(path),
        "exists": path.exists(),
        "file_count": len(files),
        "files": [_repo_relative(file_path) for file_path in files],
    }


def _artifact_from_metadata(payload):
    artifact = payload.get("artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _uploaded_artifact_from_retention(payload):
    artifact = payload.get("uploaded_artifact") if isinstance(payload, dict) else {}
    return artifact if isinstance(artifact, dict) else {}


def _retention_component_statuses(payload):
    statuses = []
    for component in payload.get("components") or []:
        if not isinstance(component, dict):
            continue
        statuses.append(
            {
                "name": str(component.get("name") or ""),
                "status": str(component.get("status") or ""),
                "message": str(component.get("message") or ""),
                "required": bool(component.get("required")),
                "path": str(component.get("path") or ""),
            }
        )
    return statuses


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _add_presence_check(rows, blockers, warnings, strict, name, value, label):
    if str(value or "").strip():
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is missing." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _summary(context, sidecar_artifact, primary_artifact, path_reviews, blockers, warnings):
    path_lines = []
    for review in path_reviews:
        path_lines.append(
            "- `%s`: exists=%s, files=%s"
            % (review["path"], "yes" if review["exists"] else "no", review["file_count"])
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Sidecar Upload Verification

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Sidecar artifact: {sidecar_artifact["name"] or "<unset>"}
- Sidecar artifact ID: {sidecar_artifact["id"] or "<missing>"}
- Sidecar artifact URL: {sidecar_artifact["artifact_url"] or "<missing>"}
- Sidecar digest: {sidecar_artifact["digest"] or "<missing>"}
- Sidecar retention days: {sidecar_artifact["retention_days"] or "<unset>"}
- Primary release artifact: {primary_artifact.get("name") or "<unset>"}

## Sidecar Paths

{chr(10).join(path_lines) or "- No sidecar paths were reviewed."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Sidecar verification manifest: protected-sidecar-verification.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context, sidecar_artifact):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "sidecar_artifact_name=%s" % (sidecar_artifact["name"] or "<unset>"),
            "sidecar_artifact_id=%s" % (sidecar_artifact["id"] or "<missing>"),
            "sidecar_artifact_url=%s" % (sidecar_artifact["artifact_url"] or "<missing>"),
            "sidecar_artifact_digest=%s" % (sidecar_artifact["digest"] or "<missing>"),
            "sidecar_retention_days=%s" % (sidecar_artifact["retention_days"] or "<unset>"),
            "minimum_retention_days=%s" % context["minimum_retention_days"],
            "expected_files=%s" % ",".join(context["expected_files"]),
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Verify protected sidecar artifact upload metadata.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_SIDECAR_VERIFICATION_OUTPUT", ""))
    parser.add_argument(
        "--artifact-metadata",
        default=os.environ.get("TIJARA_PROTECTED_SIDECAR_ARTIFACT_METADATA", ""),
    )
    parser.add_argument(
        "--retention-manifest",
        default=os.environ.get("TIJARA_PROTECTED_SIDECAR_RETENTION_MANIFEST", ""),
    )
    parser.add_argument("--sidecar-artifact-name", default=os.environ.get("TIJARA_SIDECAR_ARTIFACT_NAME", ""))
    parser.add_argument("--sidecar-artifact-id", default=os.environ.get("TIJARA_SIDECAR_ARTIFACT_ID", ""))
    parser.add_argument("--sidecar-artifact-url", default=os.environ.get("TIJARA_SIDECAR_ARTIFACT_URL", ""))
    parser.add_argument("--sidecar-artifact-digest", default=os.environ.get("TIJARA_SIDECAR_ARTIFACT_DIGEST", ""))
    parser.add_argument(
        "--sidecar-retention-days",
        default=os.environ.get("TIJARA_SIDECAR_RETENTION_DAYS", os.environ.get("TIJARA_GITHUB_ARTIFACT_RETENTION_DAYS", "30")),
    )
    parser.add_argument(
        "--minimum-retention-days",
        default=os.environ.get("TIJARA_PROTECTED_SIDECAR_MIN_RETENTION_DAYS", "30"),
    )
    parser.add_argument(
        "--expected-files",
        default=os.environ.get("TIJARA_PROTECTED_SIDECAR_EXPECTED_FILES", ",".join(DEFAULT_EXPECTED_FILES)),
    )
    parser.add_argument("--expected-file", action="append", default=[])
    parser.add_argument("--sidecar-path", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_SIDECAR_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_SIDECAR_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-sidecar-verification" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    artifact_metadata_path = args.artifact_metadata or "deploy/runtime/github-artifact-metadata/%s/github-artifact-metadata.json" % args.run_id
    retention_manifest_path = (
        args.retention_manifest
        or "deploy/runtime/protected-evidence-retention/%s/protected-evidence-retention-manifest.json" % args.run_id
    )
    expected_files = _dedupe(_csv_items(args.expected_files) + args.expected_file)
    sidecar_paths = args.sidecar_path or list(DEFAULT_SIDECAR_PATHS)
    path_reviews = [_sidecar_path_review(path, args.run_id) for path in sidecar_paths]

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

    artifact_metadata, artifact_metadata_target, artifact_metadata_status = _read_json(artifact_metadata_path)
    retention_manifest, retention_manifest_target, retention_manifest_status = _read_json(retention_manifest_path)

    for label, target, status in [
        ("github-artifact-metadata", artifact_metadata_target, artifact_metadata_status),
        ("protected-evidence-retention", retention_manifest_target, retention_manifest_status),
    ]:
        if status == "ok":
            rows.append(_row(label, "passed", "Evidence JSON is readable.", _repo_relative(target)))
        else:
            message = "%s evidence JSON is %s." % (label, status)
            if strict:
                blockers.append(message)
                rows.append(_row(label, "failed", message, _repo_relative(target)))
            else:
                warnings.append(message)
                rows.append(_row(label, "warning", message, _repo_relative(target)))

    for label, payload in [
        ("github-artifact-metadata", artifact_metadata),
        ("protected-evidence-retention", retention_manifest),
    ]:
        if not payload:
            continue
        state, decision, ci_status = _decision_state(payload)
        if state == "passed":
            rows.append(_row("%s-decision" % label, "passed", "Decision is %s/%s." % (decision, ci_status)))
        elif state == "warning":
            message = "%s decision is %s/%s." % (label, decision or "unknown", ci_status or "unknown")
            warnings.append(message)
            rows.append(_row("%s-decision" % label, "warning", message))
        elif state == "failed":
            message = "%s decision is %s/%s." % (label, decision or "unknown", ci_status or "unknown")
            blockers.append(message)
            rows.append(_row("%s-decision" % label, "failed", message))
        else:
            message = "%s decision is missing." % label
            warnings.append(message)
            rows.append(_row("%s-decision" % label, "warning", message))

    primary_artifact = _artifact_from_metadata(artifact_metadata)
    retention_uploaded_artifact = _uploaded_artifact_from_retention(retention_manifest)
    sidecar_artifact = {
        "name": str(args.sidecar_artifact_name or "").strip(),
        "id": str(args.sidecar_artifact_id or "").strip(),
        "artifact_url": str(args.sidecar_artifact_url or "").strip(),
        "digest": str(args.sidecar_artifact_digest or "").strip(),
        "retention_days": str(args.sidecar_retention_days or "").strip(),
    }

    _add_presence_check(rows, blockers, warnings, strict, "sidecar-artifact-name", sidecar_artifact["name"], "Sidecar artifact name")
    _add_presence_check(rows, blockers, warnings, strict, "sidecar-artifact-id", sidecar_artifact["id"], "Sidecar artifact ID")
    _add_presence_check(rows, blockers, warnings, strict, "sidecar-artifact-url", sidecar_artifact["artifact_url"], "Sidecar artifact URL")
    if sidecar_artifact["digest"]:
        rows.append(_row("sidecar-artifact-digest", "passed", "Sidecar artifact digest is recorded."))
    else:
        warnings.append("Sidecar artifact digest is missing.")
        rows.append(_row("sidecar-artifact-digest", "warning", "Sidecar artifact digest is missing."))

    retention_days = _as_int(sidecar_artifact["retention_days"])
    minimum_retention_days = _as_int(args.minimum_retention_days) or 0
    if retention_days is None:
        warnings.append("Sidecar retention days are not numeric.")
        rows.append(_row("sidecar-retention-days", "warning", "Sidecar retention days are not numeric."))
    elif retention_days < minimum_retention_days:
        message = "Sidecar retention days %s are below required minimum %s." % (retention_days, minimum_retention_days)
        blockers.append(message)
        rows.append(_row("sidecar-retention-days", "failed", message))
    else:
        rows.append(_row("sidecar-retention-days", "passed", "Sidecar retention days meet the minimum."))

    sidecar_files = set()
    for review in path_reviews:
        if review["exists"]:
            rows.append(_row("sidecar-path", "passed", "%s file(s) found." % review["file_count"], review["path"]))
        else:
            message = "Sidecar path is missing: %s" % review["path"]
            if strict:
                blockers.append(message)
                rows.append(_row("sidecar-path", "failed", message, review["path"]))
            else:
                warnings.append(message)
                rows.append(_row("sidecar-path", "warning", message, review["path"]))
        sidecar_files.update(Path(path).name for path in review["files"])
    missing_files = [name for name in expected_files if name not in sidecar_files]
    if missing_files:
        message = "Expected sidecar file(s) missing: %s" % ", ".join(missing_files)
        if strict:
            blockers.append(message)
            rows.append(_row("sidecar-expected-files", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("sidecar-expected-files", "warning", message))
    else:
        rows.append(_row("sidecar-expected-files", "passed", "All expected sidecar files are present."))

    for key, label in [
        ("id", "Primary artifact ID"),
        ("artifact_url", "Primary artifact URL"),
    ]:
        if primary_artifact.get(key):
            rows.append(_row("primary-%s" % key.replace("_", "-"), "passed", "%s is recorded." % label))
        else:
            message = "%s is missing from GitHub artifact metadata." % label
            blockers.append(message)
            rows.append(_row("primary-%s" % key.replace("_", "-"), "failed", message))
    if primary_artifact.get("digest"):
        rows.append(_row("primary-artifact-digest", "passed", "Primary artifact digest is recorded."))
    else:
        warnings.append("Primary artifact digest is missing from GitHub artifact metadata.")
        rows.append(_row("primary-artifact-digest", "warning", "Primary artifact digest is missing."))

    for key in ["id", "artifact_url", "digest"]:
        primary_value = str(primary_artifact.get(key) or "")
        retained_value = str(retention_uploaded_artifact.get(key) or "")
        if primary_value and retained_value and primary_value != retained_value:
            message = "Retention manifest uploaded artifact %s does not match GitHub artifact metadata." % key
            blockers.append(message)
            rows.append(_row("retention-uploaded-%s-match" % key.replace("_", "-"), "failed", message))
        elif primary_value and retained_value:
            rows.append(_row("retention-uploaded-%s-match" % key.replace("_", "-"), "passed", "Uploaded artifact %s matches." % key))
        elif key == "digest":
            warnings.append("Retention manifest or GitHub artifact metadata is missing uploaded artifact digest.")
            rows.append(_row("retention-uploaded-digest-match", "warning", "Uploaded artifact digest match is incomplete."))

    for component in _retention_component_statuses(retention_manifest):
        status = component["status"].lower()
        if status in {"failed", "blocked", "error"}:
            message = "Retention component %s is %s." % (component["name"], component["status"])
            blockers.append(message)
            rows.append(_row("retention-component-%s" % component["name"], "failed", message, component["path"]))
        elif status in {"warning", "warn", "skipped"}:
            message = "Retention component %s is %s." % (component["name"], component["status"])
            warnings.append(message)
            rows.append(_row("retention-component-%s" % component["name"], "warning", message, component["path"]))

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
        "artifact_metadata": _repo_relative(artifact_metadata_target),
        "retention_manifest": _repo_relative(retention_manifest_target),
        "sidecar_paths": [review["path"] for review in path_reviews],
        "expected_files": expected_files,
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
        "sidecar_artifact": sidecar_artifact,
        "primary_artifact": primary_artifact,
        "retention_uploaded_artifact": retention_uploaded_artifact,
        "sidecar_paths": path_reviews,
        "retention_components": _retention_component_statuses(retention_manifest),
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-sidecar-verification.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, sidecar_artifact))
    _write(output / "summary.md", _summary(context, sidecar_artifact, primary_artifact, path_reviews, blockers, warnings))
    print("Protected sidecar verification written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
