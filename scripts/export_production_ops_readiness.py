#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
GOOD_DECISIONS = {"approved", "dry-run", "executed", "pass", "passed", "ready"}
WARN_DECISIONS = {"passed-with-skips", "pass_with_warnings", "skipped", "warn", "warning"}
BAD_DECISIONS = {"blocked", "error", "fail", "failed"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve(value):
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _read_json(path):
    target = _resolve(path)
    if not target or not target.is_file():
        return {}, str(target or "")
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        return {"_read_error": str(error)}, str(target)


def _read_status_rows(path):
    target = _resolve(path)
    if not target or not target.is_file():
        return [], str(target or "")
    try:
        raw_lines = [line.rstrip("\n") for line in target.read_text(encoding="utf-8").splitlines()]
    except OSError as error:
        return [{"name": "status-file", "status": "failed", "message": str(error), "source": str(target)}], str(target)
    lines = [line for line in raw_lines if line.strip()]
    if not lines:
        return [], str(target)
    header = [item.strip().lower() for item in lines[0].split("\t")]
    has_header = "status" in header and ("check" in header or "name" in header)
    data_lines = lines[1:] if has_header else lines
    rows = []
    for line in data_lines:
        parts = line.split("\t")
        if has_header:
            values = dict(zip(header, parts))
            name = values.get("check") or values.get("name") or ""
            status = values.get("status") or ""
            message = values.get("message") or values.get("log_file") or values.get("source") or ""
        else:
            name = parts[0] if len(parts) > 0 else ""
            status = parts[1] if len(parts) > 1 else ""
            message = parts[4] if len(parts) > 4 else (parts[3] if len(parts) > 3 else "")
        rows.append(
            {
                "name": name.strip(),
                "status": status.strip(),
                "message": message.strip(),
                "source": str(target),
            }
        )
    return rows, str(target)


def _normalized_decision(payload):
    if not payload:
        return ""
    return str(payload.get("decision") or payload.get("status") or payload.get("ci_status") or "").strip().lower()


def _normalized_ci(payload):
    if not payload:
        return ""
    return str(payload.get("ci_status") or "").strip().lower()


def _component(name, label, payload, source, required, evidence_type="json"):
    if payload.get("_read_error"):
        return {
            "name": name,
            "label": label,
            "status": "failed",
            "required": required,
            "source": source,
            "evidence_type": evidence_type,
            "decision": "",
            "ci_status": "",
            "message": "Could not read evidence: %s" % payload["_read_error"],
        }
    if not payload:
        return {
            "name": name,
            "label": label,
            "status": "failed" if required else "warning",
            "required": required,
            "source": source,
            "evidence_type": evidence_type,
            "decision": "",
            "ci_status": "",
            "message": "%s evidence is missing." % label,
        }
    decision = _normalized_decision(payload)
    ci_status = _normalized_ci(payload)
    if decision in BAD_DECISIONS or ci_status == "fail":
        status = "failed"
    elif decision in WARN_DECISIONS or ci_status == "pass_with_warnings":
        status = "warning"
    elif decision in GOOD_DECISIONS and ci_status in {"", "pass"}:
        status = "passed"
    else:
        status = "warning"
    return {
        "name": name,
        "label": label,
        "status": status,
        "required": required,
        "source": source,
        "evidence_type": evidence_type,
        "decision": payload.get("decision") or payload.get("status") or "",
        "ci_status": payload.get("ci_status") or "",
        "message": "%s decision is %s/%s." % (label, decision or "empty", ci_status or "empty"),
    }


def _status_component(name, label, rows, source, required):
    if not rows:
        return {
            "name": name,
            "label": label,
            "status": "failed" if required else "warning",
            "required": required,
            "source": source,
            "evidence_type": "status.tsv",
            "decision": "",
            "ci_status": "",
            "message": "%s status rows are missing." % label,
        }
    failed = [row for row in rows if row["status"].strip().lower() in {"blocked", "error", "failed"}]
    warnings = [row for row in rows if row["status"].strip().lower() in {"skipped", "warn", "warning"}]
    if failed:
        status = "failed"
    elif warnings:
        status = "warning"
    else:
        status = "passed"
    return {
        "name": name,
        "label": label,
        "status": status,
        "required": required,
        "source": source,
        "evidence_type": "status.tsv",
        "decision": status,
        "ci_status": "fail" if status == "failed" else ("pass_with_warnings" if status == "warning" else "pass"),
        "message": "%s status rows passed/warning/failed: %s/%s/%s."
        % (label, len(rows) - len(warnings) - len(failed), len(warnings), len(failed)),
    }


def _find_status(rows, names):
    wanted = {name.lower() for name in names}
    found = []
    for row in rows:
        name = row["name"].strip().lower()
        if name in wanted:
            found.append(row)
    return found


def _has_incident_ref(payload, section, key):
    refs = payload.get(section) or {}
    return bool(refs.get(key))


def _has_deployment_env_ref(payload, key):
    environment = payload.get("environment") or {}
    return bool(environment.get(key))


def _reference_component(name, label, value, required):
    return {
        "name": name,
        "label": label,
        "status": "passed" if value else ("failed" if required else "warning"),
        "required": required,
        "source": str(value or ""),
        "evidence_type": "reference",
        "decision": "passed" if value else "",
        "ci_status": "pass" if value else "",
        "message": "%s is %s." % (label, "recorded" if value else "missing"),
    }


def _ops_tool_passed_refs(payloads, names, reference_key=""):
    wanted = {name.lower() for name in names}
    refs = []
    for payload, source in payloads:
        if str(payload.get("decision") or "").strip().lower() in BAD_DECISIONS:
            continue
        for component in payload.get("components") or []:
            name = str(component.get("name") or "").strip().lower()
            status = str(component.get("status") or "").strip().lower()
            if name in wanted and status == "passed":
                references = component.get("references") or {}
                refs.append(references.get(reference_key) if reference_key else component.get("source") or source)
    return ",".join(ref for ref in refs if ref)


def _status_tsv(components):
    lines = ["check\tstatus\trequired\tdecision\tci_status\tsource\tmessage"]
    lines.extend(
        "%s\t%s\t%s\t%s\t%s\t%s\t%s"
        % (
            component["name"],
            component["status"],
            int(bool(component["required"])),
            component.get("decision") or "",
            component.get("ci_status") or "",
            component.get("source") or "",
            component["message"],
        )
        for component in components
    )
    return "\n".join(lines)


def _summary(context, components, ops_status_rows, blockers, warnings):
    component_lines = "\n".join(
        "- %s: %s - %s" % (component["name"], component["status"], component["message"])
        for component in components
    ) or "- No components reviewed."
    status_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"])
        for row in ops_status_rows
    ) or "- No operations status rows attached."
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Production Operations Readiness Evidence

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

