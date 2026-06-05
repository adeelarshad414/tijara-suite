#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INTERESTING_JSON_NAMES = {
    "github-artifact-metadata.json",
    "protected-runbook-handoff.json",
    "protected-first-run-checklist.json",
    "protected-runner-preflight.json",
    "protected-service-checks.json",
    "protected-provider-readiness.json",
    "protected-payment-lifecycle-evidence.json",
    "protected-offline-replay-evidence.json",
    "psp-readiness.json",
    "fbr-readiness.json",
    "protected-post-run-verification.json",
    "e2e-execution-evidence.json",
    "e2e-readiness.json",
    "e2e-seed-evidence.json",
    "staging-e2e-profile.json",
    "ops-tool-evidence.json",
    "operations-release-bundle.json",
    "monitoring-evidence.json",
    "incident-runbook-evidence.json",
    "secret-runtime-evidence.json",
    "deployment-environment-evidence.json",
    "tenant-ops-evidence.json",
    "certification-evidence.json",
    "release-retention-evidence.json",
    "secret-manager-evidence.json",
    "production-ops-readiness.json",
    "release-readiness.json",
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve(path):
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _summary_status(path):
    if not path.is_file():
        return ""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("- Status:"):
                return stripped.partition(":")[2].strip()
    except OSError:
        return ""
    return ""


def _status_rows(path):
    rows = []
    if not path.is_file():
        return rows
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        rows.append(
            {
                "name": parts[0],
                "status": parts[1],
                "message": parts[4] if len(parts) >= 5 else parts[2] if len(parts) >= 3 else "",
                "source": str(path),
            }
        )
    return rows


def _component(label, raw_path):
    path = _resolve(raw_path)
    component = {
        "label": label,
        "path": _repo_relative(path),
        "exists": path.exists(),
        "file_count": 0,
        "summary_statuses": [],
        "json_reviews": [],
        "failed_rows": [],
        "warning_rows": [],
    }
    if not path.exists():
        component["failed_rows"].append(
            {"name": "artifact-path", "status": "failed", "message": "Artifact path is missing.", "source": str(path)}
        )
        return component
    files = [path] if path.is_file() else sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    component["file_count"] = len(files)
    for candidate in files:
        if candidate.name == "summary.md":
            status = _summary_status(candidate)
            if status:
                component["summary_statuses"].append({"path": _repo_relative(candidate), "status": status})
        if candidate.name == "status.tsv":
            for row in _status_rows(candidate):
                status = str(row.get("status") or "").lower()
                if status in {"failed", "blocked", "error"}:
                    component["failed_rows"].append(row)
                elif status in {"warning", "warn", "skipped"}:
                    component["warning_rows"].append(row)
        if candidate.name in INTERESTING_JSON_NAMES:
            payload = _read_json(candidate)
            if payload:
                decision = str(payload.get("decision") or "").lower()
                ci_status = str(payload.get("ci_status") or "").lower()
                component["json_reviews"].append(
                    {
                        "path": _repo_relative(candidate),
                        "decision": payload.get("decision", ""),
                        "ci_status": payload.get("ci_status", ""),
                        "blocker_count": len(payload.get("blockers") or []),
                        "warning_count": len(payload.get("warnings") or []),
                    }
                )
                if decision in {"failed", "blocked"} or ci_status == "fail":
                    component["failed_rows"].append(
                        {
                            "name": candidate.name,
                            "status": "failed",
                            "message": "JSON decision is %s/%s." % (decision or "unknown", ci_status or "unknown"),
                            "source": str(candidate),
                        }
                    )
                elif decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
                    component["warning_rows"].append(
                        {
                            "name": candidate.name,
                            "status": "warning",
                            "message": "JSON decision is %s/%s." % (decision or "unknown", ci_status or "unknown"),
                            "source": str(candidate),
                        }
                    )
    return component


def _status_tsv(components):
    lines = ["component\tstatus\tmessage\tpath"]
    for component in components:
        if component["failed_rows"]:
            status = "failed"
            message = "%s failed row(s)" % len(component["failed_rows"])
        elif component["warning_rows"]:
            status = "warning"
            message = "%s warning/skipped row(s)" % len(component["warning_rows"])
        elif not component["exists"]:
            status = "failed"
            message = "artifact path missing"
        elif component["file_count"] == 0:
            status = "warning"
            message = "artifact path contains no files"
        else:
            status = "passed"
            message = "%s file(s)" % component["file_count"]
        lines.append("%s\t%s\t%s\t%s" % (component["label"], status, message, component["path"]))
    return "\n".join(lines)


def _summary(context, components, blockers, warnings):
    component_lines = []
    for component in components:
        if component["failed_rows"]:
            status = "failed"
        elif component["warning_rows"]:
            status = "warning"
        elif component["exists"]:
            status = "passed"
        else:
            status = "failed"
        component_lines.append(
            "- `%s`: %s, files=%s, path=%s"
            % (component["label"], status, component["file_count"], component["path"])
        )
        for row in component["failed_rows"][:5]:
            component_lines.append("  - failed `%s`: %s" % (row["name"], row["message"]))
        for row in component["warning_rows"][:3]:
            component_lines.append("  - warning `%s`: %s" % (row["name"], row["message"]))
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Release Artifact Summary

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Workflow run URL: {context["workflow_run_url"] or "unset"}
- Artifact references: {", ".join(context["artifact_references"]) if context["artifact_references"] else "unset"}

