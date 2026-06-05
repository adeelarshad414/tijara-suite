#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
HIGH_SEVERITIES = {"HIGH", "CRITICAL"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _safe_int(value):
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve(path):
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _read_text(path):
    target = _resolve(path)
    if not target:
        return "", ""
    if not target.is_file():
        return "", str(target)
    try:
        return target.read_text(encoding="utf-8", errors="replace"), str(target)
    except OSError:
        return "", str(target)


def _read_json(path):
    target = _resolve(path)
    if not target:
        return {}, ""
    if not target.is_file():
        return {"_read_error": "file does not exist"}, str(target)
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        return {"_read_error": str(error)}, str(target)


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


def _component(name, evidence_type, source, status, message, metrics=None, references=None):
    decision = "passed" if status == "passed" else "warning" if status == "warning" else "failed"
    ci_status = "pass" if status == "passed" else "pass_with_warnings" if status == "warning" else "fail"
    return {
        "name": name,
        "evidence_type": evidence_type,
        "source": source,
        "status": status,
        "decision": decision,
        "ci_status": ci_status,
        "message": message,
        "metrics": metrics or {},
        "references": references or {},
    }


def _log_component(name, evidence_type, log_path, exit_code, pass_phrase="", warning_phrase="", references=None):
    text, source = _read_text(log_path)
    if exit_code is None and not source:
        return None
    if source and not text and exit_code is None:
        return _component(name, evidence_type, source, "failed", "Evidence log is missing.", references=references)
    if exit_code not in (None, 0):
        return _component(
            name,
            evidence_type,
            source,
            "failed",
            "%s command exited %s." % (name, exit_code),
            {"exit_code": exit_code},
            references,
        )
    if pass_phrase and text and pass_phrase not in text:
        return _component(
            name,
            evidence_type,
            source,
            "warning",
            "%s command exited 0, but expected success phrase was not found." % name,
            {"exit_code": exit_code if exit_code is not None else ""},
            references,
        )
    if warning_phrase and text and warning_phrase in text:
        return _component(
            name,
            evidence_type,
            source,
            "warning",
            "%s command output contains warning phrase." % name,
            {"exit_code": exit_code if exit_code is not None else ""},
            references,
        )
    return _component(
        name,
        evidence_type,
        source,
        "passed",
        "%s command evidence passed." % name,
        {"exit_code": exit_code if exit_code is not None else 0},
        references,
    )


def _trivy_component(path):
    payload, source = _read_json(path)
    if payload.get("_read_error"):
        return _component("container-scan", "trivy-json", source, "failed", payload["_read_error"])
    high_count = 0
    critical_count = 0
    misconfiguration_count = 0
    for result in payload.get("Results") or []:
        for vulnerability in result.get("Vulnerabilities") or []:
            severity = str(vulnerability.get("Severity") or "").upper()
            if severity == "CRITICAL":
                critical_count += 1
            elif severity == "HIGH":
                high_count += 1
        for misconfiguration in result.get("Misconfigurations") or []:
            severity = str(misconfiguration.get("Severity") or "").upper()
            if severity in HIGH_SEVERITIES:
                misconfiguration_count += 1
    total = high_count + critical_count + misconfiguration_count
    metrics = {
        "high_vulnerabilities": high_count,
        "critical_vulnerabilities": critical_count,
        "high_critical_misconfigurations": misconfiguration_count,
    }
    if total:
        return _component(
            "container-scan",
            "trivy-json",
            source,
            "failed",
            "Trivy found %s high/critical issue(s)." % total,
            metrics,
        )
    return _component("container-scan", "trivy-json", source, "passed", "Trivy found no high/critical issues.", metrics)


def _npm_audit_component(path):
    payload, source = _read_json(path)
    if payload.get("_read_error"):
        return _component("dependency-scan", "npm-audit-json", source, "failed", payload["_read_error"])
    vulnerabilities = (payload.get("metadata") or {}).get("vulnerabilities") or {}
    high_count = int(vulnerabilities.get("high") or 0)
    critical_count = int(vulnerabilities.get("critical") or 0)
    total = high_count + critical_count
    metrics = {"high_vulnerabilities": high_count, "critical_vulnerabilities": critical_count}
    if total:
        return _component(
            "dependency-scan",
            "npm-audit-json",
            source,
            "failed",
            "npm audit found %s high/critical issue(s)." % total,
            metrics,
        )
    return _component("dependency-scan", "npm-audit-json", source, "passed", "npm audit has no high/critical issues.", metrics)


def _pip_audit_component(path):
    payload, source = _read_json(path)
    if payload.get("_read_error"):
        return _component("dependency-scan", "pip-audit-json", source, "failed", payload["_read_error"])
    dependencies = payload if isinstance(payload, list) else payload.get("dependencies") or payload.get("results") or []
    vulnerability_count = 0
    for dependency in dependencies:
        vulnerability_count += len(dependency.get("vulns") or dependency.get("vulnerabilities") or [])
    metrics = {"vulnerability_count": vulnerability_count}
    if vulnerability_count:
        return _component(
            "dependency-scan",
            "pip-audit-json",
            source,
            "failed",
            "pip-audit found %s vulnerability item(s)." % vulnerability_count,
            metrics,
        )
    return _component("dependency-scan", "pip-audit-json", source, "passed", "pip-audit found no vulnerabilities.", metrics)


def _metric(summary, metric_name, value_name, default=None):
    metric = (summary.get("metrics") or {}).get(metric_name) or {}
    values = metric.get("values") or {}
    if value_name in values:
        return values.get(value_name, default)
    if value_name in metric:
        return metric.get(value_name, default)
    if value_name == "rate":
        return metric.get("rate", metric.get("value", default))
    return default


def _k6_component(path, max_p95_ms, max_fail_rate, min_checks_rate):
    payload, source = _read_json(path)
    if payload.get("_read_error"):
        return _component("load-k6", "k6-summary-json", source, "failed", payload["_read_error"])
    p95_ms = _safe_float(_metric(payload, "http_req_duration", "p(95)"))
    fail_rate = _safe_float(_metric(payload, "http_req_failed", "rate"))
    checks_rate = _safe_float(_metric(payload, "checks", "rate"))
    metrics = {
        "p95_ms": p95_ms,
        "fail_rate": fail_rate,
        "checks_rate": checks_rate,
        "max_p95_ms": max_p95_ms,
        "max_fail_rate": max_fail_rate,
        "min_checks_rate": min_checks_rate,
    }
    missing = [
        label
        for label, value in {
            "http_req_duration p95": p95_ms,
            "http_req_failed rate": fail_rate,
            "checks rate": checks_rate,
        }.items()
        if value is None
    ]
    if missing:
        return _component(
            "load-k6",
            "k6-summary-json",
            source,
            "warning",
            "k6 summary is missing metric(s): %s." % ", ".join(missing),
            metrics,
        )
    failures = []
    if p95_ms > max_p95_ms:
        failures.append("p95 %.4f > %.4f" % (p95_ms, max_p95_ms))
    if fail_rate > max_fail_rate:
        failures.append("failure rate %.4f > %.4f" % (fail_rate, max_fail_rate))
    if checks_rate < min_checks_rate:
        failures.append("checks rate %.4f < %.4f" % (checks_rate, min_checks_rate))
    if failures:
        return _component("load-k6", "k6-summary-json", source, "failed", "; ".join(failures), metrics)
    return _component("load-k6", "k6-summary-json", source, "passed", "k6 summary meets thresholds.", metrics)


def _status_tsv(components):
    lines = ["check\tstatus\tdecision\tci_status\ttype\tsource\tmessage"]
    lines.extend(
        "%s\t%s\t%s\t%s\t%s\t%s\t%s"
        % (
            component["name"],
            component["status"],
            component["decision"],
            component["ci_status"],
            component["evidence_type"],
            component.get("source") or "",
            component["message"],
        )
        for component in components
    )
    return "\n".join(lines)


def _summary(context, components, blockers, warnings):
    component_lines = "\n".join(
        "- %s: %s - %s" % (component["name"], component["status"], component["message"])
        for component in components
    ) or "- No tool evidence components attached."
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Operations Tool Evidence

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Strict: {context["strict"]}
- Fail on warning: {context["fail_on_warning"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Components

{component_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Operations tool evidence manifest: ops-tool-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export structured evidence from production operations tool outputs.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_OPS_TOOL_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_OPS_TOOL_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_OPS_TOOL_OUTPUT", ""))
    parser.add_argument("--restore-drill-log", default=os.environ.get("TIJARA_OPS_TOOL_RESTORE_DRILL_LOG", ""))
    parser.add_argument("--restore-drill-exit-code", default=os.environ.get("TIJARA_OPS_TOOL_RESTORE_DRILL_EXIT_CODE", ""))
    parser.add_argument("--backup-artifact-ref", default=os.environ.get("TIJARA_OPS_TOOL_BACKUP_ARTIFACT_REF", ""))
    parser.add_argument("--security-audit-log", default=os.environ.get("TIJARA_OPS_TOOL_SECURITY_AUDIT_LOG", ""))
    parser.add_argument("--security-audit-exit-code", default=os.environ.get("TIJARA_OPS_TOOL_SECURITY_AUDIT_EXIT_CODE", ""))
    parser.add_argument("--dependency-scan-log", default=os.environ.get("TIJARA_OPS_TOOL_DEPENDENCY_SCAN_LOG", ""))
    parser.add_argument("--dependency-scan-exit-code", default=os.environ.get("TIJARA_OPS_TOOL_DEPENDENCY_SCAN_EXIT_CODE", ""))
    parser.add_argument("--container-scan-log", default=os.environ.get("TIJARA_OPS_TOOL_CONTAINER_SCAN_LOG", ""))
    parser.add_argument("--container-scan-exit-code", default=os.environ.get("TIJARA_OPS_TOOL_CONTAINER_SCAN_EXIT_CODE", ""))
    parser.add_argument("--trivy-json", action="append", default=_csv_items(os.environ.get("TIJARA_OPS_TOOL_TRIVY_JSON")))
    parser.add_argument("--npm-audit-json", action="append", default=_csv_items(os.environ.get("TIJARA_OPS_TOOL_NPM_AUDIT_JSON")))
    parser.add_argument("--pip-audit-json", action="append", default=_csv_items(os.environ.get("TIJARA_OPS_TOOL_PIP_AUDIT_JSON")))
    parser.add_argument("--k6-summary-json", action="append", default=_csv_items(os.environ.get("TIJARA_OPS_TOOL_K6_SUMMARY_JSON")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--max-p95-ms", type=float, default=float(os.environ.get("TIJARA_OPS_TOOL_MAX_P95_MS", "1000")))
    parser.add_argument("--max-fail-rate", type=float, default=float(os.environ.get("TIJARA_OPS_TOOL_MAX_FAIL_RATE", "0.05")))
    parser.add_argument("--min-checks-rate", type=float, default=float(os.environ.get("TIJARA_OPS_TOOL_MIN_CHECKS_RATE", "0.95")))
    parser.add_argument("--strict", action="store_true", default=_truthy(os.environ.get("TIJARA_OPS_TOOL_STRICT", "0")))
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_OPS_TOOL_FAIL_ON_WARNING", "0")))
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/ops-tool-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        metadata_error = str(error)
    else:
        metadata_error = ""

    components = []
    restore_component = _log_component(
        "restore-drill",
        "restore-drill-log",
        args.restore_drill_log,
        _safe_int(args.restore_drill_exit_code),
        "Restore drill passed",
        references={"backup_artifact_ref": args.backup_artifact_ref},
    )
    if restore_component:
        components.append(restore_component)
    security_component = _log_component(
        "security-audit",
        "security-audit-log",
        args.security_audit_log,
        _safe_int(args.security_audit_exit_code),
        "Tijara security audit baseline passed",
    )
    if security_component:
        components.append(security_component)
    dependency_component = _log_component(
        "dependency-scan",
        "dependency-scan-log",
        args.dependency_scan_log,
        _safe_int(args.dependency_scan_exit_code),
    )
    if dependency_component:
        components.append(dependency_component)
    container_component = _log_component(
        "container-scan",
        "container-scan-log",
        args.container_scan_log,
        _safe_int(args.container_scan_exit_code),
    )
    if container_component:
        components.append(container_component)

    components.extend(_trivy_component(path) for path in args.trivy_json)
    components.extend(_npm_audit_component(path) for path in args.npm_audit_json)
    components.extend(_pip_audit_component(path) for path in args.pip_audit_json)
    components.extend(
        _k6_component(path, args.max_p95_ms, args.max_fail_rate, args.min_checks_rate)
        for path in args.k6_summary_json
    )

    blockers = []
    warnings = []
    if metadata_error:
        blockers.append(metadata_error)
    if not components:
        message = "No operations tool outputs were attached."
        if args.strict:
            blockers.append(message)
        else:
            warnings.append(message)
    for component in components:
        if component["status"] == "failed":
            blockers.append("%s: %s" % (component["name"], component["message"]))
        elif component["status"] == "warning":
            warnings.append("%s: %s" % (component["name"], component["message"]))

    if args.fail_on_warning and warnings:
        blockers.extend("warning-policy: %s" % warning for warning in warnings)
        warnings = []

    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    status_counts = {}
    component_refs = {}
    for component in components:
        status_counts[component["status"]] = status_counts.get(component["status"], 0) + 1
        if component["status"] == "passed":
            component_refs.setdefault(component["name"], []).append(component.get("source") or component["evidence_type"])

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "strict": bool(args.strict),
        "fail_on_warning": bool(args.fail_on_warning),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "components": components,
        "status_counts": status_counts,
        "component_refs": component_refs,
        "metadata": metadata,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "strict=%s" % int(args.strict),
            "fail_on_warning=%s" % int(args.fail_on_warning),
            "restore_drill_log=%s" % (args.restore_drill_log or "<unset>"),
            "security_audit_log=%s" % (args.security_audit_log or "<unset>"),
            "dependency_scan_log=%s" % (args.dependency_scan_log or "<unset>"),
            "container_scan_log=%s" % (args.container_scan_log or "<unset>"),
            "trivy_json=%s" % (",".join(args.trivy_json) or "<unset>"),
            "npm_audit_json=%s" % (",".join(args.npm_audit_json) or "<unset>"),
            "pip_audit_json=%s" % (",".join(args.pip_audit_json) or "<unset>"),
            "k6_summary_json=%s" % (",".join(args.k6_summary_json) or "<unset>"),
            "backup_artifact_ref=%s" % ("<set>" if args.backup_artifact_ref else "<unset>"),
        ]
    )
    _write(output / "ops-tool-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(components))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, components, blockers, warnings))

    print("Operations tool evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
