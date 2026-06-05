#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve_output(path, run_id):
    output = Path(path) if path else ROOT_DIR / "deploy/runtime/operations-release-bundle" / run_id
    return output if output.is_absolute() else ROOT_DIR / output


def _safe_env_value(value):
    return "<set>" if value else "<unset>"


def _read_json(path):
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _decision_status(payload):
    decision = str(payload.get("decision") or payload.get("status") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in {"passed", "ready", "dry-run", "executed"} and ci_status in {"", "pass"}:
        return "passed"
    if decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        return "warning"
    if decision in {"failed", "blocked"} or ci_status == "fail":
        return "failed"
    if decision:
        return "warning"
    return "missing"


def _run_step(name, command, env, output_dir):
    log_file = output_dir / ("%s.log" % name)
    with log_file.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return result.returncode, str(log_file)


def _step_specs(args, output):
    matrix_dir = output / "load-profile-matrix"
    load_dir = output / "load-enterprise"
    smoke_dir = output / "production-smoke"
    tenant_smoke_dir = output / "tenant-smoke"
    monitoring_dir = output / "monitoring-evidence"
    incident_dir = output / "incident-runbook"
    retention_dir = output / "release-retention"
    smoke_decision = smoke_dir / "smoke-decision.json"
    tenant_smoke_evidence = tenant_smoke_dir / "tenant-smoke-evidence.json"
    monitoring_evidence = monitoring_dir / "monitoring-evidence.json"

    specs = {
        "load-matrix": {
            "label": "load-profile-matrix",
            "output": matrix_dir,
            "manifest": matrix_dir / "load-profile-matrix.json",
            "command": [
                sys.executable,
                "scripts/export_load_profile_matrix.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(matrix_dir),
            ],
        },
        "load-enterprise": {
            "label": "load-enterprise",
            "output": load_dir,
            "manifest": load_dir / "load-evidence.json",
            "command": ["bash", "scripts/run_load_profile.sh", "enterprise-surfaces"],
            "env": {
                "TIJARA_LOAD_RUN_ID": args.run_id,
                "TIJARA_LOAD_OUTPUT": str(load_dir),
                "TIJARA_LOAD_ENVIRONMENT": args.target_environment,
                "TIJARA_LOAD_PROFILE": "enterprise-surfaces",
            },
        },
        "smoke": {
            "label": "production-smoke",
            "output": smoke_dir,
            "manifest": smoke_decision,
            "command": [
                sys.executable,
                "scripts/run_production_smoke.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(smoke_dir),
            ],
        },
        "tenant-smoke": {
            "label": "tenant-smoke",
            "output": tenant_smoke_dir,
            "manifest": tenant_smoke_dir / "tenant-smoke-evidence.json",
            "command": [
                sys.executable,
                "scripts/run_tenant_smoke.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(tenant_smoke_dir),
            ],
        },
        "monitoring": {
            "label": "monitoring-evidence",
            "output": monitoring_dir,
            "manifest": monitoring_evidence,
            "command": [
                sys.executable,
                "scripts/export_monitoring_evidence.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(monitoring_dir),
            ],
        },
        "incident": {
            "label": "incident-runbook",
            "output": incident_dir,
            "manifest": incident_dir / "incident-runbook-evidence.json",
            "command": [
                sys.executable,
                "scripts/export_incident_runbook_evidence.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(incident_dir),
            ],
        },
        "retention": {
            "label": "release-retention",
            "output": retention_dir,
            "manifest": retention_dir / "release-retention-evidence.json",
            "command": [
                sys.executable,
                "scripts/export_release_retention_evidence.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(retention_dir),
                "--evidence-path",
                str(matrix_dir),
                "--evidence-path",
                str(load_dir),
                "--evidence-path",
                str(smoke_dir),
                "--evidence-path",
                str(monitoring_dir),
                "--evidence-path",
                str(incident_dir),
            ],
        },
    }

    if args.strict:
        specs["load-matrix"]["command"].append("--strict")
        specs["incident"]["command"].append("--strict")
        specs["retention"]["command"].append("--strict")
        specs["tenant-smoke"]["command"].append("--strict")
        specs["load-enterprise"]["env"]["TIJARA_LOAD_STRICT"] = "1"
    else:
        specs["smoke"]["command"].append("--non-strict")
        specs["monitoring"]["command"].append("--non-strict")
        specs["retention"]["command"].append("--non-strict")
        specs["tenant-smoke"]["command"].append("--non-strict")
        specs["load-enterprise"]["env"]["TIJARA_LOAD_STRICT"] = "0"

    smoke_base_url = args.smoke_base_url or args.base_url
    if smoke_base_url:
        specs["smoke"]["command"].extend(["--base-url", smoke_base_url])

    for smoke_url in args.smoke_url:
        specs["smoke"]["command"].extend(["--url", smoke_url])

    for tenant_artifact in args.tenant_artifact:
        specs["tenant-smoke"]["command"].extend(["--tenant-artifact", tenant_artifact])
    for tenant_base_url in args.tenant_base_url:
        specs["tenant-smoke"]["command"].extend(["--tenant-base-url", tenant_base_url])
    for tenant_route in args.tenant_route:
        specs["tenant-smoke"]["command"].extend(["--tenant-route", tenant_route])
    for route in args.tenant_smoke_route:
        specs["tenant-smoke"]["command"].extend(["--route", route])
    if args.tenant_smoke_skip_monitoring:
        specs["tenant-smoke"]["command"].append("--skip-monitoring-route")

    if args.monitoring_url:
        for monitoring_url in args.monitoring_url:
            specs["monitoring"]["command"].extend(["--url", monitoring_url])
    if args.prometheus_url:
        specs["monitoring"]["command"].extend(["--prometheus-url", args.prometheus_url])
    if args.alertmanager_url:
        specs["monitoring"]["command"].extend(["--alertmanager-url", args.alertmanager_url])
    if args.grafana_url:
        specs["monitoring"]["command"].extend(["--grafana-url", args.grafana_url])

    if smoke_decision.is_file() or "smoke" in args.checks:
        specs["monitoring"]["command"].extend(["--smoke-decision", str(smoke_decision)])
    if tenant_smoke_evidence.is_file() or "tenant-smoke" in args.checks:
        specs["monitoring"]["command"].extend(["--tenant-smoke-evidence", str(tenant_smoke_evidence)])
    if args.deployment_decision:
        specs["monitoring"]["command"].extend(["--deployment-decision", args.deployment_decision])
        specs["smoke"]["command"].extend(["--deployment-decision", args.deployment_decision])
    if args.rollback_decision:
        specs["monitoring"]["command"].extend(["--rollback-decision", args.rollback_decision])
        specs["smoke"]["command"].extend(["--rollback-decision", args.rollback_decision])

    if monitoring_evidence.is_file() or "monitoring" in args.checks:
        specs["incident"]["command"].extend(["--monitoring-reference", str(monitoring_evidence)])
    return specs


def _classify_step(name, spec, exit_code, log_file, strict):
    manifest = _read_json(spec["manifest"])
    decision_status = _decision_status(manifest)
    message = ""
    if not manifest:
        message = "No manifest produced."
        status = "failed" if strict else "warning"
    elif decision_status == "missing":
        message = "Manifest decision is missing."
        status = "failed" if strict else "warning"
    else:
        status = decision_status
        message = "decision=%s ci_status=%s" % (
            manifest.get("decision") or manifest.get("status") or "<unset>",
            manifest.get("ci_status") or "<unset>",
        )
    if exit_code != 0 and status == "passed":
        status = "failed" if strict else "warning"
        message = "%s; command exited %s" % (message, exit_code)
    elif exit_code != 0 and status == "warning":
        message = "%s; command exited %s" % (message, exit_code)
    return {
        "name": name,
        "label": spec["label"],
        "status": status,
        "exit_code": exit_code,
        "log_file": log_file,
        "manifest": str(spec["manifest"]),
        "output": str(spec["output"]),
        "message": message,
        "decision": manifest.get("decision") or manifest.get("status") or "",
        "ci_status": manifest.get("ci_status") or "",
    }


def _status_tsv(rows):
    lines = ["check\tstatus\texit_code\tmanifest\tlog_file\tmessage"]
    lines.extend(
        "%s\t%s\t%s\t%s\t%s\t%s"
        % (
            row["name"],
            row["status"],
            row["exit_code"],
            row["manifest"],
            row["log_file"],
            row["message"],
        )
        for row in rows
    )
    return "\n".join(lines)


def _summary(context, rows, blockers, warnings):
    result_lines = "\n".join(
        "- %s: %s (exit %s) - %s - %s"
        % (row["name"], row["status"], row["exit_code"], row["message"], row["manifest"])
        for row in rows
    ) or "- No bundle checks ran."
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    evidence_lines = "\n".join("- %s: %s" % (row["name"], row["output"]) for row in rows)
    return f"""
# Operations Release Evidence Bundle

- Status: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Strict: {context["strict"]}
- Fail on warning: {context["fail_on_warning"]}
- Output directory: {context["output"]}
- Generated: {context["generated_at"]}

## Results

{result_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Directories

{evidence_lines}

## Evidence Files

- Operations bundle manifest: operations-release-bundle.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Run Tijara operations release evidence bundle.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_OPS_BUNDLE_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_OPS_BUNDLE_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_OPS_BUNDLE_OUTPUT", ""))
    parser.add_argument("--checks", default=os.environ.get("TIJARA_OPS_BUNDLE_CHECKS", "load-matrix,load-enterprise,smoke,monitoring,incident,retention"))
    parser.add_argument("--base-url", default=os.environ.get("TIJARA_BASE_URL", ""))
    parser.add_argument("--smoke-base-url", default=os.environ.get("TIJARA_SMOKE_BASE_URL", ""))
    parser.add_argument("--smoke-url", action="append", default=[])
    parser.add_argument("--tenant-artifact", action="append", default=[
        item for item in str(os.environ.get("TIJARA_OPS_BUNDLE_TENANT_SMOKE_ARTIFACTS") or os.environ.get("TIJARA_TENANT_SMOKE_ARTIFACTS") or "").split(",")
        if item.strip()
    ])
    parser.add_argument("--tenant-base-url", action="append", default=[
        item for item in str(os.environ.get("TIJARA_OPS_BUNDLE_TENANT_SMOKE_BASE_URLS") or os.environ.get("TIJARA_TENANT_SMOKE_BASE_URLS") or "").split(",")
        if item.strip()
    ])
    parser.add_argument("--tenant-smoke-route", action="append", default=[])
    parser.add_argument("--tenant-route", action="append", default=[])
    parser.add_argument("--tenant-smoke-skip-monitoring", action="store_true", default=_truthy(os.environ.get("TIJARA_OPS_BUNDLE_TENANT_SMOKE_SKIP_MONITORING")))
    parser.add_argument("--monitoring-url", action="append", default=[])
    parser.add_argument("--prometheus-url", default=os.environ.get("TIJARA_PROMETHEUS_URL", ""))
    parser.add_argument("--alertmanager-url", default=os.environ.get("TIJARA_ALERTMANAGER_URL", ""))
    parser.add_argument("--grafana-url", default=os.environ.get("TIJARA_GRAFANA_URL", ""))
    parser.add_argument("--deployment-decision", default=os.environ.get("TIJARA_OPS_BUNDLE_DEPLOYMENT_DECISION", ""))
    parser.add_argument("--rollback-decision", default=os.environ.get("TIJARA_OPS_BUNDLE_ROLLBACK_DECISION", ""))
    parser.add_argument("--strict", action="store_true", default=_truthy(os.environ.get("TIJARA_OPS_BUNDLE_STRICT", "0")))
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_OPS_BUNDLE_FAIL_ON_WARNING", "0")))
    args = parser.parse_args()
    args.checks = [
        item.strip().lower()
        for item in str(args.checks or "").split(",")
        if item.strip()
    ]
    requested = list(dict.fromkeys(args.checks))
    if args.tenant_artifact and "tenant-smoke" not in requested:
        requested.append("tenant-smoke")
    canonical_order = ["load-matrix", "load-enterprise", "smoke", "tenant-smoke", "monitoring", "incident", "retention"]
    args.checks = [check for check in canonical_order if check in requested] + [
        check for check in requested if check not in canonical_order
    ]

    output = _resolve_output(args.output, args.run_id)
    output.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    specs = _step_specs(args, output)

    rows = []
    for check in args.checks:
        spec = specs.get(check)
        if not spec:
            rows.append(
                {
                    "name": check,
                    "label": check,
                    "status": "failed" if args.strict else "warning",
                    "exit_code": 2,
                    "log_file": "",
                    "manifest": "",
                    "output": "",
                    "message": "Unknown bundle check.",
                    "decision": "",
                    "ci_status": "",
                }
            )
            continue
        spec["output"].mkdir(parents=True, exist_ok=True)
        step_env = os.environ.copy()
        step_env.update(spec.get("env") or {})
        exit_code, log_file = _run_step(check, spec["command"], step_env, output)
        rows.append(_classify_step(check, spec, exit_code, log_file, args.strict))

    blockers = []
    warnings = []
    for row in rows:
        if row["status"] in {"failed", "blocked"}:
            blockers.append("%s: %s" % (row["name"], row["message"]))
        elif row["status"] in {"warning", "warn", "skipped", "missing"}:
            warnings.append("%s: %s" % (row["name"], row["message"]))

    if args.fail_on_warning and warnings:
        blockers.extend("warning requires release owner exception: %s" % warning for warning in warnings)

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
        "strict": bool(args.strict),
        "fail_on_warning": bool(args.fail_on_warning),
        "checks": args.checks,
        "started_at": started_at,
        "generated_at": _utc_now(),
        "output": str(output),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "steps": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "checks=%s" % ",".join(args.checks),
            "strict=%s" % int(args.strict),
            "fail_on_warning=%s" % int(args.fail_on_warning),
            "base_url=%s" % (args.base_url or "<unset>"),
            "smoke_base_url=%s" % (args.smoke_base_url or "<unset>"),
            "tenant_smoke_artifacts=%s" % (",".join(args.tenant_artifact) or "<unset>"),
            "tenant_smoke_base_urls=%s" % (",".join(args.tenant_base_url) or "<unset>"),
            "tenant_smoke_routes=%s" % (",".join(args.tenant_smoke_route) or "<unset>"),
            "tenant_smoke_skip_monitoring=%s" % int(args.tenant_smoke_skip_monitoring),
            "prometheus_url=%s" % (args.prometheus_url or "<unset>"),
            "alertmanager_url=%s" % (args.alertmanager_url or "<unset>"),
            "grafana_url=%s" % (args.grafana_url or "<unset>"),
            "load_matrix_approval=%s/%s"
            % (
                _safe_env_value(os.environ.get("TIJARA_LOAD_MATRIX_APPROVED_BY")),
                _safe_env_value(os.environ.get("TIJARA_LOAD_MATRIX_APPROVAL_REF")),
            ),
            "incident_owners=%s/%s/%s/%s/%s"
            % (
                _safe_env_value(os.environ.get("TIJARA_RELEASE_OWNER")),
                _safe_env_value(os.environ.get("TIJARA_DEVOPS_OWNER")),
                _safe_env_value(os.environ.get("TIJARA_SUPPORT_OWNER")),
                _safe_env_value(os.environ.get("TIJARA_BUSINESS_OWNER")),
                _safe_env_value(os.environ.get("TIJARA_ONCALL_CONTACT")),
            ),
            "retention_store_and_secret_manager=%s/%s"
            % (
                _safe_env_value(os.environ.get("TIJARA_ARTIFACT_STORE_REFERENCE")),
                _safe_env_value(os.environ.get("TIJARA_SECRET_MANAGER_PROVIDER")),
            ),
        ]
    )

    _write(output / "operations-release-bundle.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Operations release evidence bundle written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
