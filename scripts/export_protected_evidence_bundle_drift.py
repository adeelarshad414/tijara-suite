#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PASS_DECISIONS = {"passed", "pass", "success", "ok", "promotion_ready", "approved", "ready"}
WARNING_DECISIONS = {"warning", "warn", "watch", "pass_with_warnings"}
FAILING_DECISIONS = {"failed", "fail", "blocked", "error"}
STATUS_RANKS = {
    "passed": 1,
    "pass": 1,
    "success": 1,
    "ok": 1,
    "warning": 2,
    "warn": 2,
    "skipped": 2,
    "failed": 3,
    "fail": 3,
    "blocked": 3,
    "missing": 4,
    "error": 4,
}
RELEASE_OUTCOME_RANKS = {
    "promotion_ready": 1,
    "watch": 2,
    "blocked": 3,
    "missing": 4,
    "": 4,
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve(path):
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path):
    if not path:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _read_json(path):
    target = _resolve(path)
    if not target:
        return {}, "missing_path", None
    if not target.is_file():
        return {}, "missing", target
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, "read_error:%s" % error, target
    if not isinstance(payload, dict):
        return {}, "read_error:json-root-is-not-object", target
    return payload, "ok", target


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


def _dedupe(items):
    clean = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            clean.append(value)
    return clean


def _as_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _decision_rank(value):
    lowered = str(value or "").strip().lower()
    if lowered in FAILING_DECISIONS:
        return 3
    if lowered in WARNING_DECISIONS:
        return 2
    if lowered in PASS_DECISIONS:
        return 1
    return 4


def _status_rank(value):
    return STATUS_RANKS.get(str(value or "").strip().lower(), 4)


def _release_outcome_rank(value):
    return RELEASE_OUTCOME_RANKS.get(str(value or "").strip().lower(), 4)


def _components_by_name(payload):
    components = {}
    for component in payload.get("components") or []:
        if not isinstance(component, dict):
            continue
        name = str(component.get("name") or "").strip()
        if name:
            components[name] = component
    return components


def _score(payload):
    return _as_float(payload.get("score_percent"), 0.0)


def _top_items(payload, field):
    items = ["bundle: %s" % item for item in payload.get(field) or []]
    for component in payload.get("components") or []:
        if not isinstance(component, dict):
            continue
        name = str(component.get("name") or "component").strip()
        for item in component.get(field) or []:
            items.append("%s: %s" % (name, item))
    return _dedupe(items)


def _comparison_table(rows):
    lines = ["item\tbaseline\tcurrent\tstatus\tmessage"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s\t%s"
            % (
                row["item"],
                row.get("baseline") or "",
                row.get("current") or "",
                row["status"],
                row["message"],
            )
        )
    return "\n".join(lines)


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append("%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source") or ""))
    return "\n".join(lines)


