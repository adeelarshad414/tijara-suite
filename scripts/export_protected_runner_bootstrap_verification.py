#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REQUIRED_TOOLS = "python3,node,npm,docker,docker-compose,trivy,k6,psql,pg_dump,pg_restore"


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


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_env_summary(path):
    env = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _read_bootstrap_tools(path):
    tools = {}
    if not path.is_file():
        return tools
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if not parts or parts[0] == "tool":
            continue
        while len(parts) < 5:
            parts.append("")
        tool, scope, status, exit_code, version = parts[:5]
        if tool:
            tools[tool] = {
                "name": tool,
                "scope": scope,
                "status": status,
                "exit_code": exit_code,
                "version": version,
            }
    return tools


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _tool_tsv(correlations):
    lines = [
        "tool\trequired\tbootstrap_status\tpreflight_status\tresult\tbootstrap_version\tpreflight_version"
    ]
    for row in correlations:
        lines.append(
            "%s\t%s\t%s\t%s\t%s\t%s\t%s"
            % (
                row["tool"],
                int(row["required"]),
                row["bootstrap_status"],
                row["preflight_status"],
                row["result"],
                row["bootstrap_version"],
                row["preflight_version"],
            )
        )
    return "\n".join(lines)


def _add_issue(rows, blockers, warnings, strict, name, message):
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _bootstrap_review(path, rows, blockers, warnings, strict):
    required_files = [
        "install-plan.sh",
        "preflight-command.sh",
        "tool-status.tsv",
        "summary.md",
        "env-summary.txt",
    ]
    review = {
        "path": _repo_relative(path),
        "exists": path.is_dir(),
        "files": {},
        "env_summary": {},
        "tools": {},
    }
    if not path.is_dir():
        _add_issue(rows, blockers, warnings, strict, "bootstrap-evidence", "Bootstrap evidence directory is missing: %s" % path)
        return review
    rows.append(_row("bootstrap-evidence", "passed", "Bootstrap evidence directory is present."))
    for filename in required_files:
        file_path = path / filename
        exists = file_path.is_file()
        review["files"][filename] = _repo_relative(file_path) if exists else ""
        if exists:
            rows.append(_row("bootstrap-file-%s" % filename.replace(".", "-"), "passed", "%s is present." % filename))
        else:
            _add_issue(rows, blockers, warnings, strict, "bootstrap-file-%s" % filename.replace(".", "-"), "%s is missing from bootstrap evidence." % filename)
    review["env_summary"] = _read_env_summary(path / "env-summary.txt")
    review["tools"] = _read_bootstrap_tools(path / "tool-status.tsv")
    return review


def _preflight_review(path, rows, blockers, warnings, strict):
    payload = _read_json(path)
    review = {
        "path": _repo_relative(path),
        "exists": path.is_file(),
        "decision": payload.get("decision", ""),
        "ci_status": payload.get("ci_status", ""),
        "context": payload.get("context") or {},
        "toolchain": {item.get("name"): item for item in payload.get("toolchain") or [] if item.get("name")},
    }
    if not path.is_file():
        _add_issue(rows, blockers, warnings, strict, "preflight-evidence", "Protected runner preflight JSON is missing: %s" % path)
        return review
    rows.append(_row("preflight-evidence", "passed", "Protected runner preflight JSON is present."))
    if review["decision"] in {"failed", "blocked"} or review["ci_status"] == "fail":
        _add_issue(rows, blockers, warnings, strict, "preflight-decision", "Protected runner preflight is failed.")
    elif review["decision"] == "warning" or review["ci_status"] == "pass_with_warnings":
        warnings.append("Protected runner preflight has warnings.")
        rows.append(_row("preflight-decision", "warning", "Protected runner preflight has warnings."))
    else:
        rows.append(_row("preflight-decision", "passed", "Protected runner preflight is passed."))
    return review


