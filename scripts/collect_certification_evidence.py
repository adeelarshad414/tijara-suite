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
    evidence = []
    for path in evidence_paths:
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
        "evidence": evidence,
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
