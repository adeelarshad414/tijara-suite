#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_STATUSES = {"approved", "ready", "passed", "pass", "success", "ok", "promotion_ready"}
WARNING_STATUSES = {"warning", "warn", "watch", "pass_with_warnings"}
FAILING_STATUSES = {"blocked", "failed", "fail", "error"}
VALID_CLOSURE_DECISIONS = {"promotion_ready", "watch", "blocked"}
DEFAULT_REQUIRED_COMPONENTS = [
    "protected-run-decision",
    "protected-evidence-retention",
    "protected-sidecar-verification",
    "protected-evidence-replay",
    "protected-release-evidence-index",
    "protected-release-closure",
    "protected-closure-result-verification",
    "protected-release-archive",
    "protected-archive-upload-verification",
]
DEFAULT_COMPONENT_PATHS = {
    "protected-run-decision": "deploy/runtime/protected-run-decision/{run_id}/protected-run-decision.json",
    "protected-evidence-retention": "deploy/runtime/protected-evidence-retention/{run_id}/protected-evidence-retention-manifest.json",
    "protected-sidecar-verification": "deploy/runtime/protected-sidecar-verification/{run_id}/protected-sidecar-verification.json",
    "protected-evidence-replay": "deploy/runtime/protected-evidence-replay/{run_id}/protected-evidence-replay-report.json",
    "protected-release-evidence-index": "deploy/runtime/protected-release-evidence-index/{run_id}/protected-release-evidence-index.json",
    "protected-release-closure": "deploy/runtime/protected-release-closure/{run_id}/protected-release-closure-decision.json",
    "protected-closure-result-verification": "deploy/runtime/protected-closure-result-verification/{run_id}/protected-closure-result-verification.json",
    "protected-release-archive": "deploy/runtime/protected-release-archive/{run_id}/protected-release-archive-manifest.json",
    "protected-archive-upload-verification": "deploy/runtime/protected-archive-upload-verification/{run_id}/protected-archive-upload-verification.json",
    "github-artifact-metadata": "deploy/runtime/github-artifact-metadata/{run_id}/github-artifact-metadata.json",
    "release-readiness": "deploy/runtime/signoff-packages/{run_id}/release-readiness.json",
    "production-ops-readiness": "deploy/runtime/production-ops-readiness/{run_id}/production-ops-readiness.json",
    "release-retention-evidence": "deploy/runtime/release-retention-evidence/{run_id}/release-retention-evidence.json",
    "certification-result-matrix": "deploy/runtime/certification-evidence/{run_id}/result-matrix/certification-result-matrix.json",
}
RISK_CATEGORIES = {
    "protected-run-decision": "Release governance",
    "protected-evidence-retention": "Retention",
    "protected-sidecar-verification": "Artifact integrity",
    "protected-evidence-replay": "Artifact integrity",
    "protected-release-evidence-index": "Release owner review",
    "protected-release-closure": "Closure decision",
    "protected-closure-result-verification": "Closure upload",
    "protected-release-archive": "Audit archive",
    "protected-archive-upload-verification": "Final upload",
    "github-artifact-metadata": "Artifact integrity",
    "release-readiness": "Release governance",
    "production-ops-readiness": "Operations",
    "release-retention-evidence": "Retention",
    "certification-result-matrix": "Certification",
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
    if not path.is_file():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, "read_error:%s" % error
    return payload if isinstance(payload, dict) else {}, "ok"


def _as_float(value, default):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _decision_fields(payload):
    decision = str(payload.get("decision") or payload.get("closure_decision") or payload.get("status") or "").strip()
    ci_status = str(payload.get("ci_status") or "").strip()
    if not decision and ci_status:
        decision = ci_status
    return decision, ci_status


def _decision_state(decision, ci_status):
    decision_value = str(decision or "").lower()
    ci_value = str(ci_status or "").lower()
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


def _closure_decision_from_payload(name, payload):
    if name == "protected-release-closure":
        return str(payload.get("closure_decision") or payload.get("decision") or "").strip()
    if name == "protected-closure-result-verification":
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        return str(payload.get("closure_decision") or context.get("closure_decision") or "").strip()
    if name == "protected-release-archive":
        closure = payload.get("closure") if isinstance(payload.get("closure"), dict) else {}
        return str(closure.get("closure_decision") or "").strip()
    if name == "protected-archive-upload-verification":
        closure = payload.get("closure") if isinstance(payload.get("closure"), dict) else {}
        return str(closure.get("archive_closure_decision") or closure.get("closure_result_decision") or "").strip()
    return ""


def _component_score(status):
    if status == "passed":
        return 1.0
    if status == "warning":
        return 0.5
    return 0.0


def _component_review(name, path, required):
    payload, read_status = _read_json(path)
    decision, ci_status = _decision_fields(payload)
    state = _decision_state(decision, ci_status)
    closure_decision = _closure_decision_from_payload(name, payload)
    blockers = []
    warnings = []
    evidence_status = "missing"
    risk_level = "low"
    release_risk = ""

    if read_status == "missing":
        evidence_status = "failed" if required else "skipped"
        if required:
            blockers.append("%s score source is missing." % name)
        else:
            warnings.append("%s optional score source is missing." % name)
    elif read_status.startswith("read_error:"):
        evidence_status = "failed"
        blockers.append("%s score source could not be read." % name)
    elif name == "protected-release-closure" and closure_decision in VALID_CLOSURE_DECISIONS:
        evidence_status = "passed"
        if closure_decision == "blocked":
            release_risk = "Closure decision is blocked."
            blockers.append(release_risk)
        elif closure_decision == "watch":
            release_risk = "Closure decision is watch."
            warnings.append(release_risk)
    elif state == "failed":
        evidence_status = "failed"
        blockers.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
    elif state == "warning":
        evidence_status = "warning"
        warnings.append("%s decision is %s/%s." % (name, decision or "unknown", ci_status or "unknown"))
    elif state == "passed":
        evidence_status = "passed"
    elif required:
        evidence_status = "failed"
        blockers.append("%s decision is missing or unknown." % name)
    else:
        evidence_status = "warning"
        warnings.append("%s decision is missing or unknown." % name)

    for item in payload.get("blockers") or []:
        blockers.append("%s: %s" % (name, item))
    for item in payload.get("warnings") or []:
        warnings.append("%s: %s" % (name, item))

    if blockers:
        risk_level = "critical"
    elif warnings:
        risk_level = "medium"
    elif evidence_status == "skipped":
        risk_level = "low"
    else:
        risk_level = "low"

    message = "Evidence is %s." % evidence_status
    if release_risk:
        message = release_risk
    return {
        "name": name,
        "category": RISK_CATEGORIES.get(name, "Evidence"),
        "path": _repo_relative(path),
        "required": bool(required),
        "read_status": read_status,
        "exists": path.is_file(),
        "decision": decision,
        "ci_status": ci_status,
        "state": state,
        "closure_decision": closure_decision,
        "status": evidence_status,
        "score_value": _component_score(evidence_status),
        "risk_level": risk_level,
        "message": message,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
    }


def _scorecard_tsv(components):
    lines = ["component\tcategory\tstatus\trisk\tscore\tdecision\tci_status\tclosure_decision\trequired\tpath"]
    for component in components:
        lines.append(
            "%s\t%s\t%s\t%s\t%.2f\t%s\t%s\t%s\t%s\t%s"
            % (
                component["name"],
                component["category"],
                component["status"],
                component["risk_level"],
                component["score_value"],
                component["decision"] or "",
                component["ci_status"] or "",
                component["closure_decision"] or "",
                int(component["required"]),
                component["path"],
            )
        )
    return "\n".join(lines)


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append("%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source") or ""))
    return "\n".join(lines)