def _drift_report(context, comparisons, blockers, warnings, resolved):
    comparison_rows = [
        "| Item | Baseline | Current | Status | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in comparisons:
        comparison_rows.append(
            "| %s | %s | %s | %s | %s |"
            % (
                str(row["item"]).replace("|", "\\|"),
                str(row.get("baseline") or "").replace("|", "\\|"),
                str(row.get("current") or "").replace("|", "\\|"),
                row["status"],
                str(row["message"]).replace("|", "\\|"),
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    resolved_lines = "\n".join("- %s" % item for item in resolved) or "- None"
    return f"""
# Protected Evidence Bundle Drift Report

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: `{context["run_id"]}`
- Target environment: `{context["target_environment"]}`
- Current score: {context["current_score"]:.1f}%
- Baseline score: {context["baseline_score_display"]}
- Score delta: {context["score_delta_display"]}
- Score drop threshold: {context["score_drop_threshold"]:.1f}%
- Baseline required: {int(context["baseline_required"])}
- Generated: `{context["generated_at"]}`

## Drift Checks

{chr(10).join(comparison_rows)}

## New Blockers

{blocker_lines}

## New Warnings

{warning_lines}

## Resolved Baseline Issues

{resolved_lines}
"""


def _summary(context, blockers, warnings, resolved):
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    resolved_lines = "\n".join("- %s" % item for item in resolved[:12]) or "- None"
    return f"""
# Protected Evidence Bundle Drift

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Current score: {context["current_score"]:.1f}%
- Baseline score: {context["baseline_score_display"]}
- Score delta: {context["score_delta_display"]}
- Output directory: {context["output"]}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Resolved Baseline Issues

{resolved_lines}

## Evidence Files

- Drift manifest: protected-evidence-bundle-drift.json
- Drift report: drift-report.md
- Comparison table: comparison.tsv
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _env_summary(context):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "current_score=%.1f" % context["current_score"],
            "baseline_score=%s" % context["baseline_score_display"],
            "score_delta=%s" % context["score_delta_display"],
            "score_drop_threshold=%.1f" % context["score_drop_threshold"],
            "baseline_required=%s" % int(context["baseline_required"]),
            "allow_missing_baseline=%s" % int(context["allow_missing_baseline"]),
            "fail_on_warning=%s" % int(context["fail_on_warning"]),
            "strict=%s" % int(context["strict"]),
            "decision=%s" % context["decision"],
            "ci_status=%s" % context["ci_status"],
        ]
    )


def _compare_scores(current, baseline, threshold, comparisons, blockers, warnings, rows):
    current_score = _score(current)
    baseline_score = _score(baseline)
    delta = round(current_score - baseline_score, 1)
    drop = round(baseline_score - current_score, 1)
    if drop > threshold:
        message = "Current score dropped %.1f%% from baseline, above %.1f%% threshold." % (drop, threshold)
        blockers.append(message)
        status = "failed"
    elif drop > 0:
        message = "Current score dropped %.1f%% from baseline." % drop
        warnings.append(message)
        status = "warning"
    else:
        message = "Current score did not regress."
        status = "passed"
    comparisons.append(
        {
            "item": "score_percent",
            "baseline": "%.1f%%" % baseline_score,
            "current": "%.1f%%" % current_score,
            "status": status,
            "message": message,
        }
    )
    rows.append({"name": "score-drift", "status": status, "message": message, "source": ""})
    return baseline_score, current_score, delta


def _compare_decision(field, current, baseline, comparisons, blockers, warnings, rows):
    baseline_value = str(baseline.get(field) or "").strip()
    current_value = str(current.get(field) or "").strip()
    baseline_rank = _decision_rank(baseline_value)
    current_rank = _decision_rank(current_value)
    if current_rank > baseline_rank:
        message = "%s regressed from %s to %s." % (field, baseline_value or "missing", current_value or "missing")
        if current_rank >= 3:
            blockers.append(message)
            status = "failed"
        else:
            warnings.append(message)
            status = "warning"
    else:
        message = "%s did not regress." % field
        status = "passed"
    comparisons.append(
        {
            "item": field,
            "baseline": baseline_value or "missing",
            "current": current_value or "missing",
            "status": status,
            "message": message,
        }
    )
    rows.append({"name": "%s-drift" % field.replace("_", "-"), "status": status, "message": message, "source": ""})


def _compare_release_outcome(current, baseline, comparisons, blockers, warnings, rows):
    baseline_value = str(baseline.get("release_outcome") or "").strip()
    current_value = str(current.get("release_outcome") or "").strip()
    baseline_rank = _release_outcome_rank(baseline_value)
    current_rank = _release_outcome_rank(current_value)
    if current_rank > baseline_rank:
        message = "Release outcome regressed from %s to %s." % (baseline_value or "missing", current_value or "missing")
        if current_value == "blocked" or current_rank >= 3:
            blockers.append(message)
            status = "failed"
        else:
            warnings.append(message)
            status = "warning"
    else:
        message = "Release outcome did not regress."
        status = "passed"
    comparisons.append(
        {
            "item": "release_outcome",
            "baseline": baseline_value or "missing",
            "current": current_value or "missing",
            "status": status,
            "message": message,
        }
    )
    rows.append({"name": "release-outcome-drift", "status": status, "message": message, "source": ""})


def _compare_components(current, baseline, comparisons, blockers, warnings, resolved, rows):
    current_components = _components_by_name(current)
    baseline_components = _components_by_name(baseline)
    for name in sorted(set(current_components) | set(baseline_components)):
        current_component = current_components.get(name)
        baseline_component = baseline_components.get(name)
        if baseline_component and not current_component:
            message = "%s existed in baseline but is missing from current bundle score." % name
            blockers.append(message)
            comparisons.append(
                {
                    "item": "component:%s" % name,
                    "baseline": baseline_component.get("status") or "present",
                    "current": "missing",
                    "status": "failed",
                    "message": message,
                }
            )
            rows.append({"name": "component-%s-drift" % name, "status": "failed", "message": message, "source": ""})
            continue
        if current_component and not baseline_component:
            message = "%s is new in the current bundle score." % name
            warnings.append(message)
            comparisons.append(
                {
                    "item": "component:%s" % name,
                    "baseline": "missing",
                    "current": current_component.get("status") or "present",
                    "status": "warning",
                    "message": message,
                }
            )
            rows.append({"name": "component-%s-drift" % name, "status": "warning", "message": message, "source": ""})
            continue
        baseline_status = str(baseline_component.get("status") or "").strip()
        current_status = str(current_component.get("status") or "").strip()
        if _status_rank(current_status) > _status_rank(baseline_status):
            message = "%s status regressed from %s to %s." % (name, baseline_status or "missing", current_status or "missing")
            if _status_rank(current_status) >= 3:
                blockers.append(message)
                status = "failed"
            else:
                warnings.append(message)
                status = "warning"
        else:
            message = "%s status did not regress." % name
            status = "passed"
        comparisons.append(
            {
                "item": "component:%s" % name,
                "baseline": baseline_status or "missing",
                "current": current_status or "missing",
                "status": status,
                "message": message,
            }
        )
        rows.append({"name": "component-%s-drift" % name, "status": status, "message": message, "source": current_component.get("path", "")})

        baseline_blockers = set(str(item) for item in baseline_component.get("blockers") or [])
        current_blockers = set(str(item) for item in current_component.get("blockers") or [])
        for item in sorted(current_blockers - baseline_blockers):
            blockers.append("%s new blocker: %s" % (name, item))
        for item in sorted(baseline_blockers - current_blockers):
            resolved.append("%s resolved blocker: %s" % (name, item))

        baseline_warnings = set(str(item) for item in baseline_component.get("warnings") or [])
        current_warnings = set(str(item) for item in current_component.get("warnings") or [])
        for item in sorted(current_warnings - baseline_warnings):
            warnings.append("%s new warning: %s" % (name, item))
        for item in sorted(baseline_warnings - current_warnings):
            resolved.append("%s resolved warning: %s" % (name, item))


def _compare_top_items(current, baseline, blockers, warnings, resolved):
    baseline_blockers = set(_top_items(baseline, "blockers"))
    current_blockers = set(_top_items(current, "blockers"))
    for item in sorted(current_blockers - baseline_blockers):
        blockers.append("New blocker since baseline: %s" % item)
    for item in sorted(baseline_blockers - current_blockers):
        resolved.append("Resolved blocker since baseline: %s" % item)

    baseline_warnings = set(_top_items(baseline, "warnings"))
    current_warnings = set(_top_items(current, "warnings"))
    for item in sorted(current_warnings - baseline_warnings):
        warnings.append("New warning since baseline: %s" % item)
    for item in sorted(baseline_warnings - current_warnings):
        resolved.append("Resolved warning since baseline: %s" % item)


def main():
    parser = argparse.ArgumentParser(description="Compare current protected evidence bundle score against a baseline.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_OUTPUT", ""))
    parser.add_argument("--current-score", default=os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_CURRENT_SCORE", ""))
    parser.add_argument("--baseline-score", default=os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_BASELINE_SCORE", ""))
    parser.add_argument(
        "--score-drop-threshold",
        default=os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_SCORE_DROP_THRESHOLD", "5"),
    )
    parser.add_argument(
        "--allow-missing-baseline",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_ALLOW_MISSING_BASELINE", "0")),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_FAIL_ON_WARNING", "0")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROTECTED_BUNDLE_DRIFT_NON_STRICT", "0")),
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--metadata", action="append", default=[])
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-evidence-bundle-drift" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    if not args.current_score:
        args.current_score = "deploy/runtime/protected-evidence-bundle-score/%s/protected-evidence-bundle-score.json" % args.run_id

    rows = []
    comparisons = []
    blockers = []
    warnings = []
    resolved = []
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

    current, current_status, current_path = _read_json(args.current_score)
    baseline, baseline_status, baseline_path = _read_json(args.baseline_score)
    if current_status != "ok":
        message = "Current bundle score is not readable: %s." % current_status
        blockers.append(message)
        rows.append({"name": "current-score-source", "status": "failed", "message": message, "source": _repo_relative(current_path)})
    else:
        rows.append({"name": "current-score-source", "status": "passed", "message": "Current score source is readable.", "source": _repo_relative(current_path)})

    baseline_required = strict and not args.allow_missing_baseline
    baseline_available = baseline_status == "ok"
    if baseline_available:
        rows.append({"name": "baseline-score-source", "status": "passed", "message": "Baseline score source is readable.", "source": _repo_relative(baseline_path)})
    elif baseline_required:
        message = "Baseline bundle score is required but not readable: %s." % baseline_status
        blockers.append(message)
        rows.append({"name": "baseline-score-source", "status": "failed", "message": message, "source": _repo_relative(baseline_path)})
    else:
        message = "Baseline bundle score is not available; drift comparison is recorded as first-run/watch evidence."
        warnings.append(message)
        rows.append({"name": "baseline-score-source", "status": "warning", "message": message, "source": _repo_relative(baseline_path)})

    score_drop_threshold = _as_float(args.score_drop_threshold, 5.0)
    current_score = _score(current) if current_status == "ok" else 0.0
    baseline_score = _score(baseline) if baseline_available else 0.0
    score_delta = None
    if current_status == "ok" and baseline_available:
        baseline_score, current_score, score_delta = _compare_scores(
            current, baseline, score_drop_threshold, comparisons, blockers, warnings, rows
        )
        _compare_decision("decision", current, baseline, comparisons, blockers, warnings, rows)
        _compare_decision("ci_status", current, baseline, comparisons, blockers, warnings, rows)
        _compare_release_outcome(current, baseline, comparisons, blockers, warnings, rows)
        _compare_components(current, baseline, comparisons, blockers, warnings, resolved, rows)
        _compare_top_items(current, baseline, blockers, warnings, resolved)

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    resolved = _dedupe(resolved)
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
        "current_score_path": _repo_relative(current_path),
        "baseline_score_path": _repo_relative(baseline_path),
        "current_score": current_score,
        "baseline_score": baseline_score if baseline_available else None,
        "baseline_score_display": "%.1f%%" % baseline_score if baseline_available else "missing",
        "score_delta": score_delta,
        "score_delta_display": "%.1f%%" % score_delta if score_delta is not None else "n/a",
        "score_drop_threshold": score_drop_threshold,
        "baseline_required": baseline_required,
        "allow_missing_baseline": bool(args.allow_missing_baseline),
        "fail_on_warning": bool(args.fail_on_warning),
        "strict": strict,
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "current_score": current_score,
        "baseline_score": baseline_score if baseline_available else None,
        "score_delta": score_delta,
        "score_drop_threshold": score_drop_threshold,
        "comparisons": comparisons,
        "blockers": blockers,
        "warnings": warnings,
        "resolved": resolved,
        "checks": rows,
        "metadata": metadata,
    }
    _write(output / "protected-evidence-bundle-drift.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "drift-report.md", _drift_report(context, comparisons, blockers, warnings, resolved))
    _write(output / "comparison.tsv", _comparison_table(comparisons))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, blockers, warnings, resolved))
    print("Protected evidence bundle drift written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    print("current_score=%.1f" % current_score)
    print("baseline_score=%s" % ("%.1f" % baseline_score if baseline_available else "missing"))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
