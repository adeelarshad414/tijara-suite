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
    "production-ops-readiness",
    "protected-post-run-verification",
    "protected-artifact-summary",
    "certification-result-matrix",
    "e2e-execution",
    "protected-offline-pilot",
    "operations-release-bundle",
    "ops-tool-evidence",
]
DEFAULT_COMPONENT_PATHS = {
    "release-readiness": "deploy/runtime/signoff-packages/{run_id}/release-readiness.json",
    "production-ops-readiness": "deploy/runtime/production-ops-readiness/{run_id}/production-ops-readiness.json",
    "protected-post-run-verification": "deploy/runtime/protected-post-run-verification/{run_id}/protected-post-run-verification.json",
    "protected-artifact-summary": "deploy/runtime/protected-artifact-summary/{run_id}/protected-artifact-summary.json",
    "certification-result-matrix": "deploy/runtime/certification-evidence/{run_id}/result-matrix/certification-result-matrix.json",
    "e2e-execution": "deploy/runtime/e2e-execution/{run_id}/e2e-execution-evidence.json",
    "protected-offline-pilot": "deploy/runtime/protected-offline-pilot/{run_id}/offline-pos-pilot-evidence.json",
    "operations-release-bundle": "deploy/runtime/operations-release-bundle/{run_id}/operations-release-bundle.json",
    "ops-tool-evidence": "deploy/runtime/ops-tool-evidence/{run_id}/ops-tool-evidence.json",
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
        raw = "deploy/runtime/%s/%s/%s.json" % (name, run_id, name)
    return _resolve(raw.format(run_id=run_id))


def _component_review(name, path, required):
    payload, read_status = _read_json(path)
    decision, ci_status = _decision_fields(payload)
    state = _decision_state(decision, ci_status)
    blockers = []
    warnings = []

    if read_status == "missing":
        if required:
            blockers.append("%s evidence is missing." % name)
            row_status = "failed"
            message = "Required evidence JSON is missing."
        else:
            row_status = "skipped"
            message = "Optional evidence JSON is not attached."
    elif read_status.startswith("read_error:"):
        blockers.append("%s evidence could not be read." % name)
        row_status = "failed"
        message = read_status
    elif state == "failed":
        blockers.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        row_status = "failed"
        message = "Component decision is failing."
    elif state == "warning":
        warnings.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
        row_status = "warning"
        message = "Component decision has warnings."
    elif state == "passed":
        row_status = "passed"
        message = "Component decision is passing."
    elif required:
        blockers.append("%s decision is missing or unknown." % name)
        row_status = "failed"
        message = "Required evidence JSON has no recognized decision."
    else:
        row_status = "warning"
        message = "Optional evidence JSON has no recognized decision."
        warnings.append("%s decision is missing or unknown." % name)

    blockers.extend("%s: %s" % (name, item) for item in payload.get("blockers") or [])
    warnings.extend("%s: %s" % (name, item) for item in payload.get("warnings") or [])

    return {
        "name": name,
        "path": _repo_relative(path),
        "required": bool(required),
        "exists": path.is_file(),
        "decision": decision,
        "ci_status": ci_status,
        "state": state,
        "status": row_status,
        "message": message,
        "blockers": blockers,
        "warnings": warnings,
    }


def _status_tsv(components):
    lines = ["component\tstatus\tmessage\tpath\tdecision\tci_status\trequired"]
    for component in components:
        lines.append(
            "%s\t%s\t%s\t%s\t%s\t%s\t%s"
            % (
                component["name"],
                component["status"],
                component["message"],
                component["path"],
                component["decision"] or "",
                component["ci_status"] or "",
                int(component["required"]),
            )
        )
    return "\n".join(lines)


def _env_summary(context):
    lines = [
        "run_id=%s" % context["run_id"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "required_components=%s" % ",".join(context["required_components"]),
        "optional_components=%s" % (",".join(context["optional_components"]) or "<none>"),
        "fail_on_warning=%s" % int(context["fail_on_warning"]),
        "strict=%s" % int(context["strict"]),
    ]
    return "\n".join(lines)


def _summary(context, components, blockers, warnings):
    component_lines = []
    for component in components:
        component_lines.append(
            "- `%s`: %s, required=%s, decision=%s/%s, path=%s"
            % (
                component["name"],
                component["status"],
                "yes" if component["required"] else "no",
                component["decision"] or "missing",
                component["ci_status"] or "missing",
                component["path"],
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Run Decision

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Components

{chr(10).join(component_lines) or "- No components were evaluated."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Protected run decision: protected-run-decision.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export protected release run decision evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_RUN_DECISION_OUTPUT", ""))
    parser.add_argument("--required-component", action="append", default=[])
    parser.add_argument(
        "--required-components",
        default=os.environ.get(
            "TIJARA_PROTECTED_RUN_DECISION_REQUIRED_COMPONENTS",
            ",".join(DEFAULT_REQUIRED_COMPONENTS),
        ),
    )
    parser.add_argument("--optional-component", action="append", default=[])
    parser.add_argument(
        "--optional-components",
        default=os.environ.get("TIJARA_PROTECTED_RUN_DECISION_OPTIONAL_COMPONENTS", ""),
    )
    parser.add_argument("--component", action="append", default=[], help="Override component path as name=path.")
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_RUN_DECISION_FAIL_ON_WARNING", "1")),
    )
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_RUN_DECISION_NON_STRICT", "0")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-run-decision" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    blockers = []
    warnings = []
    try:
        overrides = _component_overrides(args.component)
    except ValueError as error:
        overrides = {}
        blockers.append(str(error))
    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
    flagged = _secret_like_keys(metadata)
    if flagged:
        blockers.append("Secret-like metadata keys are not allowed: %s" % ", ".join(flagged))

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
        blockers.extend(component["blockers"])
        warnings.extend(component["warnings"])

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    if args.fail_on_warning and warnings:
        blockers.extend("Warning treated as blocker: %s" % warning for warning in warnings)
        blockers = _dedupe(blockers)
    if blockers:
        decision = "blocked"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "approved"
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
        "components": components,
        "blockers": blockers,
        "warnings": warnings,
        "metadata": metadata,
    }
    _write(output / "protected-run-decision.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(components))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, components, blockers, warnings))
    print("Protected run decision written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
