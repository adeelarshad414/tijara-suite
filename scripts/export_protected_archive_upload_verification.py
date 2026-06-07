#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_DECISIONS = {"passed", "pass", "ready", "approved", "success", "ok"}
WARNING_DECISIONS = {"warning", "warn", "watch", "pass_with_warnings"}
VALID_CLOSURE_DECISIONS = {"promotion_ready", "watch", "blocked"}
DEFAULT_EXPECTED_FILES = [
    "protected-closure-result-verification.json",
    "closure-result.md",
    "protected-release-archive-manifest.json",
    "archive-index.md",
]
DEFAULT_FINAL_UPLOAD_PATHS = [
    "deploy/runtime/protected-closure-result-verification/{run_id}",
    "deploy/runtime/protected-release-archive/{run_id}",
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
        lines.append("%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source") or ""))
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


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _path_files(path):
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    return []


def _path_review(raw_path, run_id):
    path = _resolve(str(raw_path).format(run_id=run_id))
    files = _path_files(path)
    return {
        "path": _repo_relative(path),
        "exists": path.exists(),
        "file_count": len(files),
        "files": [_repo_relative(file_path) for file_path in files],
    }


def _decision(payload):
    return str(payload.get("decision") or payload.get("status") or payload.get("ci_status") or "").strip()


def _ci_status(payload):
    return str(payload.get("ci_status") or "").strip()


def _source_review(rows, blockers, warnings, strict, label, path, payload, read_status):
    if read_status == "ok":
        rows.append(_row("%s-json" % label, "passed", "Evidence JSON is readable.", _repo_relative(path)))
    elif strict:
        message = "%s evidence JSON is %s." % (label, read_status)
        blockers.append(message)
        rows.append(_row("%s-json" % label, "failed", message, _repo_relative(path)))
        return
    else:
        message = "%s evidence JSON is %s." % (label, read_status)
        warnings.append(message)
        rows.append(_row("%s-json" % label, "warning", message, _repo_relative(path)))
        return

    decision = _decision(payload).lower()
    ci_status = _ci_status(payload).lower()
    if decision in PASS_DECISIONS or ci_status in PASS_DECISIONS:
        rows.append(_row("%s-decision" % label, "passed", "Decision is %s/%s." % (decision or "unknown", ci_status or "unknown")))
    elif decision in WARNING_DECISIONS or ci_status in WARNING_DECISIONS:
        message = "%s decision is %s/%s." % (label, decision or "unknown", ci_status or "unknown")
        warnings.append(message)
        rows.append(_row("%s-decision" % label, "warning", message))
    else:
        message = "%s decision is %s/%s." % (label, decision or "unknown", ci_status or "unknown")
        blockers.append(message)
        rows.append(_row("%s-decision" % label, "failed", message))


def _closure_decision_from_result(payload):
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return str(payload.get("closure_decision") or context.get("closure_decision") or "").strip()


def _closure_decision_from_archive(payload):
    closure = payload.get("closure") if isinstance(payload.get("closure"), dict) else {}
    return str(closure.get("closure_decision") or "").strip()


def _archive_result_decision(payload):
    closure = payload.get("closure") if isinstance(payload.get("closure"), dict) else {}
    return str(closure.get("closure_result_closure_decision") or "").strip()


def _summary(context, final_artifact, closure, blockers, warnings):
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Archive Upload Verification

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Final closure-result artifact name: {final_artifact["name"] or "<unset>"}
- Final closure-result artifact ID: {final_artifact["id"] or "<missing>"}
- Final closure-result artifact URL: {final_artifact["artifact_url"] or "<missing>"}
- Closure result decision: {closure["closure_result_decision"] or "unknown"}
- Archive closure decision: {closure["archive_closure_decision"] or "unknown"}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Archive upload verification: protected-archive-upload-verification.json
- Archive upload summary: archive-upload.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _archive_upload_markdown(context, final_artifact, closure, rows):
    lines = [
        "# Protected Archive Upload",
        "",
        "- Run ID: `%s`" % context["run_id"],
        "- Target environment: `%s`" % context["target_environment"],
        "- Verification decision: `%s`" % context["decision"],
        "- Final artifact: `%s`" % (final_artifact["name"] or "missing"),
        "- Final artifact ID: `%s`" % (final_artifact["id"] or "missing"),
        "- Final artifact URL: %s" % (final_artifact["artifact_url"] or "missing"),
        "- Final artifact digest: `%s`" % (final_artifact["digest"] or "missing"),
        "- Closure result decision: `%s`" % (closure["closure_result_decision"] or "missing"),
        "- Archive closure decision: `%s`" % (closure["archive_closure_decision"] or "missing"),
        "- Archive result closure decision: `%s`" % (closure["archive_result_closure_decision"] or "missing"),
        "",
        "## Verification Checks",
        "",
    ]
    for row in rows:
        lines.append("- `%s`: %s - %s" % (row["name"], row["status"], row["message"]))
    lines.append("")
    return "\n".join(lines)


