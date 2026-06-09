#!/usr/bin/env python3
"""Export protected POS checkout/refund/print/offline replay matrix evidence."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PASS_DECISIONS = {"approved", "ok", "pass", "passed", "ready", "success"}
WARN_DECISIONS = {"pass_with_warnings", "skipped", "warn", "warning"}
FAIL_DECISIONS = {"blocked", "error", "fail", "failed"}
DEFAULT_REQUIRED_WORKFLOWS = ["checkout", "refund", "print", "offline-replay"]
REQUIRED_SPEC_FILES = {
    "pos-checkout-print.spec.mjs",
    "pos-enterprise-journey.spec.mjs",
    "refunds-reports.spec.mjs",
}
LOCAL_ENVIRONMENTS = {"ci", "dev", "development", "local", "local-strict-evidence", "test"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("protected-pos-matrix-%Y%m%dT%H%M%SZ")


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
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path):
    if not path:
        return ""
    try:
        return str(Path(path).resolve().relative_to(ROOT_DIR))
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message, source=""):
    return {
        "name": name,
        "status": status,
        "message": message,
        "source": _repo_relative(source) if source else "",
    }


def _decision_state(payload):
    decision = str(payload.get("decision") or payload.get("status") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in FAIL_DECISIONS or ci_status in FAIL_DECISIONS:
        return "failed"
    if decision in WARN_DECISIONS or ci_status in WARN_DECISIONS:
        return "warning"
    if decision in PASS_DECISIONS or ci_status in PASS_DECISIONS:
        return "passed"
    return "unknown"


def _playwright_stats(payload):
    stats = payload.get("stats") if isinstance(payload, dict) else {}
    counts = {
        "expected": int((stats or {}).get("expected") or 0),
        "unexpected": int((stats or {}).get("unexpected") or 0),
        "flaky": int((stats or {}).get("flaky") or 0),
        "skipped": int((stats or {}).get("skipped") or 0),
        "interrupted": int((stats or {}).get("interrupted") or 0),
    }

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for spec in node.get("specs") or []:
            for test in spec.get("tests") or []:
                statuses = {
                    str(result.get("status") or "").lower()
                    for result in test.get("results") or []
                    if isinstance(result, dict)
                }
                if statuses.intersection({"failed", "interrupted", "timedout"}):
                    counts["unexpected"] += 1
        for child in node.get("suites") or []:
            walk(child)

    if not stats:
        walk(payload.get("suites") if isinstance(payload, dict) else [])
    return counts


def _spec_status(spec):
    statuses = []
    outcomes = []
    for test in spec.get("tests") or []:
        if test.get("outcome"):
            outcomes.append(str(test.get("outcome") or "").lower())
        for result in test.get("results") or []:
            if isinstance(result, dict):
                statuses.append(str(result.get("status") or "").lower())
    status_set = set(statuses + outcomes)
    if status_set.intersection({"failed", "interrupted", "timedout", "unexpected"}):
        return "failed"
    if status_set and status_set.issubset({"skipped"}):
        return "skipped"
    if status_set.intersection({"expected", "passed"}):
        return "passed"
    return "unknown"


def _playwright_specs(payload):
    specs = []

    def walk(node, current_file=""):
        if isinstance(node, list):
            for item in node:
                walk(item, current_file=current_file)
            return
        if not isinstance(node, dict):
            return
        file_name = str(node.get("file") or current_file or "")
        for spec in node.get("specs") or []:
            spec_file = str(spec.get("file") or file_name)
            title = str(spec.get("title") or "").strip()
            status = _spec_status(spec)
            specs.append(
                {
                    "file": spec_file,
                    "title": title,
                    "status": status,
                    "haystack": ("%s %s" % (spec_file, title)).lower(),
                }
            )
        for child in node.get("suites") or []:
            walk(child, current_file=file_name)

    if payload:
        walk(payload.get("suites") if isinstance(payload, dict) else payload)
    return specs


def _workflow_matches(workflow, spec):
    haystack = spec.get("haystack", "")
    file_name = spec.get("file", "")
    if spec.get("status") != "passed":
        return False
    if file_name == "pos-enterprise-journey.spec.mjs" and "enterprise pos journey" in haystack:
        return True
    if workflow == "checkout":
        return any(
            phrase in haystack
            for phrase in [
                "pos checkout",
                "checkout shell",
                "cashier pos ui search",
                "cart, payment",
                "paid browser order",
            ]
        )
    if workflow == "refund":
        return any(phrase in haystack for phrase in ["refund", "invoice barcode"])
    if workflow == "print":
        return any(phrase in haystack for phrase in ["print", "receipt print", "receipt or invoice report"])
    if workflow == "offline-replay":
        return (
            ("offline" in haystack and "replay" in haystack)
            or "replay audit" in haystack
            or "duplicate" in haystack
        )
    return False


def _workflow_reviews(required_workflows, specs):
    reviews = []
    proven = []
    for workflow in required_workflows:
        proofs = [
            {
                "file": spec["file"],
                "title": spec["title"],
                "status": spec["status"],
            }
            for spec in specs
            if _workflow_matches(workflow, spec)
        ]
        skipped = [
            {
                "file": spec["file"],
                "title": spec["title"],
                "status": spec["status"],
            }
            for spec in specs
            if spec["status"] == "skipped" and workflow.replace("-", " ") in spec["haystack"]
        ]
        status = "passed" if proofs else "failed"
        if proofs:
            proven.append(workflow)
        reviews.append(
            {
                "workflow": workflow,
                "status": status,
                "proof_count": len(proofs),
                "proofs": proofs,
                "skipped_candidates": skipped,
            }
        )
    return reviews, proven


def _readiness_review(path):
    payload = _read_json(path)
    if not payload:
        return {"present": False, "state": "missing", "blockers": ["E2E readiness evidence is missing."]}
    specs = [str(item or "") for item in payload.get("specs") or []]
    spec_files = {Path(item).name for item in specs}
    missing_specs = sorted(REQUIRED_SPEC_FILES - spec_files)
    variables = payload.get("required_variables") or []
    missing_variables = [item.get("name", "") for item in variables if not item.get("present")]
    blockers = []
    warnings = []
    state = _decision_state(payload)
    if state == "failed":
        blockers.append("E2E readiness decision is %s/%s." % (payload.get("decision", ""), payload.get("ci_status", "")))
    elif state == "warning":
        warnings.append("E2E readiness has warnings.")
    elif state == "unknown":
        warnings.append("E2E readiness decision is unknown.")
    if missing_specs:
        blockers.append("E2E readiness is missing required POS specs: %s." % ", ".join(missing_specs))
    if missing_variables:
        blockers.append("E2E readiness is missing required variables: %s." % ", ".join(missing_variables))
    return {
        "present": True,
        "state": state,
        "decision": payload.get("decision", ""),
        "ci_status": payload.get("ci_status", ""),
        "specs": specs,
        "missing_required_specs": missing_specs,
        "missing_variables": missing_variables,
        "enabled_optional_flags": [
            item.get("name", "") for item in payload.get("optional_flags") or [] if item.get("enabled")
        ],
        "blockers": blockers,
        "warnings": warnings,
    }


def _execution_review(path):
    payload = _read_json(path)
    if not payload:
        return {"present": False, "state": "missing", "blockers": ["E2E execution evidence is missing."]}
    state = _decision_state(payload)
    blockers = []
    warnings = []
    if state == "failed":
        blockers.append("E2E execution evidence is %s/%s." % (payload.get("decision", ""), payload.get("ci_status", "")))
    elif state == "warning":
        warnings.append("E2E execution evidence has warnings.")
    elif state == "unknown":
        warnings.append("E2E execution decision is unknown.")
    blockers.extend(payload.get("blockers") or [])
    warnings.extend(payload.get("warnings") or [])
    return {
        "present": True,
        "state": state,
        "decision": payload.get("decision", ""),
        "ci_status": payload.get("ci_status", ""),
        "context": payload.get("context") or {},
        "blockers": blockers,
        "warnings": warnings,
    }


def _supporting_review(label, path, required=False):
    payload = _read_json(path)
    if not payload:
        message = "%s evidence is missing." % label
        return {
            "present": False,
            "state": "missing",
            "decision": "",
            "ci_status": "",
            "blockers": [message] if required else [],
            "warnings": [] if required else [message],
        }
    state = _decision_state(payload)
    blockers = []
    warnings = []
    if state == "failed":
        blockers.append("%s evidence is %s/%s." % (label, payload.get("decision", ""), payload.get("ci_status", "")))
    elif state == "warning":
        warnings.append("%s evidence has warnings." % label)
    elif state == "unknown":
        warnings.append("%s evidence decision is unknown." % label)
    blockers.extend(payload.get("blockers") or [])
    warnings.extend(payload.get("warnings") or [])
    return {
        "present": True,
        "state": state,
        "decision": payload.get("decision", ""),
        "ci_status": payload.get("ci_status", ""),
        "blockers": blockers,
        "warnings": warnings,
    }


def _orchestration_review(path):
    if not path or not path.is_file():
        return {"present": False, "failed_steps": [], "warnings": ["Protected E2E orchestration status is missing."], "blockers": []}
    failed_steps = []
    skipped_steps = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"present": False, "failed_steps": [], "warnings": [], "blockers": ["Protected E2E orchestration status could not be read."]}
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2 or parts[0] in {"name", "check"}:
            continue
        if parts[1] in {"failed", "blocked", "error"}:
            failed_steps.append(parts[0])
        elif parts[1] in {"skipped", "warning"}:
            skipped_steps.append(parts[0])
    return {
        "present": True,
        "failed_steps": failed_steps,
        "skipped_or_warning_steps": skipped_steps,
        "blockers": ["Protected E2E orchestration failed steps: %s." % ", ".join(failed_steps)] if failed_steps else [],
        "warnings": ["Protected E2E orchestration skipped/warning steps: %s." % ", ".join(skipped_steps)] if skipped_steps else [],
    }


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s"
            % (row["name"], row["status"], row["message"], row.get("source") or "")
        )
    return "\n".join(lines)


def _env_summary(context):
    return "\n".join(
        [
            "run_id=%s" % context["run_id"],
            "target_environment=%s" % context["target_environment"],
            "strict=%s" % int(context["strict"]),
            "fail_on_warning=%s" % int(context["fail_on_warning"]),
            "allow_local_evidence=%s" % int(context["allow_local_evidence"]),
            "require_browser_matrix=%s" % int(context["require_browser_matrix"]),
            "required_workflows=%s" % ",".join(context["required_workflows"]),
            "output=%s" % context["output"],
            "e2e_evidence_dir=%s" % context["evidence_paths"]["e2e_evidence_dir"],
            "playwright_json=%s" % context["evidence_paths"]["playwright_json"],
            "execution_evidence=%s" % context["evidence_paths"]["execution_evidence"],
            "browser_matrix_evidence=%s" % context["evidence_paths"]["browser_matrix_evidence"],
            "offline_replay_evidence=%s" % context["evidence_paths"]["offline_replay_evidence"],
            "offline_pilot_evidence=%s" % context["evidence_paths"]["offline_pilot_evidence"],
            "orchestration_status=%s" % context["evidence_paths"]["orchestration_status"],
        ]
    )


def _summary(context, workflow_reviews, blockers, warnings):
    status = "blocked" if blockers else "warning" if warnings else "ready"
    workflow_lines = "\n".join(
        "- `%s`: %s, proofs=%s"
        % (review["workflow"], review["status"], review["proof_count"])
        for review in workflow_reviews
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected POS Matrix Evidence

- Status: {status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Strict: {context["strict"]}
- Fail on warning: {context["fail_on_warning"]}
- Required workflows: {", ".join(context["required_workflows"])}
- Proven workflows: {", ".join(context["proven_workflows"]) or "none"}

## Workflow Matrix

{workflow_lines or "- No workflows were evaluated."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Matrix JSON: protected-pos-matrix-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export protected POS workflow matrix evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_RUN_ID", os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id())))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_OUTPUT", ""))
    parser.add_argument("--e2e-evidence-dir", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_E2E_DIR", ""))
    parser.add_argument("--execution-evidence", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_EXECUTION_EVIDENCE", ""))
    parser.add_argument("--browser-matrix-evidence", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_BROWSER_MATRIX", ""))
    parser.add_argument("--offline-replay-evidence", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_OFFLINE_REPLAY", ""))
    parser.add_argument("--offline-pilot-evidence", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_OFFLINE_PILOT", ""))
    parser.add_argument("--orchestration-status", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_ORCH_STATUS", ""))
    parser.add_argument("--required-workflow", action="append", default=[])
    parser.add_argument("--required-workflows", default=os.environ.get("TIJARA_PROTECTED_POS_MATRIX_REQUIRED_WORKFLOWS", ",".join(DEFAULT_REQUIRED_WORKFLOWS)))
    parser.add_argument("--strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_POS_MATRIX_STRICT", "0")))
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_POS_MATRIX_FAIL_ON_WARNING", "0")))
    parser.add_argument("--allow-local-evidence", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_POS_MATRIX_ALLOW_LOCAL", "0")))
    parser.add_argument("--require-browser-matrix", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_POS_MATRIX_REQUIRE_BROWSER_MATRIX", "1")))
    parser.add_argument("--no-require-browser-matrix", action="store_true")
    args = parser.parse_args()
    if args.no_require_browser_matrix:
        args.require_browser_matrix = False

    output = _resolve(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-pos-matrix" / args.run_id
    e2e_dir = _resolve(args.e2e_evidence_dir) if args.e2e_evidence_dir else ROOT_DIR / "deploy/runtime/e2e-evidence" / args.run_id
    readiness_path = e2e_dir / "e2e-readiness.json"
    playwright_path = e2e_dir / "playwright-results.json"
    execution_path = _resolve(args.execution_evidence) if args.execution_evidence else ROOT_DIR / "deploy/runtime/e2e-execution" / args.run_id / "e2e-execution-evidence.json"
    browser_matrix_path = _resolve(args.browser_matrix_evidence) if args.browser_matrix_evidence else ROOT_DIR / "deploy/runtime/browser-e2e-matrix" / args.run_id / "browser-e2e-matrix-evidence.json"
    offline_replay_path = _resolve(args.offline_replay_evidence) if args.offline_replay_evidence else ROOT_DIR / "deploy/runtime/protected-offline-replay" / args.run_id / "protected-offline-replay-evidence.json"
    offline_pilot_path = _resolve(args.offline_pilot_evidence) if args.offline_pilot_evidence else ROOT_DIR / "deploy/runtime/protected-offline-pilot" / args.run_id / "offline-pos-pilot-evidence.json"
    orchestration_path = _resolve(args.orchestration_status) if args.orchestration_status else ROOT_DIR / "deploy/runtime/protected-e2e" / args.run_id / "status.tsv"
    output.mkdir(parents=True, exist_ok=True)

    required_workflows = _dedupe(_csv_items(args.required_workflows) + args.required_workflow) or DEFAULT_REQUIRED_WORKFLOWS
    blockers = []
    warnings = []
    rows = []

    target_value = str(args.target_environment or "").strip().lower()
    if args.strict and target_value in LOCAL_ENVIRONMENTS and not args.allow_local_evidence:
        blockers.append("Strict protected POS matrix cannot use local/CI evidence without --allow-local-evidence.")
        rows.append(_row("target-environment", "failed", "Local evidence rejected in strict mode.", ""))
    else:
        rows.append(_row("target-environment", "passed", "Target environment accepted.", ""))

    playwright_payload = _read_json(playwright_path)
    if not playwright_payload:
        blockers.append("Playwright result JSON is missing.")
        rows.append(_row("playwright-json", "failed", "Playwright result JSON is missing.", playwright_path))
        specs = []
        playwright_counts = {}
    else:
        playwright_counts = _playwright_stats(playwright_payload)
        specs = _playwright_specs(playwright_payload)
        if playwright_counts.get("unexpected", 0) or playwright_counts.get("interrupted", 0):
            blockers.append(
                "Playwright unexpected/interrupted counts are %s/%s."
                % (playwright_counts.get("unexpected", 0), playwright_counts.get("interrupted", 0))
            )
            rows.append(_row("playwright-status", "failed", "Playwright reported unexpected/interrupted tests.", playwright_path))
        else:
            rows.append(_row("playwright-status", "passed", "Playwright has no unexpected/interrupted tests.", playwright_path))

    workflow_reviews, proven_workflows = _workflow_reviews(required_workflows, specs)
    for review in workflow_reviews:
        if review["status"] == "passed":
            rows.append(_row("workflow-%s" % review["workflow"], "passed", "%s proof(s) found." % review["proof_count"], playwright_path))
        else:
            message = "Required POS workflow has no passed authenticated proof: %s." % review["workflow"]
            blockers.append(message)
            rows.append(_row("workflow-%s" % review["workflow"], "failed", message, playwright_path))

    readiness = _readiness_review(readiness_path)
    rows.append(
        _row(
            "e2e-readiness",
            "passed" if readiness.get("state") == "passed" else "failed" if readiness.get("blockers") else "warning",
            "E2E readiness state is %s." % readiness.get("state", "missing"),
            readiness_path,
        )
    )
    blockers.extend(readiness.get("blockers") or [])
    warnings.extend(readiness.get("warnings") or [])

    execution = _execution_review(execution_path)
    rows.append(
        _row(
            "e2e-execution",
            "passed" if execution.get("state") == "passed" else "failed" if execution.get("blockers") else "warning",
            "E2E execution state is %s." % execution.get("state", "missing"),
            execution_path,
        )
    )
    blockers.extend(execution.get("blockers") or [])
    warnings.extend(execution.get("warnings") or [])

    browser_matrix = _supporting_review("Browser E2E matrix", browser_matrix_path, required=args.require_browser_matrix and args.strict)
    rows.append(
        _row(
            "browser-e2e-matrix",
            "passed" if browser_matrix.get("state") == "passed" else "failed" if browser_matrix.get("blockers") else "warning",
            "Browser matrix state is %s." % browser_matrix.get("state", "missing"),
            browser_matrix_path,
        )
    )
    blockers.extend(browser_matrix.get("blockers") or [])
    warnings.extend(browser_matrix.get("warnings") or [])

    offline_replay = _supporting_review("Protected offline replay", offline_replay_path, required=False)
    rows.append(
        _row(
            "protected-offline-replay",
            "passed" if offline_replay.get("state") == "passed" else "failed" if offline_replay.get("blockers") else "warning",
            "Offline replay evidence state is %s." % offline_replay.get("state", "missing"),
            offline_replay_path,
        )
    )
    blockers.extend(offline_replay.get("blockers") or [])
    warnings.extend(offline_replay.get("warnings") or [])

    offline_pilot = _supporting_review("Protected offline pilot", offline_pilot_path, required=False)
    rows.append(
        _row(
            "protected-offline-pilot",
            "passed" if offline_pilot.get("state") == "passed" else "failed" if offline_pilot.get("blockers") else "warning",
            "Offline pilot evidence state is %s." % offline_pilot.get("state", "missing"),
            offline_pilot_path,
        )
    )
    blockers.extend(offline_pilot.get("blockers") or [])
    warnings.extend(offline_pilot.get("warnings") or [])

    orchestration = _orchestration_review(orchestration_path)
    rows.append(
        _row(
            "protected-e2e-orchestration",
            "failed" if orchestration.get("blockers") else "warning" if orchestration.get("warnings") else "passed",
            "Protected E2E orchestration reviewed.",
            orchestration_path,
        )
    )
    blockers.extend(orchestration.get("blockers") or [])
    warnings.extend(orchestration.get("warnings") or [])

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
        decision = "ready"
        ci_status = "pass"

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": _repo_relative(output),
        "strict": bool(args.strict),
        "fail_on_warning": bool(args.fail_on_warning),
        "allow_local_evidence": bool(args.allow_local_evidence),
        "require_browser_matrix": bool(args.require_browser_matrix),
        "required_workflows": required_workflows,
        "proven_workflows": proven_workflows,
        "evidence_paths": {
            "e2e_evidence_dir": _repo_relative(e2e_dir),
            "playwright_json": _repo_relative(playwright_path),
            "readiness_evidence": _repo_relative(readiness_path),
            "execution_evidence": _repo_relative(execution_path),
            "browser_matrix_evidence": _repo_relative(browser_matrix_path),
            "offline_replay_evidence": _repo_relative(offline_replay_path),
            "offline_pilot_evidence": _repo_relative(offline_pilot_path),
            "orchestration_status": _repo_relative(orchestration_path),
        },
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "required_workflows": required_workflows,
        "proven_workflows": proven_workflows,
        "workflow_reviews": workflow_reviews,
        "playwright": {
            "stats": playwright_counts,
            "passed_spec_count": len([item for item in specs if item["status"] == "passed"]),
            "skipped_spec_count": len([item for item in specs if item["status"] == "skipped"]),
            "failed_spec_count": len([item for item in specs if item["status"] == "failed"]),
        },
        "evidence_reviews": {
            "readiness": readiness,
            "execution": execution,
            "browser_matrix": browser_matrix,
            "offline_replay": offline_replay,
            "offline_pilot": offline_pilot,
            "orchestration": orchestration,
        },
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }

    _write(output / "protected-pos-matrix-evidence.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, workflow_reviews, blockers, warnings))

    print("Protected POS matrix evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
