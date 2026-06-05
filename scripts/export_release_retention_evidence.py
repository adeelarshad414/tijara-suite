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
MINIMUM_RETENTION_DAYS = {
    "ci-artifacts": 30,
    "release-evidence": 365,
    "certification-evidence": 365,
    "logs": 30,
    "backups": 30,
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _safe_int(value):
    if value in (None, ""):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _iter_evidence_files(paths):
    for raw_path in paths:
        if not raw_path:
            continue
        path = _resolve_path(raw_path)
        if path.is_file():
            yield path
        elif path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file():
                    yield candidate


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


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Release Retention Evidence

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

- Release retention manifest: release-retention-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _add_required(rows, blockers, warnings, strict, name, value, label):
    if _present(value):
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is required for production release retention." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _add_retention_check(rows, blockers, warnings, strict, name, days, label):
    minimum = MINIMUM_RETENTION_DAYS[name]
    if days is None:
        message = "%s retention days are not configured." % label
        if strict:
            blockers.append(message)
            rows.append(_row("%s-retention-days" % name, "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("%s-retention-days" % name, "warning", message))
        return
    if days < minimum:
        message = "%s retention is %s day(s); minimum operational baseline is %s day(s)." % (
            label,
            days,
            minimum,
        )
        if strict:
            blockers.append(message)
            rows.append(_row("%s-retention-days" % name, "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("%s-retention-days" % name, "warning", message))
        return
    rows.append(
        _row(
            "%s-retention-days" % name,
            "passed",
            "%s retention is %s day(s), meeting the %s day baseline."
            % (label, days, minimum),
        )
    )


def _fingerprint_evidence(paths):
    files = []
    total_bytes = 0
    for path in _iter_evidence_files(paths):
        try:
            size = path.stat().st_size
            total_bytes += size
            files.append(
                {
                    "path": _repo_relative(path),
                    "size_bytes": size,
                    "sha256": _hash_file(path),
                }
            )
        except OSError:
            continue
    return files, total_bytes


def main():
    parser = argparse.ArgumentParser(
        description="Export Tijara release artifact retention and secret-manager evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_RETENTION_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_RETENTION_ENVIRONMENT", "production"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_RETENTION_OUTPUT", ""))
    parser.add_argument(
        "--artifact-store-reference",
        default=os.environ.get("TIJARA_ARTIFACT_STORE_REFERENCE", ""),
    )
    parser.add_argument(
        "--artifact-retention-policy-ref",
        default=os.environ.get("TIJARA_ARTIFACT_RETENTION_POLICY_REF", ""),
    )
    parser.add_argument(
        "--certification-retention-policy-ref",
        default=os.environ.get("TIJARA_CERTIFICATION_RETENTION_POLICY_REF", ""),
    )
    parser.add_argument(
        "--secret-manager-provider",
        default=os.environ.get("TIJARA_SECRET_MANAGER_PROVIDER", ""),
    )
    parser.add_argument(
        "--secret-manager-reference",
        default=os.environ.get("TIJARA_SECRET_MANAGER_REFERENCE", ""),
    )
    parser.add_argument(
        "--secret-rotation-policy-ref",
        default=os.environ.get("TIJARA_SECRET_ROTATION_POLICY_REF", ""),
    )
    parser.add_argument(
        "--ci-artifact-retention-days",
        default=os.environ.get("TIJARA_CI_ARTIFACT_RETENTION_DAYS", ""),
    )
    parser.add_argument(
        "--release-evidence-retention-days",
        default=os.environ.get("TIJARA_RELEASE_EVIDENCE_RETENTION_DAYS", ""),
    )
    parser.add_argument(
        "--certification-evidence-retention-days",
        default=os.environ.get("TIJARA_CERTIFICATION_EVIDENCE_RETENTION_DAYS", ""),
    )
    parser.add_argument("--log-retention-days", default=os.environ.get("TIJARA_LOG_RETENTION_DAYS", ""))
    parser.add_argument(
        "--backup-retention-days",
        default=os.environ.get("TIJARA_BACKUP_RETENTION_DAYS", ""),
    )
    parser.add_argument("--evidence-path", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_RETENTION_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when retention evidence is missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/release-retention-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    evidence_paths = list(args.evidence_path)
    evidence_paths.extend(_csv_items(os.environ.get("TIJARA_RETENTION_EVIDENCE_PATHS")))
    evidence_files, total_evidence_bytes = _fingerprint_evidence(evidence_paths)

    rows = []
    blockers = []
    warnings = []

    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append(_row("metadata-format", "failed", str(error)))
    else:
        rows.append(_row("metadata-format", "passed", "%s metadata item(s) parsed." % len(metadata)))

    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append(_row("metadata-secret-safety", "failed", message))
    else:
        rows.append(_row("metadata-secret-safety", "passed", "No secret-like metadata keys found."))

    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "artifact-store-reference",
        args.artifact_store_reference,
        "Artifact store",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "artifact-retention-policy",
        args.artifact_retention_policy_ref,
        "Artifact retention policy",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "certification-retention-policy",
        args.certification_retention_policy_ref,
        "Certification evidence retention policy",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-manager-provider",
        args.secret_manager_provider,
        "Secret manager provider",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-manager-reference",
        args.secret_manager_reference,
        "Secret manager reference",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-rotation-policy",
        args.secret_rotation_policy_ref,
        "Secret rotation policy",
    )

    retention_days = {
        "ci-artifacts": _safe_int(args.ci_artifact_retention_days),
        "release-evidence": _safe_int(args.release_evidence_retention_days),
        "certification-evidence": _safe_int(args.certification_evidence_retention_days),
        "logs": _safe_int(args.log_retention_days),
        "backups": _safe_int(args.backup_retention_days),
    }
    _add_retention_check(rows, blockers, warnings, strict, "ci-artifacts", retention_days["ci-artifacts"], "CI artifact")
    _add_retention_check(
        rows,
        blockers,
        warnings,
        strict,
        "release-evidence",
        retention_days["release-evidence"],
        "Release evidence",
    )
    _add_retention_check(
        rows,
        blockers,
        warnings,
        strict,
        "certification-evidence",
        retention_days["certification-evidence"],
        "Certification evidence",
    )
    _add_retention_check(rows, blockers, warnings, strict, "logs", retention_days["logs"], "Log")
    _add_retention_check(rows, blockers, warnings, strict, "backups", retention_days["backups"], "Backup")

    if evidence_files:
        rows.append(
            _row(
                "evidence-fingerprints",
                "passed",
                "%s evidence file(s) fingerprinted." % len(evidence_files),
            )
        )
    else:
        message = "No release evidence files were attached for retention fingerprinting."
        if strict:
            blockers.append(message)
            rows.append(_row("evidence-fingerprints", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("evidence-fingerprints", "warning", message))

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
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "artifact_store": {
            "reference_present": _present(args.artifact_store_reference),
            "retention_policy_reference_present": _present(args.artifact_retention_policy_ref),
            "certification_policy_reference_present": _present(args.certification_retention_policy_ref),
        },
        "secret_manager": {
            "provider_present": _present(args.secret_manager_provider),
            "provider": args.secret_manager_provider.strip(),
            "reference_present": _present(args.secret_manager_reference),
            "rotation_policy_reference_present": _present(args.secret_rotation_policy_ref),
        },
        "retention_days": retention_days,
        "minimum_retention_days": MINIMUM_RETENTION_DAYS,
        "evidence": {
            "input_paths": evidence_paths,
            "file_count": len(evidence_files),
            "total_bytes": total_evidence_bytes,
            "files": evidence_files,
        },
        "metadata": metadata,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "artifact_store_reference_present=%s" % int(_present(args.artifact_store_reference)),
            "artifact_retention_policy_present=%s" % int(_present(args.artifact_retention_policy_ref)),
            "certification_retention_policy_present=%s" % int(_present(args.certification_retention_policy_ref)),
            "secret_manager_provider=%s" % (args.secret_manager_provider.strip() or "<unset>"),
            "secret_manager_reference_present=%s" % int(_present(args.secret_manager_reference)),
            "secret_rotation_policy_present=%s" % int(_present(args.secret_rotation_policy_ref)),
            "ci_artifact_retention_days=%s" % (retention_days["ci-artifacts"] or "<unset>"),
            "release_evidence_retention_days=%s" % (retention_days["release-evidence"] or "<unset>"),
            "certification_evidence_retention_days=%s" % (retention_days["certification-evidence"] or "<unset>"),
            "log_retention_days=%s" % (retention_days["logs"] or "<unset>"),
            "backup_retention_days=%s" % (retention_days["backups"] or "<unset>"),
            "evidence_file_count=%s" % len(evidence_files),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "release-retention-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Release retention evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