## Operations Status Rows

{status_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Production operations readiness manifest: production-ops-readiness.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(
        description="Export a CI-friendly production operations readiness verdict."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROD_OPS_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_PROD_OPS_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROD_OPS_OUTPUT", ""))
    parser.add_argument("--operations-bundle", default=os.environ.get("TIJARA_PROD_OPS_OPERATIONS_BUNDLE", ""))
    parser.add_argument("--monitoring-evidence", default=os.environ.get("TIJARA_PROD_OPS_MONITORING_EVIDENCE", ""))
    parser.add_argument("--incident-runbook-evidence", default=os.environ.get("TIJARA_PROD_OPS_INCIDENT_RUNBOOK_EVIDENCE", ""))
    parser.add_argument("--load-evidence", action="append", default=_csv_items(os.environ.get("TIJARA_PROD_OPS_LOAD_EVIDENCE")))
    parser.add_argument("--load-profile-matrix", default=os.environ.get("TIJARA_PROD_OPS_LOAD_PROFILE_MATRIX", ""))
    parser.add_argument("--release-retention-evidence", default=os.environ.get("TIJARA_PROD_OPS_RELEASE_RETENTION_EVIDENCE", ""))
    parser.add_argument("--secret-manager-evidence", default=os.environ.get("TIJARA_PROD_OPS_SECRET_MANAGER_EVIDENCE", ""))
    parser.add_argument("--secret-runtime-evidence", default=os.environ.get("TIJARA_PROD_OPS_SECRET_RUNTIME_EVIDENCE", ""))
    parser.add_argument("--deployment-environment-evidence", default=os.environ.get("TIJARA_PROD_OPS_DEPLOYMENT_ENVIRONMENT_EVIDENCE", ""))
    parser.add_argument("--tenant-ops-evidence", default=os.environ.get("TIJARA_PROD_OPS_TENANT_OPS_EVIDENCE", ""))
    parser.add_argument("--ops-tool-evidence", action="append", default=_csv_items(os.environ.get("TIJARA_PROD_OPS_TOOL_EVIDENCE")))
    parser.add_argument("--ops-status", action="append", default=_csv_items(os.environ.get("TIJARA_PROD_OPS_STATUS")))
    parser.add_argument("--release-readiness", default=os.environ.get("TIJARA_PROD_OPS_RELEASE_READINESS", ""))
    parser.add_argument("--backup-artifact-ref", default=os.environ.get("TIJARA_PROD_OPS_BACKUP_ARTIFACT_REF", ""))
    parser.add_argument("--restore-drill-ref", default=os.environ.get("TIJARA_PROD_OPS_RESTORE_DRILL_REF", ""))
    parser.add_argument("--security-audit-ref", default=os.environ.get("TIJARA_PROD_OPS_SECURITY_AUDIT_REF", ""))
    parser.add_argument("--dependency-scan-ref", default=os.environ.get("TIJARA_PROD_OPS_DEPENDENCY_SCAN_REF", ""))
    parser.add_argument("--container-scan-ref", default=os.environ.get("TIJARA_PROD_OPS_CONTAINER_SCAN_REF", ""))
    parser.add_argument("--require-tenant-ops", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_REQUIRE_TENANT_OPS", "1")))
    parser.add_argument("--require-secret-runtime", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_REQUIRE_SECRET_RUNTIME", "1")))
    parser.add_argument("--require-release-readiness", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_REQUIRE_RELEASE_READINESS", "0")))
    parser.add_argument("--strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_STRICT", "0")))
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_FAIL_ON_WARNING", "0")))
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/production-ops-readiness" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    components = []
    evidence_refs = {}

    operations_bundle, operations_bundle_path = _read_json(args.operations_bundle)
    monitoring, monitoring_path = _read_json(args.monitoring_evidence)
    incident, incident_path = _read_json(args.incident_runbook_evidence)
    load_matrix, load_matrix_path = _read_json(args.load_profile_matrix)
    retention, retention_path = _read_json(args.release_retention_evidence)
    secret_manager, secret_manager_path = _read_json(args.secret_manager_evidence)
    secret_runtime, secret_runtime_path = _read_json(args.secret_runtime_evidence)
    deployment_environment, deployment_environment_path = _read_json(args.deployment_environment_evidence)
    tenant_ops, tenant_ops_path = _read_json(args.tenant_ops_evidence)
    release_readiness, release_readiness_path = _read_json(args.release_readiness)
    ops_tool_payloads = []
    for raw_path in args.ops_tool_evidence:
        payload, source = _read_json(raw_path)
        ops_tool_payloads.append((payload, source))

    for key, value in {
        "operations_bundle": operations_bundle_path,
        "monitoring": monitoring_path,
        "incident_runbook": incident_path,
        "load_profile_matrix": load_matrix_path,
        "release_retention": retention_path,
        "secret_manager": secret_manager_path,
        "secret_runtime": secret_runtime_path,
        "deployment_environment": deployment_environment_path,
        "tenant_ops": tenant_ops_path,
        "release_readiness": release_readiness_path,
    }.items():
        if value:
            evidence_refs[key] = value
    if ops_tool_payloads:
        evidence_refs["ops_tool"] = [source for _payload, source in ops_tool_payloads if source]

    required = bool(args.strict)
    components.append(_component("operations-bundle", "Operations release bundle", operations_bundle, operations_bundle_path, required))
    components.append(_component("monitoring", "Monitoring evidence", monitoring, monitoring_path, required))
    components.append(_component("incident-runbook", "Incident runbook evidence", incident, incident_path, required))
    components.append(_component("load-profile-matrix", "Load profile matrix", load_matrix, load_matrix_path, required))
    components.append(_component("release-retention", "Release retention evidence", retention, retention_path, required))
    components.append(_component("secret-manager", "Secret manager evidence", secret_manager, secret_manager_path, required))
    components.append(_component("secret-runtime", "Secret runtime evidence", secret_runtime, secret_runtime_path, required and args.require_secret_runtime))
    components.append(_component("deployment-environment", "Deployment environment evidence", deployment_environment, deployment_environment_path, required))
    components.append(_component("tenant-ops", "Tenant operations evidence", tenant_ops, tenant_ops_path, required and args.require_tenant_ops))
    components.append(_component("release-readiness", "Release readiness evidence", release_readiness, release_readiness_path, args.require_release_readiness))
    for index, (payload, source) in enumerate(ops_tool_payloads, start=1):
        components.append(
            _component(
                "ops-tool-evidence-%s" % index,
                "Operations tool evidence %s" % index,
                payload,
                source,
                False,
            )
        )

    load_components = []
    for index, raw_path in enumerate(args.load_evidence, start=1):
        payload, source = _read_json(raw_path)
        evidence_refs["load_%s" % index] = source
        load_components.append(_component("load-evidence-%s" % index, "Load evidence %s" % index, payload, source, required))
    ops_tool_load_ref = _ops_tool_passed_refs(ops_tool_payloads, {"load-k6"})
    if load_components:
        components.extend(load_components)
    elif ops_tool_load_ref:
        components.append(_reference_component("load-evidence", "Load evidence", ops_tool_load_ref, required))
    else:
        components.append(
            {
                "name": "load-evidence",
                "label": "Load evidence",
                "status": "failed" if required else "warning",
                "required": required,
                "source": "",
                "evidence_type": "json",
                "decision": "",
                "ci_status": "",
                "message": "No load evidence JSON path was attached.",
            }
        )

    ops_status_rows = []
    ops_status_sources = []
    for raw_status in args.ops_status:
        rows, source = _read_status_rows(raw_status)
        ops_status_rows.extend(rows)
        if source:
            ops_status_sources.append(source)
    if ops_status_sources:
        evidence_refs["ops_status"] = ops_status_sources
    components.append(_status_component("ops-status", "Operations status table", ops_status_rows, ",".join(ops_status_sources), required))

    restore_status_rows = _find_status(ops_status_rows, {"restore-drill"})
    dependency_status_rows = _find_status(ops_status_rows, {"dependency-scan"})
    container_status_rows = _find_status(ops_status_rows, {"container-scan"})
    backup_ref = args.backup_artifact_ref or (
        "incident-runbook" if _has_incident_ref(incident, "references", "backup_reference_present") else ""
    ) or (
        "deployment-environment" if _has_deployment_env_ref(deployment_environment, "backup_policy_ref_present") else ""
    ) or _ops_tool_passed_refs(ops_tool_payloads, {"restore-drill"}, "backup_artifact_ref")
    restore_ref = args.restore_drill_ref or _ops_tool_passed_refs(ops_tool_payloads, {"restore-drill"}) or (
        "incident-runbook" if _has_incident_ref(incident, "references", "restore_drill_reference_present") else ""
    )
    if restore_status_rows and not restore_ref:
        passed_restore = [row for row in restore_status_rows if row["status"].strip().lower() == "passed"]
        if passed_restore:
            restore_ref = ",".join(row["source"] for row in passed_restore)
    dependency_ref = args.dependency_scan_ref or _ops_tool_passed_refs(ops_tool_payloads, {"dependency-scan"})
    if dependency_status_rows and not dependency_ref:
        passed_dependency = [row for row in dependency_status_rows if row["status"].strip().lower() == "passed"]
        if passed_dependency:
            dependency_ref = ",".join(row["source"] for row in passed_dependency)
    container_ref = args.container_scan_ref or _ops_tool_passed_refs(ops_tool_payloads, {"container-scan"})
    if container_status_rows and not container_ref:
        passed_container = [row for row in container_status_rows if row["status"].strip().lower() == "passed"]
        if passed_container:
            container_ref = ",".join(row["source"] for row in passed_container)

    components.append(_reference_component("backup-artifact", "Backup artifact reference", backup_ref, required))
    components.append(_reference_component("restore-drill", "Restore drill reference", restore_ref, required))
    components.append(
        _reference_component(
            "security-audit",
            "Security audit reference",
            args.security_audit_ref or _ops_tool_passed_refs(ops_tool_payloads, {"security-audit"}),
            required,
        )
    )
    components.append(_reference_component("dependency-scan", "Dependency scan reference", dependency_ref, required))
    components.append(_reference_component("container-scan", "Container scan reference", container_ref, required))

    blockers = []
    warnings = []
    for component in components:
        if component["status"] == "failed":
            blockers.append("%s: %s" % (component["name"], component["message"]))
        elif component["status"] in {"warning", "skipped"}:
            warnings.append("%s: %s" % (component["name"], component["message"]))

    if args.fail_on_warning and warnings:
        blockers.extend("warning-policy: %s" % warning for warning in warnings)
        warnings = []

    if blockers:
        decision = "blocked"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "ready"
        ci_status = "pass"

    status_counts = {}
    for component in components:
        status_counts[component["status"]] = status_counts.get(component["status"], 0) + 1

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": str(output),
        "strict": bool(args.strict),
        "fail_on_warning": bool(args.fail_on_warning),
        "require_tenant_ops": bool(args.require_tenant_ops),
        "require_secret_runtime": bool(args.require_secret_runtime),
        "require_release_readiness": bool(args.require_release_readiness),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "components": components,
        "status_counts": status_counts,
        "ops_status_rows": ops_status_rows,
        "evidence_refs": evidence_refs,
        "references": {
            "backup_artifact_ref_present": bool(backup_ref),
            "restore_drill_ref_present": bool(restore_ref),
            "security_audit_ref_present": bool(args.security_audit_ref),
            "dependency_scan_ref_present": bool(dependency_ref),
            "container_scan_ref_present": bool(container_ref),
        },
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "strict=%s" % int(args.strict),
            "fail_on_warning=%s" % int(args.fail_on_warning),
            "operations_bundle=%s" % (operations_bundle_path or "<unset>"),
            "monitoring_evidence=%s" % (monitoring_path or "<unset>"),
            "incident_runbook_evidence=%s" % (incident_path or "<unset>"),
            "load_evidence=%s" % (",".join(args.load_evidence) or "<unset>"),
            "load_profile_matrix=%s" % (load_matrix_path or "<unset>"),
            "release_retention_evidence=%s" % (retention_path or "<unset>"),
            "secret_manager_evidence=%s" % (secret_manager_path or "<unset>"),
            "secret_runtime_evidence=%s" % (secret_runtime_path or "<unset>"),
            "deployment_environment_evidence=%s" % (deployment_environment_path or "<unset>"),
            "tenant_ops_evidence=%s" % (tenant_ops_path or "<unset>"),
            "ops_tool_evidence=%s" % (",".join(args.ops_tool_evidence) or "<unset>"),
            "ops_status=%s" % (",".join(ops_status_sources) or "<unset>"),
            "backup_artifact_ref=%s" % ("<set>" if args.backup_artifact_ref else "<unset>"),
            "restore_drill_ref=%s" % ("<set>" if args.restore_drill_ref else "<unset>"),
            "security_audit_ref=%s" % ("<set>" if args.security_audit_ref else "<unset>"),
            "dependency_scan_ref=%s" % ("<set>" if args.dependency_scan_ref else "<unset>"),
            "container_scan_ref=%s" % ("<set>" if args.container_scan_ref else "<unset>"),
        ]
    )

    _write(output / "production-ops-readiness.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(components))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, components, ops_status_rows, blockers, warnings))

    print("Production operations readiness evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
