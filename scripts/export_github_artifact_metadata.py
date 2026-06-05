#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
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


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _read_artifacts_json(path):
    if not path:
        return {}, []
    artifact_path = Path(path)
    if not artifact_path.is_absolute():
        artifact_path = ROOT_DIR / artifact_path
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    if isinstance(payload, dict):
        artifacts = payload.get("artifacts")
        if isinstance(artifacts, list):
            return payload, artifacts
        if payload.get("name"):
            return payload, [payload]
    if isinstance(payload, list):
        return {"artifacts": payload}, payload
    return payload if isinstance(payload, dict) else {}, []


def _find_artifact(artifacts, artifact_name):
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("name") or "") == artifact_name:
            return artifact
    return {}


def _retention_expires_at(created_at, retention_days):
    if not created_at or not retention_days:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return (parsed + dt.timedelta(days=int(retention_days))).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return ""


def _artifact_download_url(repository, artifact_id):
    if repository and artifact_id:
        return "https://github.com/%s/actions/runs/artifacts/%s" % (repository, artifact_id)
    return ""


def _summary(context, rows, artifact, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# GitHub Artifact Metadata

- Status: {decision}
- Stage: {context["stage"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Artifact name: {artifact["name"] or "<unset>"}
- Artifact ID: {artifact["id"] or "<pending>"}
- Artifact URL: {artifact["artifact_url"] or "<pending>"}
- Workflow run URL: {context["workflow_run_url"] or "<unset>"}
- Retention days: {artifact["retention_days"] or "<unset>"}
- Expires at: {artifact["expires_at"] or "<pending>"}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Artifact metadata manifest: github-artifact-metadata.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export GitHub Actions artifact metadata for protected release evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_GITHUB_ARTIFACT_METADATA_OUTPUT", ""))
    parser.add_argument("--stage", default=os.environ.get("TIJARA_GITHUB_ARTIFACT_METADATA_STAGE", "pre_upload"))
    parser.add_argument("--artifact-name", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_NAME", ""))
    parser.add_argument("--artifact-id", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_ID", ""))
    parser.add_argument("--artifact-url", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_URL", ""))
    parser.add_argument("--artifact-digest", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_DIGEST", ""))
    parser.add_argument("--artifact-reference", action="append", default=[])
    parser.add_argument("--artifacts-json", default=os.environ.get("TIJARA_GITHUB_ARTIFACTS_JSON", ""))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--github-run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--github-run-number", default=os.environ.get("GITHUB_RUN_NUMBER", ""))
    parser.add_argument("--github-run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    parser.add_argument("--workflow-run-url", default=os.environ.get("GITHUB_RUN_URL", ""))
    parser.add_argument("--retention-days", default=os.environ.get("TIJARA_GITHUB_ARTIFACT_RETENTION_DAYS", "30"))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_GITHUB_ARTIFACT_METADATA_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/github-artifact-metadata" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    stage = str(args.stage or "pre_upload").strip().lower().replace("-", "_")
    artifact_name = args.artifact_name.strip()
    artifact_references = list(args.artifact_reference)
    artifact_references.extend(_csv_items(os.environ.get("TIJARA_ARTIFACT_REFERENCES")))

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

    if not artifact_name:
        message = "Artifact name is required."
        if strict:
            blockers.append(message)
            rows.append(_row("artifact-name", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("artifact-name", "warning", message))
    else:
        rows.append(_row("artifact-name", "passed", "Artifact name is recorded."))

    raw_payload, artifacts = _read_artifacts_json(args.artifacts_json)
    matched_artifact = _find_artifact(artifacts, artifact_name) if artifact_name else {}
    if args.artifacts_json:
        if matched_artifact:
            rows.append(_row("artifacts-json", "passed", "Matched artifact in GitHub artifacts JSON."))
        else:
            message = "No matching artifact found in GitHub artifacts JSON."
            if stage == "post_upload" and strict:
                blockers.append(message)
                rows.append(_row("artifacts-json", "failed", message))
            else:
                warnings.append(message)
                rows.append(_row("artifacts-json", "warning", message))

    artifact_id = args.artifact_id or str(matched_artifact.get("id") or "")
    artifact_url = args.artifact_url or str(matched_artifact.get("artifact_url") or "")
    artifact_url = artifact_url or str(matched_artifact.get("html_url") or "")
    artifact_url = artifact_url or _artifact_download_url(args.repository, artifact_id)
    api_url = str(matched_artifact.get("url") or "")
    archive_download_url = str(matched_artifact.get("archive_download_url") or "")
    artifact_digest = args.artifact_digest or str(matched_artifact.get("digest") or "")
    size_in_bytes = matched_artifact.get("size_in_bytes", "")
    created_at = str(matched_artifact.get("created_at") or "")
    updated_at = str(matched_artifact.get("updated_at") or "")
    expires_at = str(matched_artifact.get("expires_at") or "")
    expires_at = expires_at or _retention_expires_at(created_at or _utc_now(), args.retention_days)

    if stage == "post_upload":
        if artifact_id:
            rows.append(_row("artifact-id", "passed", "Uploaded artifact ID is recorded."))
        else:
            message = "Uploaded artifact ID is missing after upload."
            if strict:
                blockers.append(message)
                rows.append(_row("artifact-id", "failed", message))
            else:
                warnings.append(message)
                rows.append(_row("artifact-id", "warning", message))
        if artifact_url:
            rows.append(_row("artifact-url", "passed", "Uploaded artifact URL is recorded."))
        else:
            message = "Uploaded artifact URL is missing after upload."
            if strict:
                blockers.append(message)
                rows.append(_row("artifact-url", "failed", message))
            else:
                warnings.append(message)
                rows.append(_row("artifact-url", "warning", message))
    else:
        rows.append(_row("artifact-upload-stage", "passed", "Pre-upload metadata placeholder recorded."))

    if args.retention_days:
        rows.append(_row("retention-days", "passed", "Retention days set to %s." % args.retention_days))
    else:
        warnings.append("Artifact retention days are unset.")
        rows.append(_row("retention-days", "warning", "Artifact retention days are unset."))

    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    workflow_run_url = args.workflow_run_url
    if not workflow_run_url and args.repository and args.github_run_id:
        workflow_run_url = "https://github.com/%s/actions/runs/%s" % (args.repository, args.github_run_id)
    generated_at = _utc_now()
    artifact = {
        "name": artifact_name,
        "id": artifact_id,
        "artifact_url": artifact_url,
        "api_url": api_url,
        "archive_download_url": archive_download_url,
        "digest": artifact_digest,
        "size_in_bytes": size_in_bytes,
        "created_at": created_at,
        "updated_at": updated_at,
        "expires_at": expires_at,
        "retention_days": args.retention_days,
        "expired": matched_artifact.get("expired", ""),
        "references": artifact_references,
    }
    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": generated_at,
        "output": str(output),
        "stage": stage,
        "workflow_run_url": workflow_run_url,
        "github": {
            "repository": args.repository,
            "run_id": args.github_run_id,
            "run_number": args.github_run_number,
            "run_attempt": args.github_run_attempt,
        },
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "artifact": artifact,
        "raw_artifact_match": matched_artifact,
        "raw_artifact_count": len(artifacts),
        "raw_payload_keys": sorted(raw_payload) if isinstance(raw_payload, dict) else [],
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "stage=%s" % stage,
            "artifact_name=%s" % (artifact_name or "<unset>"),
            "artifact_id=%s" % (artifact_id or "<pending>"),
            "artifact_url=%s" % (artifact_url or "<pending>"),
            "workflow_run_url=%s" % (workflow_run_url or "<unset>"),
            "retention_days=%s" % (args.retention_days or "<unset>"),
            "expires_at=%s" % (expires_at or "<pending>"),
            "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )

    _write(output / "github-artifact-metadata.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, artifact, decision, blockers, warnings))

    print("GitHub artifact metadata written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
