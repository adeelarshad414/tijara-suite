#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
REQUIRED_BY_CATEGORY = {
    "psp": ["provider", "reference", "owner"],
    "fbr": ["provider", "reference", "owner"],
    "hardware": ["device_model", "device_serial", "store", "owner"],
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_items(items):
    metadata = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError("Metadata must use key=value format: %s" % raw)
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("Metadata key cannot be blank.")
        metadata[key] = value
    return metadata


def _validate_sha256(digest, label):
    cleaned = str(digest or "").strip().lower()
    if len(cleaned) != 64 or any(char not in "0123456789abcdef" for char in cleaned):
        raise ValueError("%s must be a 64-character SHA-256 hex digest." % label)
    return cleaned


def _expected_hash_items(items):
    expected = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError("Expected hash must use path=sha256 format: %s" % raw)
        path, digest = raw.split("=", 1)
        path = path.strip()
        if not path:
            raise ValueError("Expected hash path cannot be blank.")
        expected[path] = _validate_sha256(digest, "Expected hash for %s" % path)
    return expected


def _load_artifact_manifest(path):
    if not path:
        return {}, [], None
    manifest_path = Path(path)
    if not manifest_path.is_absolute():
        manifest_path = ROOT_DIR / manifest_path
    if not manifest_path.is_file():
        raise ValueError("Artifact manifest does not exist: %s" % manifest_path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read artifact manifest %s: %s" % (manifest_path, error)) from error
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Artifact manifest must contain an artifacts list.")
    return payload, artifacts, manifest_path


def _manifest_artifact_path(manifest_path, artifact_path):
    candidate = Path(str(artifact_path or ""))
    if candidate.is_absolute():
        return str(candidate)
    if manifest_path:
        return str(manifest_path.parent / candidate)
    return str(ROOT_DIR / candidate)


def _normalized_input_path(raw_path):
    path = Path(str(raw_path or ""))
    if not path.is_absolute():
        path = ROOT_DIR / path
    return str(path)


def _parse_valid_until(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("valid-until must use YYYY-MM-DD format.") from error


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return ""


def _secret_metadata_keys(metadata):
    flagged = []
    for key in metadata:
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


def _evidence_file_entry(path, source):
    return {
        "source": source,
        "path": str(path),
        "relative_path": _repo_relative(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": _hash_file(path),
    }


def _missing_evidence_entry(path, source, message):
    return {
        "source": source,
        "path": str(path),
        "relative_path": _repo_relative(path),
        "exists": False,
        "size_bytes": 0,
        "sha256": "",
        "message": message,
    }


def _evidence_entries(raw_path):
    source = raw_path
    path = Path(source)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if path.is_dir():
        files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
        if not files:
            return [_missing_evidence_entry(path, source, "Evidence directory contains no files.")]
        return [_evidence_file_entry(candidate, source) for candidate in files]
    if not path.is_file():
        return [_missing_evidence_entry(path, source, "Evidence file does not exist.")]
    return [_evidence_file_entry(path, source)]


def _entry_matches(entry, expected_path):
    path = str(entry.get("path") or "")
    relative = str(entry.get("relative_path") or "")
    source = str(entry.get("source") or "")
    name = Path(path).name
    expected = str(expected_path or "")
    return expected in {path, relative, source, name}


def _status_row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings, output):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Certification Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Category: {context["category"]}
- Target environment: {context["target_environment"]}
- Output directory: {output}
- Generated: {context["generated_at"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Certification manifest: certification-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Collect and validate Tijara external certification evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_CERT_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--category",
        choices=sorted(REQUIRED_BY_CATEGORY),
        default=os.environ.get("TIJARA_CERT_CATEGORY", ""),
        required=not bool(os.environ.get("TIJARA_CERT_CATEGORY")),
    )
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_CERT_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_CERT_OUTPUT", ""))
    parser.add_argument("--provider", default=os.environ.get("TIJARA_CERT_PROVIDER", ""))
    parser.add_argument("--reference", default=os.environ.get("TIJARA_CERT_REFERENCE", ""))
    parser.add_argument("--owner", default=os.environ.get("TIJARA_CERT_OWNER", ""))
    parser.add_argument("--device-model", default=os.environ.get("TIJARA_CERT_DEVICE_MODEL", ""))
    parser.add_argument("--device-serial", default=os.environ.get("TIJARA_CERT_DEVICE_SERIAL", ""))
    parser.add_argument("--store", default=os.environ.get("TIJARA_CERT_STORE", ""))
    parser.add_argument("--evidence-file", action="append", default=[])
    parser.add_argument("--artifact-manifest", default=os.environ.get("TIJARA_CERT_ARTIFACT_MANIFEST", ""))
    parser.add_argument(
        "--expected-sha256",
        action="append",
        default=_csv_items(os.environ.get("TIJARA_CERT_EXPECTED_SHA256")),
        help="Expected evidence hash in path=sha256 format. Can be repeated.",
    )
    parser.add_argument(
        "--minimum-evidence-files",
        type=int,
        default=int(os.environ.get("TIJARA_CERT_MINIMUM_EVIDENCE_FILES", "1")),
    )
    parser.add_argument("--approved-by", default=os.environ.get("TIJARA_CERT_APPROVED_BY", ""))
    parser.add_argument("--approval-reference", default=os.environ.get("TIJARA_CERT_APPROVAL_REFERENCE", ""))
    parser.add_argument("--valid-until", default=os.environ.get("TIJARA_CERT_VALID_UNTIL", ""))
    parser.add_argument(
        "--require-artifact-manifest",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_CERT_REQUIRE_ARTIFACT_MANIFEST")),
    )
    parser.add_argument(
        "--require-approval",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_CERT_REQUIRE_APPROVAL")),
    )
    parser.add_argument(
        "--require-validity",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_CERT_REQUIRE_VALIDITY")),
    )
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_CERT_NON_STRICT")),
        help="Write warnings instead of failing when required evidence is missing.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Force strict blocker behavior even when TIJARA_CERT_NON_STRICT is set.",
    )
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False

    output = (
        Path(args.output)
        if args.output
        else ROOT_DIR / "deploy/runtime/certification-evidence" / args.run_id / args.category
    )
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append(_status_row("metadata-format", "failed", str(error)))
    else:
        rows.append(_status_row("metadata-format", "passed", "%s metadata item(s) parsed." % len(metadata)))

    try:
        expected_hashes = _expected_hash_items(args.expected_sha256)
    except ValueError as error:
        expected_hashes = {}
        blockers.append(str(error))
        rows.append(_status_row("expected-hash-format", "failed", str(error)))
    else:
        rows.append(_status_row("expected-hash-format", "passed", "%s expected hash item(s) parsed." % len(expected_hashes)))

    try:
        artifact_manifest, manifest_artifacts, artifact_manifest_path = _load_artifact_manifest(args.artifact_manifest)
    except ValueError as error:
        artifact_manifest = {}
        manifest_artifacts = []
        artifact_manifest_path = None
        blockers.append(str(error))
        rows.append(_status_row("artifact-manifest", "failed", str(error)))
    else:
        if args.artifact_manifest:
            rows.append(_status_row("artifact-manifest", "passed", "%s artifact manifest item(s) parsed." % len(manifest_artifacts)))
        elif args.require_artifact_manifest:
            message = "Artifact manifest is required for this certification evidence run."
            if args.non_strict:
                warnings.append(message)
                rows.append(_status_row("artifact-manifest", "warning", message))
            else:
                blockers.append(message)
                rows.append(_status_row("artifact-manifest", "failed", message))
        else:
            warnings.append("No artifact manifest was attached.")
            rows.append(_status_row("artifact-manifest", "warning", "No artifact manifest was attached."))

    try:
        valid_until_date = _parse_valid_until(args.valid_until)
    except ValueError as error:
        valid_until_date = None
        blockers.append(str(error))
        rows.append(_status_row("valid-until-format", "failed", str(error)))
    else:
        rows.append(
            _status_row(
                "valid-until-format",
                "passed" if valid_until_date else "warning",
                "Certification validity date is %s." % (args.valid_until or "not recorded"),
            )
        )

    secret_keys = _secret_metadata_keys(metadata)
    if secret_keys:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(secret_keys)
        blockers.append(message)
        rows.append(_status_row("metadata-secret-safety", "failed", message))
    else:
        rows.append(_status_row("metadata-secret-safety", "passed", "No secret-like metadata keys found."))

    context = {
        "run_id": args.run_id,
        "category": args.category,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "provider": args.provider,
        "reference": args.reference,
        "owner": args.owner,
        "device_model": args.device_model,
        "device_serial": args.device_serial,
        "store": args.store,
        "approved_by": args.approved_by,
        "approval_reference": args.approval_reference,
        "valid_until": args.valid_until,
    }
    for field in REQUIRED_BY_CATEGORY[args.category]:
        value = context.get(field)
        if value:
            rows.append(_status_row("required-%s" % field, "passed", "%s recorded." % field))
        else:
            message = "%s is required for %s certification evidence." % (field, args.category)
            if args.non_strict:
                warnings.append(message)
                rows.append(_status_row("required-%s" % field, "warning", message))
            else:
                blockers.append(message)
                rows.append(_status_row("required-%s" % field, "failed", message))

    evidence_paths = list(args.evidence_file)
    env_paths = os.environ.get("TIJARA_CERT_EVIDENCE_FILES", "")
    if env_paths:
        evidence_paths.extend(path.strip() for path in env_paths.split(",") if path.strip())
    manifest_hash_errors = []
    resolved_manifest_artifacts = []
    for artifact in manifest_artifacts:
        if isinstance(artifact, dict) and artifact.get("path"):
            resolved_path = _manifest_artifact_path(artifact_manifest_path, artifact["path"])
            resolved_manifest_artifacts.append(
                {
                    "path": str(artifact["path"]),
                    "resolved_path": resolved_path,
                    "required": artifact.get("required", True),
                    "sha256": str(artifact.get("sha256") or "").strip().lower(),
                }
            )
            evidence_paths.append(resolved_path)
            if artifact.get("sha256"):
                try:
                    expected_hashes.setdefault(
                        resolved_path,
                        _validate_sha256(artifact["sha256"], "Manifest artifact hash for %s" % artifact["path"]),
                    )
                except ValueError as error:
                    manifest_hash_errors.append(str(error))
    if manifest_hash_errors:
        message = "; ".join(manifest_hash_errors)
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("manifest-artifact-hashes", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("manifest-artifact-hashes", "failed", message))
    else:
        rows.append(
            _status_row(
                "manifest-artifact-hashes",
                "passed",
                "%s manifest artifact hash item(s) parsed." % len(
                    [artifact for artifact in resolved_manifest_artifacts if artifact.get("sha256")]
                ),
            )
        )
    deduped_evidence_paths = []
    seen_evidence_paths = set()
    for path in evidence_paths:
        normalized_path = _normalized_input_path(path)
        if normalized_path in seen_evidence_paths:
            continue
        seen_evidence_paths.add(normalized_path)
        deduped_evidence_paths.append(normalized_path)
    evidence = []
    for path in deduped_evidence_paths:
        evidence.extend(_evidence_entries(path))
    if evidence and all(entry["exists"] for entry in evidence):
        rows.append(_status_row("evidence-files", "passed", "%s evidence file(s) hashed." % len(evidence)))
    elif evidence:
        missing = [entry["path"] for entry in evidence if not entry["exists"]]
        message = "Missing evidence file(s): %s" % ", ".join(missing)
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("evidence-files", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("evidence-files", "failed", message))
    else:
        message = "At least one evidence file should be attached."
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("evidence-files", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("evidence-files", "failed", message))

    present_evidence = [entry for entry in evidence if entry.get("exists")]
    if len(present_evidence) >= args.minimum_evidence_files:
        rows.append(
            _status_row(
                "minimum-evidence-files",
                "passed",
                "%s/%s required evidence file(s) are present." % (len(present_evidence), args.minimum_evidence_files),
            )
        )
    else:
        message = "%s evidence file(s) attached; minimum is %s." % (len(present_evidence), args.minimum_evidence_files)
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("minimum-evidence-files", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("minimum-evidence-files", "failed", message))

    hash_failures = []
    for expected_path, expected_hash in expected_hashes.items():
        matches = [entry for entry in present_evidence if _entry_matches(entry, expected_path)]
        if not matches:
            hash_failures.append("%s was not found in attached evidence" % expected_path)
            continue
        if not any(entry.get("sha256") == expected_hash for entry in matches):
            hash_failures.append("%s hash does not match expected SHA-256" % expected_path)
    if hash_failures:
        message = "; ".join(hash_failures)
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("expected-hashes", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("expected-hashes", "failed", message))
    else:
        rows.append(_status_row("expected-hashes", "passed", "%s expected hash item(s) matched." % len(expected_hashes)))

    missing_manifest_artifacts = []
    for artifact in resolved_manifest_artifacts:
        required = artifact.get("required", True)
        path = str(artifact.get("path") or "")
        resolved_path = str(artifact.get("resolved_path") or "")
        if required and resolved_path and not any(
            (_entry_matches(entry, resolved_path) or _entry_matches(entry, path)) and entry.get("exists")
            for entry in evidence
        ):
            missing_manifest_artifacts.append(path or resolved_path)
    if missing_manifest_artifacts:
        message = "Required manifest artifact(s) missing: %s" % ", ".join(missing_manifest_artifacts)
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("manifest-required-artifacts", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("manifest-required-artifacts", "failed", message))
    else:
        rows.append(_status_row("manifest-required-artifacts", "passed", "All required manifest artifact(s) are present."))

    if args.approved_by and args.approval_reference:
        rows.append(_status_row("approval", "passed", "Approval owner and reference are recorded."))
    elif args.require_approval:
        message = "Approval owner and reference are required for production certification evidence."
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("approval", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("approval", "failed", message))
    else:
        warnings.append("Approval owner/reference are not recorded.")
        rows.append(_status_row("approval", "warning", "Approval owner/reference are not recorded."))

    if valid_until_date:
        today = dt.datetime.now(dt.timezone.utc).date()
        if valid_until_date >= today:
            rows.append(_status_row("validity", "passed", "Certification evidence is valid until %s." % args.valid_until))
        else:
            message = "Certification evidence expired on %s." % args.valid_until
            if args.non_strict:
                warnings.append(message)
                rows.append(_status_row("validity", "warning", message))
            else:
                blockers.append(message)
                rows.append(_status_row("validity", "failed", message))
    elif args.require_validity:
        message = "Certification validity date is required."
        if args.non_strict:
            warnings.append(message)
            rows.append(_status_row("validity", "warning", message))
        else:
            blockers.append(message)
            rows.append(_status_row("validity", "failed", message))
    else:
        rows.append(_status_row("validity", "warning", "Certification validity date is not recorded."))

    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    manifest = {
        "context": context,
        "metadata": metadata,
        "artifact_manifest": {
            "path": args.artifact_manifest,
            "artifact_count": len(manifest_artifacts),
            "metadata": artifact_manifest.get("metadata") if isinstance(artifact_manifest.get("metadata"), dict) else {},
            "required": bool(args.require_artifact_manifest),
            "resolved_artifacts": resolved_manifest_artifacts,
        },
        "evidence": evidence,
        "expected_hashes": expected_hashes,
        "approval": {
            "approved_by_present": bool(args.approved_by),
            "approval_reference_present": bool(args.approval_reference),
            "approved_by": args.approved_by,
            "approval_reference": args.approval_reference,
            "require_approval": bool(args.require_approval),
        },
        "validity": {
            "valid_until": args.valid_until,
            "valid_until_present": bool(args.valid_until),
            "require_validity": bool(args.require_validity),
        },
        "requirements": {
            "minimum_evidence_files": args.minimum_evidence_files,
            "attached_evidence_files": len(present_evidence),
            "require_artifact_manifest": bool(args.require_artifact_manifest),
        },
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "category=%s" % args.category,
            "target_environment=%s" % args.target_environment,
            "provider=%s" % (args.provider or "<unset>"),
            "reference=%s" % (args.reference or "<unset>"),
            "owner=%s" % (args.owner or "<unset>"),
            "device_model=%s" % (args.device_model or "<unset>"),
            "device_serial=%s" % (args.device_serial or "<unset>"),
            "store=%s" % (args.store or "<unset>"),
            "approved_by=%s" % (args.approved_by or "<unset>"),
            "approval_reference=%s" % (args.approval_reference or "<unset>"),
            "valid_until=%s" % (args.valid_until or "<unset>"),
            "artifact_manifest=%s" % (args.artifact_manifest or "<unset>"),
            "require_artifact_manifest=%s" % int(args.require_artifact_manifest),
            "minimum_evidence_files=%s" % args.minimum_evidence_files,
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "certification-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings, output))

    print("Certification evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