def _correlate_tools(required_tools, bootstrap_tools, preflight_tools, rows, blockers, warnings, strict):
    correlations = []
    all_tools = _dedupe(required_tools + sorted(set(bootstrap_tools) | set(preflight_tools)))
    for tool in all_tools:
        required = tool in required_tools
        bootstrap = bootstrap_tools.get(tool) or {}
        preflight = preflight_tools.get(tool) or {}
        bootstrap_status = bootstrap.get("status") or "missing"
        preflight_status = preflight.get("status") or "missing"
        bootstrap_version = bootstrap.get("version") or ""
        preflight_version = preflight.get("version") or ""
        result = "passed"
        messages = []
        if required and bootstrap_status != "present":
            result = "failed"
            messages.append("bootstrap missing")
        if required and preflight_status != "passed":
            result = "failed"
            messages.append("preflight not passed")
        if result == "passed" and bootstrap_status == "present" and preflight_status == "passed":
            if bootstrap_version and preflight_version and bootstrap_version != preflight_version:
                result = "warning"
                messages.append("version output differs")
        if result == "passed" and (bootstrap_status == "missing" or preflight_status == "missing"):
            result = "warning"
            messages.append("optional evidence incomplete")
        correlations.append(
            {
                "tool": tool,
                "required": required,
                "bootstrap_status": bootstrap_status,
                "preflight_status": preflight_status,
                "bootstrap_version": bootstrap_version,
                "preflight_version": preflight_version,
                "result": result,
                "message": "; ".join(messages) or "tool evidence is aligned",
            }
        )
        check_name = "tool-%s" % tool.replace("_", "-")
        message = "%s: bootstrap=%s, preflight=%s" % (tool, bootstrap_status, preflight_status)
        if result == "failed":
            if strict:
                blockers.append("%s (%s)" % (message, correlations[-1]["message"]))
                rows.append(_row(check_name, "failed", "%s (%s)" % (message, correlations[-1]["message"])))
            else:
                warnings.append("%s (%s)" % (message, correlations[-1]["message"]))
                rows.append(_row(check_name, "warning", "%s (%s)" % (message, correlations[-1]["message"])))
        elif result == "warning":
            warnings.append("%s (%s)" % (message, correlations[-1]["message"]))
            rows.append(_row(check_name, "warning", "%s (%s)" % (message, correlations[-1]["message"])))
        else:
            rows.append(_row(check_name, "passed", message))
    return correlations


def _summary(context, rows, blockers, warnings):
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Runner Bootstrap Verification

- Status: {context["decision"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Bootstrap evidence: {context["bootstrap_evidence"]}
- Preflight evidence: {context["preflight_evidence"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Verification manifest: protected-runner-bootstrap-verification.json
- Tool correlation: tool-correlation.tsv
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara protected runner bootstrap/preflight verification evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_BOOTSTRAP_VERIFICATION_OUTPUT", ""))
    parser.add_argument("--bootstrap-evidence", default=os.environ.get("TIJARA_BOOTSTRAP_VERIFICATION_BOOTSTRAP_EVIDENCE", ""))
    parser.add_argument("--preflight-evidence", default=os.environ.get("TIJARA_BOOTSTRAP_VERIFICATION_PREFLIGHT_EVIDENCE", ""))
    parser.add_argument("--required-tools", default=os.environ.get("TIJARA_BOOTSTRAP_VERIFICATION_REQUIRED_TOOLS", DEFAULT_REQUIRED_TOOLS))
    parser.add_argument("--required-tool", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_BOOTSTRAP_VERIFICATION_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true", default=_truthy(os.environ.get("TIJARA_BOOTSTRAP_VERIFICATION_STRICT", "0")))
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-runner-bootstrap-verification" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    bootstrap_path = _resolve(args.bootstrap_evidence or "deploy/runtime/protected-runner-bootstrap/%s" % args.run_id)
    preflight_path = _resolve(
        args.preflight_evidence
        or "deploy/runtime/protected-runner-preflight/%s/protected-runner-preflight.json" % args.run_id
    )
    rows = []
    blockers = []
    warnings = []

    bootstrap = _bootstrap_review(bootstrap_path, rows, blockers, warnings, strict)
    preflight = _preflight_review(preflight_path, rows, blockers, warnings, strict)
    required_tools = _dedupe(
        _csv_items(args.required_tools)
        + args.required_tool
        + list((preflight.get("context") or {}).get("required_tools") or [])
    )
    correlations = _correlate_tools(
        required_tools,
        bootstrap.get("tools") or {},
        preflight.get("toolchain") or {},
        rows,
        blockers,
        warnings,
        strict,
    )

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
        "strict": strict,
        "bootstrap_evidence": _repo_relative(bootstrap_path),
        "preflight_evidence": _repo_relative(preflight_path),
        "required_tools": required_tools,
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "bootstrap": bootstrap,
        "preflight": preflight,
        "tool_correlations": correlations,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "strict=%s" % int(strict),
            "bootstrap_evidence=%s" % _repo_relative(bootstrap_path),
            "preflight_evidence=%s" % _repo_relative(preflight_path),
            "required_tools=%s" % ",".join(required_tools),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )

    _write(output / "protected-runner-bootstrap-verification.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "tool-correlation.tsv", _tool_tsv(correlations))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Protected runner bootstrap verification written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
