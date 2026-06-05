#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_json(path):
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_summary_fields(path):
    fields = {}
    if not path or not path.is_file():
        return fields
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return fields
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        label, separator, value = stripped[2:].partition(":")
        if separator:
            fields[label.strip()] = value.strip()
    return fields


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s"
            % (row["name"], row["status"], row["message"], row.get("source") or "")
        )
    return "\n".join(lines)


def _env_summary(context):
    lines = [
        "run_id=%s" % context["run_id"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "strict=%s" % context["strict"],
        "seed_evidence=%s" % (context["seed_evidence"] or "<unset>"),
        "profile_evidence=%s" % (context["profile_evidence"] or "<unset>"),
        "e2e_evidence_dir=%s" % (context["e2e_evidence_dir"] or "<unset>"),
        "readiness_evidence=%s" % (context["readiness_evidence"] or "<unset>"),
        "playwright_json=%s" % (context["playwright_json"] or "<unset>"),
        "e2e_summary=%s" % (context["e2e_summary"] or "<unset>"),
        "signoff_readiness=%s" % (context["signoff_readiness"] or "<unset>"),
        "orchestration_status=%s" % (context["orchestration_status"] or "<unset>"),
    ]
    return "\n".join(lines)


def _summary(context, rows, blockers, warnings, reviews):
    status = "blocked" if blockers else "warning" if warnings else "ready"
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    review_lines = []
    for key in [
        "seed",
        "profile",
        "readiness",
        "e2e_summary",
        "playwright",
        "signoff",
        "orchestration",
    ]:
        review = reviews.get(key) or {}
        if not review:
            continue
        bits = []
        for label in ["decision", "ci_status", "status", "exit_code", "path"]:
            value = review.get(label)
            if value not in (None, ""):
                bits.append("%s=%s" % (label, value))
        review_lines.append("- %s: %s" % (key, ", ".join(bits) or "attached"))
    review_text = "\n".join(review_lines) or "- No reviews were found."
    return f"""
# Browser E2E Execution Evidence

- Status: {status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Strict: {context["strict"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Correlated Reviews

{review_text}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Execution manifest: e2e-execution-evidence.json
- Environment summary: env-summary.txt
- Status table: status.tsv
"""


def _artifact_review(label, path, required, rows, blockers, warnings):
    if not path:
        message = "%s evidence path is not configured." % label
        rows.append(_row(label, "failed" if required else "passed", message))
        if required:
            blockers.append(message)
        return {}
    if not path.is_file():
        message = "%s evidence file is missing." % label
        rows.append(_row(label, "failed" if required else "passed", message, str(path)))
        if required:
            blockers.append(message)
        return {"path": str(path), "present": False}
    rows.append(_row(label, "passed", "%s evidence file is present." % label, str(path)))
    return {"path": str(path), "present": True}


def _review_decision(label, payload, path, rows, blockers, warnings):
    decision = str(payload.get("decision") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if not decision and not ci_status:
        message = "%s evidence has no decision or CI status." % label
        rows.append(_row("%s-decision" % label, "warning", message, str(path)))
        warnings.append(message)
    elif decision in {"blocked", "failed"} or ci_status == "fail":
        message = "%s evidence is %s/%s." % (label, decision or "unknown", ci_status or "unknown")
        rows.append(_row("%s-decision" % label, "failed", message, str(path)))
        blockers.append(message)
    elif decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        message = "%s evidence is %s/%s." % (label, decision or "unknown", ci_status or "unknown")
        rows.append(_row("%s-decision" % label, "warning", message, str(path)))
        warnings.append(message)
    else:
        rows.append(_row("%s-decision" % label, "passed", "%s evidence is ready/pass." % label, str(path)))
    return {"decision": decision, "ci_status": ci_status}


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
        if isinstance(node, dict):
            for test in node.get("tests") or []:
                outcome = str(test.get("outcome") or "").lower()
                if outcome in {"unexpected", "failed", "timedout", "interrupted"}:
                    counts["unexpected"] += 1
                elif outcome == "flaky":
                    counts["flaky"] += 1
                elif outcome == "skipped":
                    counts["skipped"] += 1
                elif outcome:
                    counts["expected"] += 1
                for result in test.get("results") or []:
                    status = str(result.get("status") or "").lower()
                    if status in {"failed", "timedout", "interrupted"}:
                        counts["unexpected"] += 1
            for child in node.get("suites") or []:
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if not stats:
        walk(payload.get("suites") if isinstance(payload, dict) else [])
    return counts


def _orchestration_counts(path):
    counts = {}
    failed = []
    if not path or not path.is_file():
        return counts, failed
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return counts, failed
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, status = parts[0], parts[1]
        counts[status] = counts.get(status, 0) + 1
        if status in {"failed", "blocked", "error"}:
            failed.append(name)
    return counts, failed


def main():
    parser = argparse.ArgumentParser(
        description="Export correlated Tijara browser E2E execution evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_E2E_EXECUTION_RUN_ID", ""))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_E2E_EXECUTION_ENVIRONMENT", "staging"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_E2E_EXECUTION_OUTPUT", ""))
    parser.add_argument("--seed-evidence", default=os.environ.get("TIJARA_E2E_EXECUTION_SEED_EVIDENCE", ""))
    parser.add_argument("--profile-evidence", default=os.environ.get("TIJARA_E2E_EXECUTION_PROFILE_EVIDENCE", ""))
    parser.add_argument("--e2e-evidence-dir", default=os.environ.get("TIJARA_E2E_EXECUTION_E2E_DIR", ""))
    parser.add_argument("--readiness-evidence", default=os.environ.get("TIJARA_E2E_EXECUTION_READINESS_EVIDENCE", ""))
    parser.add_argument("--playwright-json", default=os.environ.get("TIJARA_E2E_EXECUTION_PLAYWRIGHT_JSON", ""))
    parser.add_argument("--e2e-summary", default=os.environ.get("TIJARA_E2E_EXECUTION_E2E_SUMMARY", ""))
    parser.add_argument("--signoff-readiness", default=os.environ.get("TIJARA_E2E_EXECUTION_SIGNOFF_READINESS", ""))
    parser.add_argument("--orchestration-status", default=os.environ.get("TIJARA_E2E_EXECUTION_ORCH_STATUS", ""))
    parser.add_argument(
        "--strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_E2E_EXECUTION_STRICT")),
        help="Require seed, profile, readiness, Playwright JSON, E2E summary, sign-off, and orchestration evidence.",
    )
    args = parser.parse_args()

    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/e2e-execution" / run_id
    e2e_dir = Path(args.e2e_evidence_dir) if args.e2e_evidence_dir else ROOT_DIR / "deploy/runtime/e2e-evidence" / run_id
    seed_path = Path(args.seed_evidence) if args.seed_evidence else ROOT_DIR / "deploy/runtime/e2e-seed" / run_id / "e2e-seed-evidence.json"
    profile_path = Path(args.profile_evidence) if args.profile_evidence else ROOT_DIR / "deploy/runtime/e2e-profile" / run_id / "staging-e2e-profile.json"
    readiness_path = Path(args.readiness_evidence) if args.readiness_evidence else e2e_dir / "e2e-readiness.json"
    playwright_path = Path(args.playwright_json) if args.playwright_json else e2e_dir / "playwright-results.json"
    e2e_summary_path = Path(args.e2e_summary) if args.e2e_summary else e2e_dir / "summary.md"
    signoff_path = Path(args.signoff_readiness) if args.signoff_readiness else ROOT_DIR / "deploy/runtime/signoff-packages" / run_id / "release-readiness.json"
    orchestration_path = Path(args.orchestration_status) if args.orchestration_status else ROOT_DIR / "deploy/runtime/staging-release" / run_id / "status.tsv"

    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    reviews = {}

    artifact_specs = [
        ("seed", seed_path, args.strict),
        ("profile", profile_path, args.strict),
        ("readiness", readiness_path, True),
        ("playwright", playwright_path, True),
        ("e2e-summary", e2e_summary_path, True),
        ("signoff", signoff_path, args.strict),
        ("orchestration", orchestration_path, False),
    ]
    for label, path, required in artifact_specs:
        reviews[label.replace("-", "_")] = _artifact_review(label, path, required, rows, blockers, warnings)

    for label, path in [
        ("seed", seed_path),
        ("profile", profile_path),
        ("readiness", readiness_path),
        ("signoff", signoff_path),
    ]:
        payload = _read_json(path)
        if payload:
            reviews[label].update(_review_decision(label, payload, path, rows, blockers, warnings))

    summary_fields = _read_summary_fields(e2e_summary_path)
    if summary_fields:
        status = str(summary_fields.get("Status") or "").strip().lower()
        exit_code = str(summary_fields.get("Exit code") or "").strip()
        reviews["e2e_summary"].update(
            {
                "status": summary_fields.get("Status", ""),
                "exit_code": exit_code,
                "path": str(e2e_summary_path),
            }
        )
        if status in {"passed", "ready", "approved"}:
            rows.append(_row("e2e-summary-status", "passed", "E2E summary status is %s." % status, str(e2e_summary_path)))
        elif status in {"warning", "warn", "pass_with_warnings"}:
            message = "E2E summary status is %s." % status
            rows.append(_row("e2e-summary-status", "warning", message, str(e2e_summary_path)))
            warnings.append(message)
        elif status:
            message = "E2E summary status is %s." % status
            rows.append(_row("e2e-summary-status", "failed", message, str(e2e_summary_path)))
            blockers.append(message)

    playwright_payload = _read_json(playwright_path)
    if playwright_payload:
        stats = _playwright_stats(playwright_payload)
        reviews["playwright"].update({"stats": stats, "path": str(playwright_path)})
        if stats["unexpected"] or stats["interrupted"]:
            message = "Playwright JSON contains unexpected/interrupted tests: %s/%s." % (
                stats["unexpected"],
                stats["interrupted"],
            )
            rows.append(_row("playwright-results", "failed", message, str(playwright_path)))
            blockers.append(message)
        else:
            rows.append(
                _row(
                    "playwright-results",
                    "passed",
                    "Playwright JSON has no unexpected/interrupted tests.",
                    str(playwright_path),
                )
            )

    orch_counts, failed_steps = _orchestration_counts(orchestration_path)
    if orch_counts:
        reviews["orchestration"].update({"status_counts": orch_counts, "failed_steps": failed_steps})
        if failed_steps:
            message = "Staging orchestration failed steps: %s." % ", ".join(failed_steps)
            rows.append(_row("orchestration-status", "failed", message, str(orchestration_path)))
            blockers.append(message)
        else:
            rows.append(_row("orchestration-status", "passed", "Staging orchestration has no failed steps.", str(orchestration_path)))

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
        "run_id": run_id,
        "target_environment": args.target_environment,
        "output": str(output),
        "strict": bool(args.strict),
        "generated_at": _utc_now(),
        "seed_evidence": str(seed_path),
        "profile_evidence": str(profile_path),
        "e2e_evidence_dir": str(e2e_dir),
        "readiness_evidence": str(readiness_path),
        "playwright_json": str(playwright_path),
        "e2e_summary": str(e2e_summary_path),
        "signoff_readiness": str(signoff_path),
        "orchestration_status": str(orchestration_path),
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "reviews": reviews,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    _write(output / "e2e-execution-evidence.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings, reviews))

    print("Browser E2E execution evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("blockers=%s" % len(blockers))
    if warnings:
        print("warnings=%s" % len(warnings))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
