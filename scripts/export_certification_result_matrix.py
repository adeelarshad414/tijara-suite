#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
CATEGORIES = ["psp", "fbr", "courier", "hardware"]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip().lower() for item in str(value or "").split(",") if item.strip()]


def _dedupe(items):
    clean = []
    seen = set()
    for item in items:
        value = str(item or "").strip().lower()
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


def _read_json(path):
    if not path or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _secret_like_keys(metadata):
    flagged = []
    for key in metadata:
        normalized = str(key).lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


def _decision_status(payload):
    decision = str(payload.get("decision") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in {"failed", "blocked"} or ci_status == "fail":
        return "failed"
    if decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        return "warning"
    if decision or ci_status:
        return "passed"
    return "missing"


def _execution_category_map(execution_payload):
    rows = {}
    for item in execution_payload.get("categories") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip().lower()
        if category:
            rows[category] = item
    return rows


def _category_output(root, execution_row, category):
    raw = str((execution_row or {}).get("output") or "").strip()
    if raw:
        return _resolve(raw)
    return root / category


def _present(value):
    return bool(str(value or "").strip())


def _today():
    return dt.datetime.now(dt.timezone.utc).date()


def _validity_state(payload):
    validity = payload.get("validity") or {}
    value = str(validity.get("valid_until") or "").strip()
    if not value:
        return {"present": False, "expired": False, "valid_until": ""}
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        return {"present": True, "expired": True, "valid_until": value}
    return {"present": True, "expired": parsed < _today(), "valid_until": value}


def _provider_readiness_status(provider_payload, category):
    runs = provider_payload.get("runs") if isinstance(provider_payload, dict) else []
    if not isinstance(runs, list):
        return {"present": bool(provider_payload), "status": "", "decision": "", "ci_status": ""}
    wanted = "psp-readiness" if category == "psp" else "fbr-readiness" if category == "fbr" else ""
    for run in runs:
        if not isinstance(run, dict) or run.get("name") != wanted:
            continue
        payload = run.get("payload") if isinstance(run.get("payload"), dict) else {}
        return {
            "present": True,
            "status": run.get("status", "") or _decision_status(payload),
            "decision": payload.get("decision", ""),
            "ci_status": payload.get("ci_status", ""),
            "output": run.get("output", ""),
        }
    return {"present": bool(provider_payload), "status": "", "decision": "", "ci_status": ""}


def _category_matrix_row(root, category, required, execution_row, provider_payload, require_provider_readiness, fail_on_warning):
    category_dir = _category_output(root, execution_row, category)
    evidence_path = category_dir / "certification-evidence.json"
    payload = _read_json(evidence_path)
    context = payload.get("context") or {}
    approval = payload.get("approval") or {}
    requirements = payload.get("requirements") or {}
    artifact_manifest = payload.get("artifact_manifest") or {}
    evidence = payload.get("evidence") or []
    validity = _validity_state(payload)
    existing = [item for item in evidence if isinstance(item, dict) and item.get("exists")]
    execution_status = str((execution_row or {}).get("status") or "").strip().lower()
    provider_status = _provider_readiness_status(provider_payload, category)
    warnings = []
    blockers = []

    if not payload:
        if required:
            blockers.append("%s certification evidence is missing." % category.upper())
        elif execution_status and execution_status != "skipped":
            warnings.append(
                "%s certification execution is %s but evidence is not attached."
                % (category.upper(), execution_status)
            )
    else:
        status = _decision_status(payload)
        if status == "failed":
            blockers.append("%s certification evidence is failed." % category.upper())
        elif status == "warning":
            message = "%s certification evidence has warnings." % category.upper()
            if required and fail_on_warning:
                blockers.append(message)
            else:
                warnings.append(message)
        if required and not approval.get("approved_by_present"):
            blockers.append("%s certification approval owner is missing." % category.upper())
        if required and not approval.get("approval_reference_present"):
            blockers.append("%s certification approval reference is missing." % category.upper())
        if required and not validity["present"]:
            blockers.append("%s certification validity date is missing." % category.upper())
        if validity["expired"]:
            blockers.append("%s certification validity is expired." % category.upper())
        if required and len(existing) < int(requirements.get("minimum_evidence_files") or 0):
            blockers.append("%s certification evidence file count is below minimum." % category.upper())

    if required and execution_status in {"failed", "blocked"}:
        blockers.append("%s protected certification execution failed." % category.upper())
    if required and execution_status == "skipped":
        blockers.append("%s protected certification execution was skipped." % category.upper())

    if require_provider_readiness and category in {"psp", "fbr"}:
        status = str(provider_status.get("status") or "").lower()
        if not provider_status.get("present") or not status:
            blockers.append("%s provider readiness evidence is missing." % category.upper())
        elif status == "failed":
            blockers.append("%s provider readiness evidence failed." % category.upper())
        elif status == "warning":
            message = "%s provider readiness evidence has warnings." % category.upper()
            if fail_on_warning:
                blockers.append(message)
            else:
                warnings.append(message)

    if blockers:
        result = "failed"
    elif warnings:
        result = "warning"
    elif payload:
        result = "passed"
    else:
        result = "skipped"

    return {
        "category": category,
        "required": bool(required),
        "result": result,
        "execution_status": execution_status,
        "execution_message": (execution_row or {}).get("message", ""),
        "output": _repo_relative(category_dir),
        "evidence_path": _repo_relative(evidence_path),
        "evidence_present": bool(payload),
        "evidence_decision": payload.get("decision", ""),
        "evidence_ci_status": payload.get("ci_status", ""),
        "provider": context.get("provider", ""),
        "reference": context.get("reference", ""),
        "owner": context.get("owner", ""),
        "device_model": context.get("device_model", ""),
        "device_serial_present": bool(context.get("device_serial")),
        "store": context.get("store", ""),
        "evidence_count": len(existing),
        "minimum_evidence_files": requirements.get("minimum_evidence_files", 0),
        "expected_hash_count": len(payload.get("expected_hashes") or {}),
        "artifact_manifest_present": bool(artifact_manifest.get("path")),
        "artifact_manifest_count": artifact_manifest.get("artifact_count", 0),
        "approved_by_present": bool(approval.get("approved_by_present")),
        "approval_reference_present": bool(approval.get("approval_reference_present")),
        "valid_until": validity["valid_until"],
        "validity_present": validity["present"],
        "validity_expired": validity["expired"],
        "provider_readiness": provider_status,
        "blockers": blockers,
        "warnings": warnings,
    }


def _summary(context, rows, matrix_rows, blockers, warnings):
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    matrix_lines = []
    for item in matrix_rows:
        matrix_lines.append(
            "- %s: %s, required=%s, evidence=%s/%s, approval=%s/%s, valid_until=%s"
            % (
                item["category"],
                item["result"],
                "yes" if item["required"] else "no",
                item["evidence_decision"] or "missing",
                item["evidence_ci_status"] or "missing",
                "yes" if item["approved_by_present"] else "no",
                "yes" if item["approval_reference_present"] else "no",
                item["valid_until"] or "unset",
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Certification Result Matrix

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Required groups: {", ".join(context["required_groups"]) or "none"}

## Matrix

{chr(10).join(matrix_lines) or "- No certification categories were evaluated."}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Certification result matrix: certification-result-matrix.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context):
    lines = [
        "run_id=%s" % context["run_id"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "certification_root=%s" % context["certification_root"],
        "provider_readiness=%s" % (context["provider_readiness"] or "<unset>"),
        "required_groups=%s" % (",".join(context["required_groups"]) or "<none>"),
        "require_provider_readiness=%s" % int(context["require_provider_readiness"]),
        "fail_on_warning=%s" % int(context["fail_on_warning"]),
        "strict=%s" % int(context["strict"]),
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export PSP/FBR/courier/hardware certification result matrix.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", os.environ.get("TIJARA_CERT_RUN_ID", _default_run_id())))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", os.environ.get("TIJARA_CERT_ENVIRONMENT", "staging")))
    parser.add_argument("--output", default=os.environ.get("TIJARA_CERTIFICATION_MATRIX_OUTPUT", ""))
    parser.add_argument("--certification-root", default=os.environ.get("TIJARA_CERTIFICATION_MATRIX_ROOT", ""))
    parser.add_argument("--provider-readiness", default=os.environ.get("TIJARA_CERTIFICATION_MATRIX_PROVIDER_READINESS", ""))
    parser.add_argument("--required-group", action="append", default=[])
    parser.add_argument("--required-groups", default=os.environ.get("TIJARA_CERTIFICATION_MATRIX_REQUIRED_GROUPS", os.environ.get("TIJARA_PROTECTED_CERTIFICATION_GROUPS", "")))
    parser.add_argument("--require-provider-readiness", action="store_true", default=_truthy(os.environ.get("TIJARA_CERTIFICATION_MATRIX_REQUIRE_PROVIDER_READINESS")))
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_CERTIFICATION_MATRIX_FAIL_ON_WARNING")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_CERTIFICATION_MATRIX_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    root = _resolve(args.certification_root) if args.certification_root else ROOT_DIR / "deploy/runtime/certification-evidence" / args.run_id
    output = Path(args.output) if args.output else root / "result-matrix"
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    provider_readiness_path = (
        _resolve(args.provider_readiness)
        if args.provider_readiness
        else ROOT_DIR / "deploy/runtime/protected-provider-readiness" / args.run_id / "protected-provider-readiness.json"
    )
    required_groups = _dedupe(args.required_group + _csv_items(args.required_groups))
    required_groups = [item for item in required_groups if item in CATEGORIES]
    execution_path = root / "certification-execution.json"
    execution_payload = _read_json(execution_path)
    execution_rows = _execution_category_map(execution_payload)
    provider_payload = _read_json(provider_readiness_path)

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

    if execution_payload:
        rows.append(_row("certification-execution", _decision_status(execution_payload), "Root certification execution evidence is present.", _repo_relative(execution_path)))
    else:
        message = "Root certification execution evidence is missing."
        if strict:
            blockers.append(message)
            rows.append(_row("certification-execution", "failed", message, _repo_relative(execution_path)))
        else:
            warnings.append(message)
            rows.append(_row("certification-execution", "warning", message, _repo_relative(execution_path)))

    if provider_payload:
        rows.append(_row("provider-readiness", _decision_status(provider_payload), "Protected provider readiness evidence is present.", _repo_relative(provider_readiness_path)))
    elif args.require_provider_readiness:
        message = "Protected provider readiness evidence is required but missing."
        blockers.append(message)
        rows.append(_row("provider-readiness", "failed", message, _repo_relative(provider_readiness_path)))
    else:
        rows.append(_row("provider-readiness", "warning", "Protected provider readiness evidence is not attached.", _repo_relative(provider_readiness_path)))

    matrix_rows = []
    for category in CATEGORIES:
        item = _category_matrix_row(
            root,
            category,
            category in required_groups,
            execution_rows.get(category),
            provider_payload,
            args.require_provider_readiness,
            args.fail_on_warning,
        )
        matrix_rows.append(item)
        if item["result"] == "failed":
            blockers.extend(item["blockers"])
            rows.append(_row("category-%s" % category, "failed", "%s result is failed." % category.upper(), item["evidence_path"]))
        elif item["result"] == "warning":
            warnings.extend(item["warnings"])
            rows.append(_row("category-%s" % category, "warning", "%s result has warnings." % category.upper(), item["evidence_path"]))
        elif item["result"] == "passed":
            rows.append(_row("category-%s" % category, "passed", "%s result is passed." % category.upper(), item["evidence_path"]))
        else:
            rows.append(_row("category-%s" % category, "skipped", "%s is optional and not attached." % category.upper(), item["evidence_path"]))

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

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "certification_root": _repo_relative(root),
        "provider_readiness": _repo_relative(provider_readiness_path),
        "required_groups": required_groups,
        "require_provider_readiness": bool(args.require_provider_readiness),
        "fail_on_warning": bool(args.fail_on_warning),
        "strict": strict,
        "decision": decision,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "matrix": matrix_rows,
        "blockers": blockers,
        "warnings": warnings,
        "metadata": metadata,
    }
    _write(output / "certification-result-matrix.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, rows, matrix_rows, blockers, warnings))

    print("Certification result matrix written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