## Components

{chr(10).join(component_lines) or "- No artifact paths were provided."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Artifact summary manifest: protected-artifact-summary.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export a protected release artifact summary.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_ARTIFACT_SUMMARY_OUTPUT", ""))
    parser.add_argument("--artifact-path", action="append", default=[])
    parser.add_argument("--artifact-reference", action="append", default=[])
    parser.add_argument("--workflow-run-url", default=os.environ.get("GITHUB_RUN_URL", ""))
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-artifact-summary" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    artifact_paths = list(args.artifact_path)
    artifact_paths.extend(_csv_items(os.environ.get("TIJARA_ARTIFACT_SUMMARY_PATHS")))
    if not artifact_paths:
        artifact_paths = [
            "deploy/runtime/protected-runbook-handoff/%s" % args.run_id,
            "deploy/runtime/protected-first-run/%s" % args.run_id,
            "deploy/runtime/protected-runner-preflight/%s" % args.run_id,
            "deploy/runtime/protected-service-checks/%s" % args.run_id,
            "deploy/runtime/protected-provider-readiness/%s" % args.run_id,
            "deploy/runtime/protected-payment-lifecycle/%s" % args.run_id,
            "deploy/runtime/protected-offline-replay/%s" % args.run_id,
            "deploy/runtime/release-evidence/%s" % args.run_id,
            "deploy/runtime/protected-e2e/%s" % args.run_id,
            "deploy/runtime/e2e-execution/%s" % args.run_id,
            "deploy/runtime/ops-tool-evidence/%s" % args.run_id,
            "deploy/runtime/operations-release-bundle/%s" % args.run_id,
            "deploy/runtime/monitoring-evidence/%s" % args.run_id,
            "deploy/runtime/incident-runbooks/%s" % args.run_id,
            "deploy/runtime/secret-runtime-evidence/%s" % args.run_id,
            "deploy/runtime/deployment-environments/%s" % args.run_id,
            "deploy/runtime/tenant-ops-evidence/%s" % args.run_id,
            "deploy/runtime/certification-evidence/%s" % args.run_id,
            "deploy/runtime/release-retention-evidence/%s" % args.run_id,
            "deploy/runtime/secret-manager-evidence/%s" % args.run_id,
            "deploy/runtime/production-ops-readiness/%s" % args.run_id,
            "deploy/runtime/signoff-packages/%s" % args.run_id,
            "deploy/runtime/protected-post-run-verification/%s" % args.run_id,
            "deploy/runtime/github-artifact-metadata/%s" % args.run_id,
        ]

    labels = {}
    components = []
    for raw_path in artifact_paths:
        normalized = raw_path.strip()
        if not normalized:
            continue
        label = Path(normalized).name or normalized
        if label in labels:
            labels[label] += 1
            label = "%s-%s" % (label, labels[label])
        else:
            labels[label] = 1
        components.append(_component(label, normalized))

    blockers = []
    warnings = []
    for component in components:
        for row in component["failed_rows"]:
            blockers.append("%s: %s is %s" % (component["label"], row["name"], row["status"]))
        for row in component["warning_rows"]:
            warnings.append("%s: %s is %s" % (component["label"], row["name"], row["status"]))
        if component["exists"] and component["file_count"] == 0:
            warnings.append("%s contains no files" % component["label"])
    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    github_server = os.environ.get("GITHUB_SERVER_URL", "")
    github_repository = os.environ.get("GITHUB_REPOSITORY", "")
    github_run_id = os.environ.get("GITHUB_RUN_ID", "")
    workflow_run_url = args.workflow_run_url
    if not workflow_run_url and github_server and github_repository and github_run_id:
        workflow_run_url = "%s/%s/actions/runs/%s" % (
            github_server.rstrip("/"),
            github_repository,
            github_run_id,
        )
    artifact_references = list(args.artifact_reference)
    artifact_references.extend(_csv_items(os.environ.get("TIJARA_ARTIFACT_REFERENCES")))
    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "decision": decision,
        "ci_status": ci_status,
        "workflow_run_url": workflow_run_url,
        "github": {
            "server_url": github_server,
            "repository": github_repository,
            "run_id": github_run_id,
            "run_number": os.environ.get("GITHUB_RUN_NUMBER", ""),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "sha": os.environ.get("GITHUB_SHA", ""),
            "ref": os.environ.get("GITHUB_REF", ""),
            "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        },
        "artifact_references": artifact_references,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "components": components,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "component_count=%s" % len(components),
            "workflow_run_url=%s" % (workflow_run_url or "<unset>"),
            "artifact_references=%s" % (",".join(artifact_references) or "<unset>"),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-artifact-summary.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(components))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, components, blockers, warnings))

    print("Protected artifact summary written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
