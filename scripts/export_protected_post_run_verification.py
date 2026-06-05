#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
DEFAULT_REQUIRED_ARTIFACTS = [
    "protected-runbook-handoff",
    "protected-first-run",
    "protected-runner-preflight",
    "protected-service-checks",
    "protected-provider-readiness",
    "release-evidence",
    "protected-e2e",
    "ops-tool-evidence",
    "certification-evidence",
    "release-retention-evidence",
    "secret-manager-evidence",
    "production-ops-readiness",
    "signoff-packages",
    "github-artifact-metadata",
]
ARTIFACT_PATHS = {
    "protected-runbook-handoff": "protected-runbook-handoff/{run_id}",
    "protected-first-run": "protected-first-run/{run_id}",
    "protected-runner-preflight": "protected-runner-preflight/{run_id}",
    "protected-service-checks": "protected-service-checks/{run_id}",
    "protected-provider-readiness": "protected-provider-readiness/{run_id}",
    "release-evidence": "release-evidence/{run_id}",
    "protected-e2e": "protected-e2e/{run_id}",
    "e2e-seed": "e2e-seed/{run_id}",
    "e2e-profile": "e2e-profile/{run_id}",
    "e2e-evidence": "e2e-evidence/{run_id}",
    "e2e-execution": "e2e-execution/{run_id}",
    "ops-tool-evidence": "ops-tool-evidence/{run_id}",
    "operations-release-bundle": "operations-release-bundle/{run_id}",
    "certification-evidence": "certification-evidence/{run_id}",
    "release-retention-evidence": "release-retention-evidence/{run_id}",
    "secret-manager-evidence": "secret-manager-evidence/{run_id}",
    "production-ops-readiness": "production-ops-readiness/{run_id}",
    "signoff-packages": "signoff-packages/{run_id}",
    "github-artifact-metadata": "github-artifact-metadata/{run_id}",
    "protected-artifact-summary": "protected-artifact-summary/{run_id}",
}
FAILING_STATUSES = {"fail", "failed", "error", "blocked"}
WARNING_STATUSES = {"warn", "warning", "pass_with_warnings"}


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