def _risk_level_rank(level):
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(level or "").lower(), 0)


def _risk_matrix_markdown(context, components, blockers, warnings):
    rows = [
        "| Component | Category | Status | Risk | Score | Decision | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for component in sorted(components, key=lambda item: (-_risk_level_rank(item["risk_level"]), item["name"])):
        rows.append(
            "| %s | %s | %s | %s | %.0f%% | %s/%s | `%s` |"
            % (
                component["name"],
                component["category"],
                component["status"],
                component["risk_level"],
                component["score_value"] * 100,
                component["decision"] or "missing",
                component["ci_status"] or "missing",
                component["path"],
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Evidence Bundle Risk Matrix

- Status: {context["decision"]}
- Score: {context["score_percent"]:.1f}%
- Minimum score: {context["minimum_score"]:.1f}%
- Release outcome: {context["release_outcome"] or "unknown"}
- Run ID: `{context["run_id"]}`
- Target environment: `{context["target_environment"]}`
- Generated: `{context["generated_at"]}`

## Risk Matrix

{chr(10).join(rows)}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}
"""


def _summary(context, blockers, warnings):
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Evidence Bundle Score

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Score: {context["score_percent"]:.1f}%
- Minimum score: {context["minimum_score"]:.1f}%
- Release outcome: {context["release_outcome"] or "unknown"}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Bundle score manifest: protected-evidence-bundle-score.json
- Release owner risk matrix: release-owner-risk-matrix.md
- Scorecard table: scorecard.tsv
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "score_percent=%.1f" % context["score_percent"],
            "minimum_score=%.1f" % context["minimum_score"],
            "release_outcome=%s" % (context["release_outcome"] or "<missing>"),
            "required_components=%s" % ",".join(context["required_components"]),
            "optional_components=%s" % (",".join(context["optional_components"]) or "<none>"),
            "fail_on_warning=%s" % int(context["fail_on_warning"]),
            "strict=%s" % int(context["strict"]),
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def _release_outcome(components):
    for name in [
        "protected-archive-upload-verification",
        "protected-release-archive",
        "protected-closure-result-verification",
        "protected-release-closure",
    ]:
        component = next((item for item in components if item["name"] == name), {})
        if component.get("closure_decision"):
            return component["closure_decision"]
    return ""


def main():
    parser = argparse.ArgumentParser(description="Export protected release evidence bundle score and risk matrix.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_BUNDLE_SCORE_OUTPUT", ""))
    parser.add_argument(
        "--required-components",
        default=os.environ.get("TIJARA_PROTECTED_BUNDLE_SCORE_REQUIRED_COMPONENTS", ",".join(DEFAULT_REQUIRED_COMPONENTS)),
    )
    parser.add_argument("--required-component", action="append", default=[])
    parser.add_argument(
        "--optional-components",
        default=os.environ.get("TIJARA_PROTECTED_BUNDLE_SCORE_OPTIONAL_COMPONENTS", ""),
    )
    parser.add_argument("--optional-component", action="append", default=[])
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument(
        "--minimum-score",
        default=os.environ.get("TIJARA_PROTECTED_BUNDLE_SCORE_MINIMUM", "90"),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_BUNDLE_SCORE_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_BUNDLE_SCORE_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-evidence-bundle-score" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    try:
        overrides = _component_overrides(args.component)
        rows.append({"name": "component-overrides", "status": "passed", "message": "%s override(s) parsed." % len(overrides), "source": ""})
    except ValueError as error:
        overrides = {}
        blockers.append(str(error))
        rows.append({"name": "component-overrides", "status": "failed", "message": str(error), "source": ""})
    try:
        metadata = _metadata_items(args.metadata)
        rows.append({"name": "metadata-format", "status": "passed", "message": "%s metadata item(s) parsed." % len(metadata), "source": ""})
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append({"name": "metadata-format", "status": "failed", "message": str(error), "source": ""})
    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append({"name": "metadata-secret-safety", "status": "failed", "message": message, "source": ""})
    else:
        rows.append({"name": "metadata-secret-safety", "status": "passed", "message": "No secret-like metadata keys found.", "source": ""})

    required_components = _dedupe(_csv_items(args.required_components) + args.required_component)
    optional_components = [
        item for item in _dedupe(_csv_items(args.optional_components) + args.optional_component) if item not in required_components
    ]
    component_names = _dedupe(required_components + optional_components + list(overrides))
    components = []
    for name in component_names:
        component = _component_review(name, _component_path(name, args.run_id, overrides), name in required_components)
        components.append(component)
        rows.append(
            {
                "name": "component-%s" % name,
                "status": component["status"] if component["status"] != "skipped" else "warning",
                "message": component["message"],
                "source": component["path"],
            }
        )
        blockers.extend(component["blockers"])
        warnings.extend(component["warnings"])

    scored = [component for component in components if component["required"] or component["exists"]]
    total = len(scored) or 1
    score_percent = round(sum(component["score_value"] for component in scored) / total * 100, 1)
    minimum_score = _as_float(args.minimum_score, 90.0)
    release_outcome = _release_outcome(components)
    if score_percent < minimum_score:
        blockers.append("Evidence bundle score %.1f%% is below required minimum %.1f%%." % (score_percent, minimum_score))
        rows.append({"name": "bundle-score-minimum", "status": "failed", "message": "Bundle score is below minimum.", "source": ""})
    else:
        rows.append({"name": "bundle-score-minimum", "status": "passed", "message": "Bundle score meets minimum.", "source": ""})
    if release_outcome == "blocked":
        blockers.append("Release outcome is blocked.")
        rows.append({"name": "release-outcome", "status": "failed", "message": "Release outcome is blocked.", "source": ""})
    elif release_outcome == "watch":
        warnings.append("Release outcome is watch.")
        rows.append({"name": "release-outcome", "status": "warning", "message": "Release outcome is watch.", "source": ""})
    elif release_outcome == "promotion_ready":
        rows.append({"name": "release-outcome", "status": "passed", "message": "Release outcome is promotion_ready.", "source": ""})
    elif strict:
        blockers.append("Release outcome is missing.")
        rows.append({"name": "release-outcome", "status": "failed", "message": "Release outcome is missing.", "source": ""})
    else:
        warnings.append("Release outcome is missing.")
        rows.append({"name": "release-outcome", "status": "warning", "message": "Release outcome is missing.", "source": ""})

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
        "required_components": required_components,
        "optional_components": optional_components,
        "score_percent": score_percent,
        "minimum_score": minimum_score,
        "release_outcome": release_outcome,
        "fail_on_warning": bool(args.fail_on_warning),
        "strict": strict,
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "score_percent": score_percent,
        "minimum_score": minimum_score,
        "release_outcome": release_outcome,
        "components": components,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-evidence-bundle-score.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "release-owner-risk-matrix.md", _risk_matrix_markdown(context, components, blockers, warnings))
    _write(output / "scorecard.tsv", _scorecard_tsv(components))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, blockers, warnings))
    print("Protected evidence bundle score written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    print("score_percent=%.1f" % score_percent)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
