#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(project, status, message, source=""):
    return {
        "project": project,
        "status": status,
        "message": message,
        "source": source,
    }


def _load_project_status(path):
    rows = {}
    if not path or not path.is_file():
        return rows
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        rows[parts[0]] = {
            "project": parts[0],
            "status": parts[1],
            "e2e_exit": parts[2],
            "execution_exit": parts[3],
            "e2e_dir": parts[4],
            "execution_dir": parts[5],
            "log": parts[6],
            "message": parts[7],
        }
    return rows


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


def _status_tsv(rows):
    lines = ["project\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s"
            % (row["project"], row["status"], row["message"], row.get("source") or "")
        )
    return "\n".join(lines)


def _summary(context, rows, blockers, warnings):
    status = "blocked" if blockers else "warning" if warnings else "ready"
    project_lines = "\n".join(
        "- %s: %s - %s" % (row["project"], row["status"], row["message"])
        for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Browser E2E Matrix Evidence

- Status: {status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Strict: {context["strict"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Project status source: {context["project_status"]}
- Projects: {", ".join(context["projects"]) or "<none>"}

## Project Results

{project_lines or "- No project rows were recorded."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Matrix manifest: browser-e2e-matrix-evidence.json
- Environment summary: env-summary.txt
- Status table: status.tsv
"""


def main():
    parser = argparse.ArgumentParser(
        description="Export aggregate Tijara browser/device E2E matrix evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_BROWSER_E2E_RUN_ID", ""))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("TIJARA_BROWSER_E2E_MATRIX_OUTPUT", ""),
    )
    parser.add_argument(
        "--project-status",
        default=os.environ.get("TIJARA_BROWSER_E2E_PROJECT_STATUS", ""),
    )
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/browser-e2e-matrix" / run_id
    project_status_path = (
        Path(args.project_status)
        if args.project_status
        else output / "project-status.tsv"
    )
    projects = args.project or []
    output.mkdir(parents=True, exist_ok=True)

    project_status = _load_project_status(project_status_path)
    rows = []
    blockers = []
    warnings = []
    reviews = {}

    for project in projects:
        status_row = project_status.get(project)
        if not status_row:
            message = "Project was requested but no status row was recorded."
            rows.append(_row(project, "failed", message))
            blockers.append("%s: %s" % (project, message))
            continue

        e2e_dir = Path(status_row["e2e_dir"])
        execution_dir = Path(status_row["execution_dir"])
        e2e_summary = e2e_dir / "summary.md"
        readiness = e2e_dir / "e2e-readiness.json"
        playwright_json = e2e_dir / "playwright-results.json"
        execution_json = execution_dir / "e2e-execution-evidence.json"

        summary_fields = _read_summary_fields(e2e_summary)
        readiness_payload = _read_json(readiness)
        playwright_payload = _read_json(playwright_json)
        execution_payload = _read_json(execution_json)
        playwright_counts = _playwright_stats(playwright_payload) if playwright_payload else {}

        reviews[project] = {
            "status": status_row,
            "e2e_summary": str(e2e_summary),
            "readiness": str(readiness),
            "playwright_json": str(playwright_json),
            "execution": str(execution_json),
            "summary_fields": summary_fields,
            "readiness_decision": readiness_payload.get("decision") if readiness_payload else "",
            "readiness_ci_status": readiness_payload.get("ci_status") if readiness_payload else "",
            "execution_decision": execution_payload.get("decision") if execution_payload else "",
            "execution_ci_status": execution_payload.get("ci_status") if execution_payload else "",
            "playwright_counts": playwright_counts,
        }

        missing_files = [
            str(path)
            for path in [e2e_summary, readiness, playwright_json, execution_json]
            if not path.is_file()
        ]
        if missing_files:
            message = "Missing evidence files: %s." % ", ".join(missing_files)
            rows.append(_row(project, "failed", message, status_row.get("log") or ""))
            blockers.append("%s: %s" % (project, message))
            continue

        if status_row["status"] != "passed":
            message = status_row.get("message") or "Project did not pass."
            rows.append(_row(project, "failed", message, status_row.get("log") or ""))
            blockers.append("%s: %s" % (project, message))
            continue

        if playwright_counts and (
            playwright_counts.get("unexpected", 0) or playwright_counts.get("interrupted", 0)
        ):
            message = "Playwright unexpected/interrupted counts are %s/%s." % (
                playwright_counts.get("unexpected", 0),
                playwright_counts.get("interrupted", 0),
            )
            rows.append(_row(project, "failed", message, str(playwright_json)))
            blockers.append("%s: %s" % (project, message))
            continue

        execution_decision = str(execution_payload.get("decision") or "").lower()
        execution_ci = str(execution_payload.get("ci_status") or "").lower()
        if execution_decision in {"blocked", "failed"} or execution_ci == "fail":
            message = "Execution evidence is %s/%s." % (
                execution_decision or "unknown",
                execution_ci or "unknown",
            )
            rows.append(_row(project, "failed", message, str(execution_json)))
            blockers.append("%s: %s" % (project, message))
            continue

        if execution_decision in {"warning", "warn"} or execution_ci == "pass_with_warnings":
            message = "Execution evidence passed with warnings."
            rows.append(_row(project, "warning", message, str(execution_json)))
            warnings.append("%s: %s" % (project, message))
            continue

        rows.append(_row(project, "passed", "Project E2E and execution evidence are ready.", str(execution_json)))

    if not projects:
        message = "No browser/device projects were requested."
        rows.append(_row("matrix", "failed", message))
        blockers.append(message)

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
        "strict": bool(args.strict),
        "generated_at": _utc_now(),
        "output": str(output),
        "project_status": str(project_status_path),
        "projects": projects,
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "reviews": reviews,
        "blockers": blockers,
        "warnings": warnings,
    }
    _write(output / "browser-e2e-matrix-evidence.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", "\n".join([
        "run_id=%s" % run_id,
        "target_environment=%s" % args.target_environment,
        "strict=%s" % bool(args.strict),
        "output=%s" % output,
        "project_status=%s" % project_status_path,
        "projects=%s" % ",".join(projects),
    ]))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Browser E2E matrix evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("blockers=%s" % len(blockers))
    if warnings:
        print("warnings=%s" % len(warnings))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