def _resolve_path(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _parse_status_tsv(path):
    rows = []
    if not path.is_file():
        return rows
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[1:]:
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        rows.append({"check": parts[0], "status": parts[1], "message": parts[2]})
    return rows


def _json_decisions(path):
    decisions = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return decisions
    if not isinstance(payload, dict):
        return decisions
    for key in ["decision", "ci_status", "status"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            decisions.append({"file": _repo_relative(path), "key": key, "value": value.strip()})
    return decisions


def _artifact_component(name, path, required):
    component = {
        "name": name,
        "path": str(path),
        "relative_path": _repo_relative(path),
        "required": required,
        "exists": path.exists(),
        "file_count": 0,
        "status_rows": [],
        "failed_rows": [],
        "warning_rows": [],
        "json_decisions": [],
    }
    if not path.exists():
        return component
    files = [path] if path.is_file() else sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    component["file_count"] = len(files)
    for file_path in files:
        if file_path.name == "status.tsv":
            for status_row in _parse_status_tsv(file_path):
                status = str(status_row.get("status") or "").strip().lower()
                entry = {
                    "file": _repo_relative(file_path),
                    "check": status_row.get("check", ""),
                    "status": status_row.get("status", ""),
                    "message": status_row.get("message", ""),
                }
                component["status_rows"].append(entry)
                if status in FAILING_STATUSES:
                    component["failed_rows"].append(entry)
                elif status in WARNING_STATUSES:
                    component["warning_rows"].append(entry)
        if file_path.suffix.lower() == ".json":
            component["json_decisions"].extend(_json_decisions(file_path))
    return component


def _decision_status(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"ready", "passed", "pass", "success"}:
        return "passed"
    if normalized in WARNING_STATUSES:
        return "warning"
    if normalized in FAILING_STATUSES or normalized in {"failed", "fail"}:
        return "failed"
    return "warning" if normalized else "failed"


def _evidence_overview(context, components, readiness, blockers, warnings):
    lines = [
        "# Protected Post-Run Evidence Overview",
        "",
        "- Run ID: %s" % context["run_id"],
        "- Target environment: %s" % context["target_environment"],
        "- Generated: %s" % context["generated_at"],
        "- Release readiness: %s" % (readiness.get("decision") or "<missing>"),
        "",
        "## Artifact Components",
        "",
    ]
    for component in components:
        status = "present" if component["exists"] else "missing"
        lines.append(
            "- `%s`: %s, files=%s, failed_rows=%s, warning_rows=%s"
            % (
                component["name"],
                status,
                component["file_count"],
                len(component["failed_rows"]),
                len(component["warning_rows"]),
            )
        )
    lines.extend(["", "## Blockers", ""])
    lines.extend("- %s" % item for item in blockers or ["None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend("- %s" % item for item in warnings or ["None"])
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Post-Run Verification

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

- Verification manifest: protected-post-run-verification.json
- Evidence overview: evidence-overview.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Verify Tijara protected post-run evidence folders.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_POST_RUN_OUTPUT", ""))
    parser.add_argument("--artifact-root", default=os.environ.get("TIJARA_POST_RUN_ARTIFACT_ROOT", "deploy/runtime"))
    parser.add_argument(
        "--required-artifacts",
        default=os.environ.get("TIJARA_POST_RUN_REQUIRED_ARTIFACTS", ",".join(DEFAULT_REQUIRED_ARTIFACTS)),
    )
    parser.add_argument("--required-artifact", action="append", default=[])
    parser.add_argument("--artifact-path", action="append", default=[])
    parser.add_argument("--readiness", default=os.environ.get("TIJARA_POST_RUN_READINESS", ""))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_POST_RUN_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-post-run-verification" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    required_artifacts = _dedupe(_csv_items(args.required_artifacts) + args.required_artifact)
    artifact_names = _dedupe(required_artifacts + [name for name in ARTIFACT_PATHS if name not in required_artifacts])

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

    components = []
    artifact_root = _resolve_path(args.artifact_root)
    for name in artifact_names:
        template = ARTIFACT_PATHS.get(name)
        if template:
            path = artifact_root / template.format(run_id=args.run_id)
        else:
            path = artifact_root / name / args.run_id
        components.append(_artifact_component(name, path, name in required_artifacts))
    for raw_path in args.artifact_path:
        path = _resolve_path(raw_path)
        components.append(_artifact_component(path.name, path, False))

    for component in components:
        if component["required"] and not component["exists"]:
            message = "Required protected artifact is missing: %s" % component["relative_path"]
            if strict:
                blockers.append(message)
                rows.append(_row("artifact-%s" % component["name"], "failed", message))
            else:
                warnings.append(message)
                rows.append(_row("artifact-%s" % component["name"], "warning", message))
            continue
        if component["exists"]:
            rows.append(
                _row(
                    "artifact-%s" % component["name"],
                    "passed",
                    "Artifact present with %s file(s)." % component["file_count"],
                )
            )

    for component in components:
        for failed in component["failed_rows"]:
            message = "Failed status row in %s: %s" % (failed["file"], failed["check"])
            blockers.append(message)
        for warning in component["warning_rows"]:
            message = "Warning status row in %s: %s" % (warning["file"], warning["check"])
            warnings.append(message)
        for decision in component["json_decisions"]:
            status = _decision_status(decision["value"])
            message = "%s has %s=%s" % (decision["file"], decision["key"], decision["value"])
            if status == "failed":
                blockers.append(message)
            elif status == "warning":
                warnings.append(message)

    if args.readiness:
        readiness_path = _resolve_path(args.readiness)
    else:
        readiness_path = artifact_root / "signoff-packages" / args.run_id / "release-readiness.json"
    readiness = {
        "path": str(readiness_path),
        "relative_path": _repo_relative(readiness_path),
        "exists": readiness_path.is_file(),
        "decision": "",
        "ci_status": "",
    }
    if not readiness_path.is_file():
        message = "Release readiness JSON is missing: %s" % _repo_relative(readiness_path)
        if strict:
            blockers.append(message)
            rows.append(_row("release-readiness", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("release-readiness", "warning", message))
    else:
        try:
            payload = json.loads(readiness_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            message = "Release readiness JSON cannot be parsed: %s" % error
            blockers.append(message)
            rows.append(_row("release-readiness", "failed", message))
        else:
            readiness["decision"] = str(payload.get("decision") or "")
            readiness["ci_status"] = str(payload.get("ci_status") or "")
            readiness_status = _decision_status(readiness["decision"])
            if readiness_status == "passed":
                rows.append(_row("release-readiness", "passed", "Release readiness is %s." % readiness["decision"]))
            elif readiness_status == "warning":
                message = "Release readiness is warning: %s" % readiness["decision"]
                warnings.append(message)
                rows.append(_row("release-readiness", "warning", message))
            else:
                message = "Release readiness is not passing: %s" % (readiness["decision"] or "<unset>")
                blockers.append(message)
                rows.append(_row("release-readiness", "failed", message))

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
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
        "artifact_root": str(artifact_root),
        "strict": strict,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "required_artifacts": required_artifacts,
        "components": components,
        "release_readiness": readiness,
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "artifact_root=%s" % artifact_root,
            "required_artifacts=%s" % ",".join(required_artifacts),
            "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
            "strict=%s" % int(strict),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-post-run-verification.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "evidence-overview.md", _evidence_overview(context, components, readiness, blockers, warnings))
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Protected post-run verification written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