def _env_summary(context, final_artifact, closure):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "closure_result_decision=%s" % (closure["closure_result_decision"] or "<missing>"),
            "archive_closure_decision=%s" % (closure["archive_closure_decision"] or "<missing>"),
            "archive_result_closure_decision=%s" % (closure["archive_result_closure_decision"] or "<missing>"),
            "final_artifact_name=%s" % (final_artifact["name"] or "<unset>"),
            "final_artifact_id=%s" % (final_artifact["id"] or "<missing>"),
            "final_artifact_url=%s" % (final_artifact["artifact_url"] or "<missing>"),
            "final_artifact_digest=%s" % (final_artifact["digest"] or "<missing>"),
            "retention_days=%s" % (final_artifact["retention_days"] or "<unset>"),
            "minimum_retention_days=%s" % context["minimum_retention_days"],
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Verify the final protected closure-result upload includes archive evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_OUTPUT", ""))
    parser.add_argument(
        "--closure-result",
        default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_CLOSURE_RESULT", ""),
    )
    parser.add_argument(
        "--release-archive",
        default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_RELEASE_ARCHIVE", ""),
    )
    parser.add_argument("--final-artifact-name", default=os.environ.get("TIJARA_ARCHIVE_UPLOAD_ARTIFACT_NAME", ""))
    parser.add_argument("--final-artifact-id", default=os.environ.get("TIJARA_ARCHIVE_UPLOAD_ARTIFACT_ID", ""))
    parser.add_argument("--final-artifact-url", default=os.environ.get("TIJARA_ARCHIVE_UPLOAD_ARTIFACT_URL", ""))
    parser.add_argument("--final-artifact-digest", default=os.environ.get("TIJARA_ARCHIVE_UPLOAD_ARTIFACT_DIGEST", ""))
    parser.add_argument(
        "--final-retention-days",
        default=os.environ.get("TIJARA_ARCHIVE_UPLOAD_RETENTION_DAYS", os.environ.get("TIJARA_GITHUB_ARTIFACT_RETENTION_DAYS", "30")),
    )
    parser.add_argument(
        "--minimum-retention-days",
        default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_MIN_RETENTION_DAYS", "30"),
    )
    parser.add_argument(
        "--expected-files",
        default=os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_EXPECTED_FILES", ",".join(DEFAULT_EXPECTED_FILES)),
    )
    parser.add_argument("--expected-file", action="append", default=[])
    parser.add_argument("--final-upload-path", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_ARCHIVE_UPLOAD_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-archive-upload-verification" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    closure_result_path = args.closure_result or "deploy/runtime/protected-closure-result-verification/%s/protected-closure-result-verification.json" % args.run_id
    release_archive_path = args.release_archive or "deploy/runtime/protected-release-archive/%s/protected-release-archive-manifest.json" % args.run_id
    closure_result, closure_result_target, closure_result_status = _read_json(closure_result_path)
    release_archive, release_archive_target, release_archive_status = _read_json(release_archive_path)
    upload_paths = args.final_upload_path or list(DEFAULT_FINAL_UPLOAD_PATHS)
    path_reviews = [_path_review(path, args.run_id) for path in upload_paths]
    expected_files = _dedupe(_csv_items(args.expected_files) + args.expected_file)
    final_artifact = {
        "name": str(args.final_artifact_name or "").strip(),
        "id": str(args.final_artifact_id or "").strip(),
        "artifact_url": str(args.final_artifact_url or "").strip(),
        "digest": str(args.final_artifact_digest or "").strip(),
        "retention_days": str(args.final_retention_days or "").strip(),
    }

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

    _source_review(rows, blockers, warnings, strict, "closure-result", closure_result_target, closure_result, closure_result_status)
    _source_review(rows, blockers, warnings, strict, "release-archive", release_archive_target, release_archive, release_archive_status)

    closure = {
        "closure_result_decision": _closure_decision_from_result(closure_result),
        "archive_closure_decision": _closure_decision_from_archive(release_archive),
        "archive_result_closure_decision": _archive_result_decision(release_archive),
    }
    for key, value in closure.items():
        if value in VALID_CLOSURE_DECISIONS:
            rows.append(_row(key.replace("_", "-"), "passed", "%s is %s." % (key, value)))
        else:
            message = "%s is missing or invalid: %s." % (key, value or "empty")
            blockers.append(message)
            rows.append(_row(key.replace("_", "-"), "failed", message))
    if closure["closure_result_decision"] and closure["archive_closure_decision"]:
        if closure["closure_result_decision"] != closure["archive_closure_decision"]:
            message = "Closure result decision %s does not match archive closure decision %s." % (
                closure["closure_result_decision"],
                closure["archive_closure_decision"],
            )
            blockers.append(message)
            rows.append(_row("closure-result-archive-match", "failed", message))
        elif closure["archive_result_closure_decision"] != closure["archive_closure_decision"]:
            message = "Archive result closure decision %s does not match archive closure decision %s." % (
                closure["archive_result_closure_decision"],
                closure["archive_closure_decision"],
            )
            blockers.append(message)
            rows.append(_row("archive-result-closure-match", "failed", message))
        else:
            rows.append(_row("closure-result-archive-match", "passed", "Closure decisions match across result and archive."))

    for field, label in [
        ("name", "Final closure-result artifact name"),
        ("id", "Final closure-result artifact ID"),
        ("artifact_url", "Final closure-result artifact URL"),
    ]:
        if final_artifact.get(field):
            rows.append(_row("final-artifact-%s" % field.replace("_", "-"), "passed", "%s is recorded." % label))
        elif strict:
            message = "%s is required." % label
            blockers.append(message)
            rows.append(_row("final-artifact-%s" % field.replace("_", "-"), "failed", message))
        else:
            message = "%s is missing." % label
            warnings.append(message)
            rows.append(_row("final-artifact-%s" % field.replace("_", "-"), "warning", message))
    if final_artifact["digest"]:
        rows.append(_row("final-artifact-digest", "passed", "Final closure-result artifact digest is recorded."))
    else:
        warnings.append("Final closure-result artifact digest is missing.")
        rows.append(_row("final-artifact-digest", "warning", "Final closure-result artifact digest is missing."))

    retention_days = _as_int(final_artifact["retention_days"])
    minimum_retention_days = _as_int(args.minimum_retention_days) or 0
    if retention_days is None:
        warnings.append("Final closure-result artifact retention days are not numeric.")
        rows.append(_row("final-retention-days", "warning", "Final closure-result artifact retention days are not numeric."))
    elif retention_days < minimum_retention_days:
        message = "Final closure-result artifact retention days %s are below required minimum %s." % (
            retention_days,
            minimum_retention_days,
        )
        blockers.append(message)
        rows.append(_row("final-retention-days", "failed", message))
    else:
        rows.append(_row("final-retention-days", "passed", "Final closure-result artifact retention days meet policy."))

    final_files = set()
    for review in path_reviews:
        if review["exists"]:
            rows.append(_row("final-upload-path", "passed", "%s file(s) found." % review["file_count"], review["path"]))
        elif strict:
            message = "Final upload path is missing: %s" % review["path"]
            blockers.append(message)
            rows.append(_row("final-upload-path", "failed", message, review["path"]))
        else:
            message = "Final upload path is missing: %s" % review["path"]
            warnings.append(message)
            rows.append(_row("final-upload-path", "warning", message, review["path"]))
        final_files.update(Path(path).name for path in review["files"])
    missing_files = [name for name in expected_files if name not in final_files]
    if missing_files:
        message = "Expected archive upload file(s) missing from final upload paths: %s" % ", ".join(missing_files)
        if strict:
            blockers.append(message)
            rows.append(_row("final-expected-files", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("final-expected-files", "warning", message))
    else:
        rows.append(_row("final-expected-files", "passed", "All expected archive upload files are present."))

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
        "closure_result": _repo_relative(closure_result_target),
        "release_archive": _repo_relative(release_archive_target),
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
        "final_artifact": final_artifact,
        "final_upload_paths": path_reviews,
        "expected_files": expected_files,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-archive-upload-verification.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "archive-upload.md", _archive_upload_markdown(context, final_artifact, closure, rows))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, final_artifact, closure))
    _write(output / "summary.md", _summary(context, final_artifact, closure, blockers, warnings))
    print("Protected archive upload verification written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
