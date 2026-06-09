#!/usr/bin/env python3
"""Run the protected production release evidence chain in one command."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
GOOD_DECISIONS = {"approved", "dry-run", "executed", "pass", "passed", "ready"}
WARN_DECISIONS = {"passed-with-skips", "pass_with_warnings", "skipped", "warn", "warning"}
BAD_DECISIONS = {"blocked", "error", "fail", "failed"}
DEFAULT_INFRA_PROVIDERS = ["cloudflare", "route53", "cert-manager", "postgres"]
DEFAULT_PROVIDER_TEMPLATES = [
    "cloudflare-dns",
    "route53-dns",
    "cert-manager-kubernetes-tls",
    "postgres-backup-restore",
]
INTERESTING_JSON_NAMES = {
    "production-infra-automation.json",
    "infra-provider-readiness.json",
    "production-ops-readiness.json",
    "release-readiness.json",
    "deployment-decision.json",
    "rollback-decision.json",
    "ci-artifact-bundle.json",
    "protected-release-chain.json",
}
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
DEFAULT_PROTECTED_EVIDENCE_DIRS = [
    "deploy/runtime/protected-runbook-handoff/{run_id}",
    "deploy/runtime/protected-first-run/{run_id}",
    "deploy/runtime/protected-runner-preflight/{run_id}",
    "deploy/runtime/protected-runner-bootstrap-verification/{run_id}",
    "deploy/runtime/protected-service-checks/{run_id}",
    "deploy/runtime/protected-provider-readiness/{run_id}",
    "deploy/runtime/protected-payment-lifecycle/{run_id}",
    "deploy/runtime/release-evidence/{run_id}",
    "deploy/runtime/protected-e2e/{run_id}",
    "deploy/runtime/protected-offline-replay/{run_id}",
    "deploy/runtime/protected-offline-pilot/{run_id}",
    "deploy/runtime/e2e-seed/{run_id}",
    "deploy/runtime/e2e-profile/{run_id}",
    "deploy/runtime/e2e-evidence/{run_id}",
    "deploy/runtime/e2e-execution/{run_id}",
    "deploy/runtime/certification-evidence/{run_id}",
]


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("protected-chain-%Y%m%dT%H%M%SZ")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            clean.append(value)
            seen.add(value)
    return clean


def _resolve(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path: str | Path) -> str:
    target = Path(path)
    try:
        return str(target.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(target)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _read_json(path: str | Path) -> dict:
    target = _resolve(path)
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _decision_state(payload: dict) -> str:
    decision = str(payload.get("decision") or payload.get("status") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in BAD_DECISIONS or ci_status == "fail":
        return "failed"
    if decision in WARN_DECISIONS or ci_status == "pass_with_warnings":
        return "warning"
    if decision in GOOD_DECISIONS or ci_status == "pass":
        return "passed"
    return "missing"


def _safe_metadata(items: list[str]) -> tuple[dict[str, str], list[str]]:
    metadata: dict[str, str] = {}
    errors: list[str] = []
    for raw in items:
        if "=" not in raw:
            errors.append("Metadata must use key=value format: %s" % raw)
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            errors.append("Metadata key cannot be blank.")
            continue
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            errors.append("Secret-like metadata keys are not allowed: %s" % key)
            continue
        metadata[key] = value.strip()
    return metadata, errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for raw_path in paths:
        if not raw_path:
            continue
        path = _resolve(raw_path)
        candidates = [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []
        for candidate in candidates:
            if not candidate.is_file():
                continue
            key = str(candidate.resolve())
            if key in seen:
                continue
            seen.add(key)
            files.append(candidate)
    return files


def _run_step(name: str, command: list[str], output: Path, required: bool = True) -> dict:
    log_path = output / "logs" / ("%s.log" % name)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write("$ %s\n\n" % " ".join(command))
        process = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return {
        "name": name,
        "required": bool(required),
        "command": command,
        "exit_code": process.returncode,
        "status": "passed" if process.returncode == 0 else "failed",
        "started_at": started_at,
        "finished_at": _utc_now(),
        "log_file": _repo_relative(log_path),
    }


def _default_path(run_id: str, kind: str) -> str:
    defaults = {
        "operations_bundle": "deploy/runtime/operations-release-bundle/%s/operations-release-bundle.json",
        "monitoring": "deploy/runtime/monitoring-evidence/%s/monitoring-evidence.json",
        "incident": "deploy/runtime/incident-runbooks/%s/incident-runbook-evidence.json",
        "load": "deploy/runtime/operations-release-bundle/%s/load-enterprise/load-evidence.json",
        "load_matrix": "deploy/runtime/operations-release-bundle/%s/load-profile-matrix/load-profile-matrix.json",
        "release_retention": "deploy/runtime/release-retention-evidence/%s/release-retention-evidence.json",
        "secret_manager": "deploy/runtime/secret-manager-evidence/%s/secret-manager-evidence.json",
        "secret_runtime": "deploy/runtime/secret-runtime-evidence/%s/secret-runtime-evidence.json",
        "deployment_environment": "deploy/runtime/deployment-environments/%s/deployment-environment-evidence.json",
        "tenant_ops": "deploy/runtime/tenant-ops-evidence/%s/tenant-ops-evidence.json",
        "ops_tool": "deploy/runtime/ops-tool-evidence/%s/ops-tool-evidence.json",
        "ops_status": "deploy/runtime/ops-tool-evidence/%s/status.tsv",
    }
    return defaults[kind] % run_id


def _existing_or_empty(path: str) -> str:
    return path if path and _resolve(path).exists() else ""


def _default_protected_evidence_paths(run_id: str) -> list[str]:
    paths: list[str] = []
    for template in DEFAULT_PROTECTED_EVIDENCE_DIRS:
        raw_path = template.format(run_id=run_id)
        if _resolve(raw_path).exists():
            paths.append(raw_path)
    return paths


def _production_infra_command(args: argparse.Namespace, run_id: str, output: Path) -> list[str]:
    command = [
        "python3",
        "scripts/run_production_infra_automation.py",
        "--run-id",
        run_id,
        "--target-environment",
        args.target_environment,
        "--output",
        str(output),
        "--minimum-tenants",
        str(args.minimum_tenants),
        "--mode",
        args.production_infra_mode,
    ]
    for tenant_artifact in args.tenant_artifact:
        command.extend(["--tenant-artifact", tenant_artifact])
    for provider_template in args.provider_template:
        command.extend(["--provider-template", provider_template])
    for template_file in args.template_file:
        command.extend(["--template-file", template_file])
    for metadata in args.metadata:
        command.extend(["--metadata", metadata])
    if args.execute_production_infra:
        command.append("--execute")
    if args.confirm_production_infra:
        command.extend(["--confirm", args.confirm_production_infra])
    if args.strict:
        command.append("--strict")
    return command


def _infra_readiness_command(
    args: argparse.Namespace,
    run_id: str,
    output: Path,
    production_infra_output: Path,
    deployment_decision: str,
    rollback_decision: str,
) -> list[str]:
    command = [
        "python3",
        "scripts/export_infra_provider_readiness.py",
        "--run-id",
        run_id,
        "--target-environment",
        args.target_environment,
        "--output",
        str(output),
        "--production-infra-evidence",
        str(production_infra_output),
    ]
    for provider in args.infra_provider:
        command.extend(["--provider", provider])
    if deployment_decision:
        command.extend(["--deployment-decision", deployment_decision])
    if rollback_decision:
        command.extend(["--rollback-decision", rollback_decision])
    if args.allow_assumptions:
        command.append("--allow-assumptions")
        for provider in args.assume_provider:
            command.extend(["--assume-provider", provider])
    if args.require_provider_credentials:
        command.append("--require-provider-credentials")
    if args.require_tools:
        command.append("--require-tools")
    if args.require_real_approvals:
        command.append("--require-real-approvals")
    if args.strict:
        command.append("--strict")
    return command


def _production_ops_command(
    args: argparse.Namespace,
    run_id: str,
    output: Path,
    production_infra_output: Path,
    infra_readiness_output: Path,
) -> list[str]:
    command = [
        "python3",
        "scripts/export_production_ops_readiness.py",
        "--run-id",
        run_id,
        "--target-environment",
        args.target_environment,
        "--output",
        str(output),
        "--production-infra-evidence",
        str(production_infra_output),
        "--infra-provider-readiness-evidence",
        str(infra_readiness_output / "infra-provider-readiness.json"),
    ]
    optional_pairs = [
        ("--operations-bundle", args.operations_bundle),
        ("--monitoring-evidence", args.monitoring_evidence),
        ("--incident-runbook-evidence", args.incident_runbook_evidence),
        ("--load-profile-matrix", args.load_profile_matrix),
        ("--release-retention-evidence", args.release_retention_evidence),
        ("--secret-manager-evidence", args.secret_manager_evidence),
        ("--secret-runtime-evidence", args.secret_runtime_evidence),
        ("--deployment-environment-evidence", args.deployment_environment_evidence),
        ("--tenant-ops-evidence", args.tenant_ops_evidence),
        ("--ops-tool-evidence", args.ops_tool_evidence),
        ("--ops-status", args.ops_status),
        ("--backup-artifact-ref", args.backup_artifact_ref),
        ("--restore-drill-ref", args.restore_drill_ref),
        ("--security-audit-ref", args.security_audit_ref),
        ("--dependency-scan-ref", args.dependency_scan_ref),
        ("--container-scan-ref", args.container_scan_ref),
    ]
    for flag, value in optional_pairs:
        if value:
            command.extend([flag, value])
    for load_evidence in args.load_evidence:
        command.extend(["--load-evidence", load_evidence])
    if args.allow_warning_exception:
        command.append("--allow-warning-exception")
        for flag, value in [
            ("--warning-exception-ref", args.warning_exception_ref),
            ("--warning-exception-approved-by", args.warning_exception_approved_by),
            ("--warning-exception-reason", args.warning_exception_reason),
            ("--warning-exception-expires-at", args.warning_exception_expires_at),
        ]:
            if value:
                command.extend([flag, value])
    if args.strict:
        command.append("--strict")
    if args.fail_on_warning:
        command.append("--fail-on-warning")
    return command


def _signoff_command(
    args: argparse.Namespace,
    run_id: str,
    output: Path,
    evidence_paths: list[str],
) -> list[str]:
    command = [
        "python3",
        "scripts/generate_signoff_pack.py",
        "--run-id",
        run_id,
        "--target-environment",
        args.target_environment,
        "--output",
        str(output),
    ]
    for path in evidence_paths:
        command.extend(["--evidence-path", path])
    for group in args.signoff_required_group:
        command.extend(["--required-evidence-group", group])
    if args.signoff_strict:
        command.append("--strict-required-evidence")
    return command


def _deployment_gate_command(args: argparse.Namespace, run_id: str, readiness_file: str, output: Path) -> list[str]:
    command = [
        "python3",
        "scripts/run_production_deployment_gate.py",
        readiness_file,
        "--run-id",
        run_id,
        "--target-environment",
        args.target_environment,
        "--output",
        str(output),
    ]
    for flag, value in [
        ("--backup-ref", args.backup_artifact_ref),
        ("--rollback-ref", args.deployment_rollback_ref),
        ("--monitoring-ref", args.monitoring_ref or args.monitoring_evidence),
        ("--tenant-smoke-ref", args.tenant_smoke_ref),
        ("--tenant-rollout-ref", args.tenant_rollout_ref),
        ("--approver", args.deployment_approver),
        ("--signoff-package", str(_resolve(readiness_file).parent)),
    ]:
        if value:
            command.extend([flag, value])
    if args.fail_on_warning:
        command.append("--fail-on-warning")
    return command


def _rollback_command(args: argparse.Namespace, run_id: str, deployment_gate: str, output: Path) -> list[str]:
    command = [
        "python3",
        "scripts/run_production_rollback.py",
        deployment_gate,
        "--run-id",
        run_id,
        "--output",
        str(output),
        "--provider",
        args.rollback_provider,
    ]
    for flag, value in [
        ("--rollback-ref", args.deployment_rollback_ref),
        ("--compose-file", args.rollback_compose_file),
        ("--compose-project", args.rollback_compose_project),
        ("--compose-image-env", args.rollback_compose_image_env),
        ("--service", args.rollback_service),
        ("--namespace", args.rollback_namespace),
        ("--deployment", args.rollback_deployment),
        ("--container", args.rollback_container),
        ("--manifest", args.rollback_manifest),
    ]:
        if value:
            command.extend([flag, value])
    if args.execute_rollback:
        command.append("--execute")
    return command


def _json_review(path: Path) -> dict:
    payload = _read_json(path)
    return {
        "path": _repo_relative(path),
        "exists": path.is_file(),
        "decision": payload.get("decision") or payload.get("status") or "",
        "ci_status": payload.get("ci_status") or "",
        "state": _decision_state(payload) if payload else "missing",
        "blocker_count": len(payload.get("blockers") or []) if payload else 0,
        "warning_count": len(payload.get("warnings") or []) if payload else 0,
    }


def _artifact_bundle(
    args: argparse.Namespace,
    output: Path,
    evidence_paths: list[str],
    steps: list[dict],
    generated_refs: dict[str, str],
) -> dict:
    self_manifests = {
        str((output / "protected-release-chain.json").resolve()),
        str((output / "ci-artifact-bundle.json").resolve()),
    }
    files = [
        path
        for path in _iter_files(evidence_paths + [str(output)])
        if str(path.resolve()) not in self_manifests
    ]
    file_entries = []
    for path in files:
        file_entries.append(
            {
                "path": _repo_relative(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    reviews = [
        _json_review(path)
        for path in files
        if path.name in INTERESTING_JSON_NAMES
    ]
    artifact = {
        "name": args.artifact_name,
        "retention_days": args.artifact_retention_days,
        "upload_paths": [_repo_relative(_resolve(path)) for path in evidence_paths + [str(output)]],
        "github_actions_upload_step": "actions/upload-artifact@v4",
    }
    warnings = []
    blockers = []
    for step in steps:
        if step["status"] == "failed" and step["required"]:
            blockers.append("%s exited %s." % (step["name"], step["exit_code"]))
    for review in reviews:
        if review["state"] == "failed":
            blockers.append("%s decision is %s/%s." % (review["path"], review["decision"], review["ci_status"]))
        elif review["state"] == "warning":
            warnings.append("%s decision is %s/%s." % (review["path"], review["decision"], review["ci_status"]))
    if args.fail_on_warning and warnings:
        blockers.extend("warning-policy: %s" % warning for warning in warnings)
        warnings = []
    decision = "failed" if blockers else "warning" if warnings else "passed"
    ci_status = "fail" if blockers else "pass_with_warnings" if warnings else "pass"
    return {
        "context": {
            "run_id": args.run_id,
            "target_environment": args.target_environment,
            "generated_at": _utc_now(),
            "output": _repo_relative(output),
            "strict": bool(args.strict),
            "allow_assumptions": bool(args.allow_assumptions),
            "fail_on_warning": bool(args.fail_on_warning),
        },
        "decision": decision,
        "ci_status": ci_status,
        "artifact": artifact,
        "generated_refs": generated_refs,
        "steps": steps,
        "json_reviews": reviews,
        "file_count": len(file_entries),
        "files": file_entries,
        "blockers": blockers,
        "warnings": warnings,
    }


def _status_tsv(steps: list[dict], bundle: dict) -> str:
    lines = ["step\tstatus\texit_code\trequired\tlog_file"]
    for step in steps:
        lines.append(
            "%s\t%s\t%s\t%s\t%s"
            % (step["name"], step["status"], step["exit_code"], int(step["required"]), step["log_file"])
        )
    lines.append("ci-artifact-bundle\t%s\t0\t1\t%s" % (bundle["decision"], "ci-artifact-bundle.json"))
    return "\n".join(lines)


def _summary(context: dict, steps: list[dict], bundle: dict, metadata_errors: list[str]) -> str:
    step_lines = "\n".join(
        "- %s: %s, exit=%s, required=%s, log=%s"
        % (
            step["name"],
            step["status"],
            step["exit_code"],
            "yes" if step["required"] else "no",
            step["log_file"],
        )
        for step in steps
    )
    review_lines = "\n".join(
        "- %s: %s/%s (%s)"
        % (review["path"], review["decision"] or "missing", review["ci_status"] or "missing", review["state"])
        for review in bundle["json_reviews"]
    ) or "- No JSON reviews found."
    blocker_lines = "\n".join("- %s" % item for item in bundle["blockers"]) or "- None"
    warning_lines = "\n".join("- %s" % item for item in bundle["warnings"]) or "- None"
    metadata_lines = "\n".join("- %s" % item for item in metadata_errors) or "- None"
    return f"""
# Protected Release Evidence Chain

- Decision: {bundle["decision"]}
- CI status: {bundle["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Strict: {context["strict"]}
- Allow assumptions: {context["allow_assumptions"]}
- Fail on warning: {context["fail_on_warning"]}
- Generated: {context["generated_at"]}
- Output: {context["output"]}
- Artifact name: {bundle["artifact"]["name"]}
- Artifact retention days: {bundle["artifact"]["retention_days"]}
- Evidence file count: {bundle["file_count"]}

## Steps

{step_lines}

## Evidence Reviews

{review_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Metadata Errors

{metadata_lines}

## Evidence Files

- Chain manifest: protected-release-chain.json
- CI artifact bundle manifest: ci-artifact-bundle.json
- Status table: status.tsv
- Environment summary: env-summary.txt
- Logs: logs/*.log
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tijara protected release evidence chain.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_CHAIN_RUN_ID") or os.environ.get("TIJARA_PROTECTED_RUN_ID") or _default_run_id())
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROTECTED_CHAIN_OUTPUT", ""))
    parser.add_argument("--strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_STRICT", "1")))
    parser.add_argument("--non-strict", action="store_true", default=False)
    parser.add_argument("--fail-on-warning", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_FAIL_ON_WARNING", "1")))
    parser.add_argument("--allow-assumptions", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_ALLOW_ASSUMPTIONS", "0")))
    parser.add_argument("--assume-provider", action="append", default=_csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_ASSUME_PROVIDERS")))
    parser.add_argument("--tenant-artifact", action="append", default=[])
    parser.add_argument("--provider-template", action="append", default=[])
    parser.add_argument("--template-file", action="append", default=[])
    parser.add_argument("--minimum-tenants", type=int, default=int(os.environ.get("TIJARA_PROTECTED_CHAIN_MINIMUM_TENANTS", os.environ.get("TIJARA_TENANT_OPS_MINIMUM_TENANTS", "1"))))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--production-infra-mode", choices=["plan", "apply"], default=os.environ.get("TIJARA_PROTECTED_CHAIN_INFRA_MODE", os.environ.get("TIJARA_PRODUCTION_INFRA_MODE", "plan")))
    parser.add_argument("--execute-production-infra", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_EXECUTE_INFRA")))
    parser.add_argument("--confirm-production-infra", default=os.environ.get("CONFIRM_PRODUCTION_INFRA", ""))
    parser.add_argument("--infra-provider", action="append", default=[])
    parser.add_argument("--require-provider-credentials", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_REQUIRE_PROVIDER_CREDENTIALS", "1")))
    parser.add_argument("--require-tools", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_REQUIRE_TOOLS", "1")))
    parser.add_argument("--require-real-approvals", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_REQUIRE_REAL_APPROVALS", "1")))
    parser.add_argument("--deployment-decision", default=os.environ.get("TIJARA_PROTECTED_CHAIN_DEPLOYMENT_DECISION", ""))
    parser.add_argument("--rollback-decision", default=os.environ.get("TIJARA_PROTECTED_CHAIN_ROLLBACK_DECISION", ""))
    parser.add_argument("--run-deployment-gate", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_RUN_DEPLOYMENT_GATE", "0")))
    parser.add_argument("--run-rollback-drill", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_RUN_ROLLBACK_DRILL", "0")))
    parser.add_argument("--deployment-approver", default=os.environ.get("TIJARA_DEPLOYMENT_APPROVER", os.environ.get("TIJARA_RELEASE_OWNER", "")))
    parser.add_argument("--deployment-rollback-ref", default=os.environ.get("TIJARA_DEPLOYMENT_ROLLBACK_REF", os.environ.get("TIJARA_ROLLBACK_REF", "")))
    parser.add_argument("--monitoring-ref", default=os.environ.get("TIJARA_DEPLOYMENT_MONITORING_REF", ""))
    parser.add_argument("--tenant-smoke-ref", default=os.environ.get("TIJARA_DEPLOYMENT_TENANT_SMOKE_REF", ""))
    parser.add_argument("--tenant-rollout-ref", default=os.environ.get("TIJARA_DEPLOYMENT_TENANT_ROLLOUT_REF", ""))
    parser.add_argument("--rollback-provider", default=os.environ.get("TIJARA_ROLLBACK_PROVIDER", "manifest"))
    parser.add_argument("--execute-rollback", action="store_true", default=_truthy(os.environ.get("TIJARA_ROLLBACK_EXECUTE")))
    parser.add_argument("--rollback-compose-file", default=os.environ.get("TIJARA_ROLLBACK_COMPOSE_FILE", ""))
    parser.add_argument("--rollback-compose-project", default=os.environ.get("TIJARA_ROLLBACK_COMPOSE_PROJECT", ""))
    parser.add_argument("--rollback-compose-image-env", default=os.environ.get("TIJARA_ROLLBACK_COMPOSE_IMAGE_ENV", ""))
    parser.add_argument("--rollback-service", default=os.environ.get("TIJARA_ROLLBACK_SERVICE", ""))
    parser.add_argument("--rollback-namespace", default=os.environ.get("TIJARA_ROLLBACK_NAMESPACE", ""))
    parser.add_argument("--rollback-deployment", default=os.environ.get("TIJARA_ROLLBACK_DEPLOYMENT", ""))
    parser.add_argument("--rollback-container", default=os.environ.get("TIJARA_ROLLBACK_CONTAINER", ""))
    parser.add_argument("--rollback-manifest", default=os.environ.get("TIJARA_ROLLBACK_MANIFEST", ""))
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
    parser.add_argument("--ops-tool-evidence", default=os.environ.get("TIJARA_PROD_OPS_TOOL_EVIDENCE", ""))
    parser.add_argument("--ops-status", default=os.environ.get("TIJARA_PROD_OPS_STATUS", ""))
    parser.add_argument("--backup-artifact-ref", default=os.environ.get("TIJARA_PROD_OPS_BACKUP_ARTIFACT_REF", os.environ.get("TIJARA_BACKUP_ARTIFACT_REF", "")))
    parser.add_argument("--restore-drill-ref", default=os.environ.get("TIJARA_PROD_OPS_RESTORE_DRILL_REF", ""))
    parser.add_argument("--security-audit-ref", default=os.environ.get("TIJARA_PROD_OPS_SECURITY_AUDIT_REF", ""))
    parser.add_argument("--dependency-scan-ref", default=os.environ.get("TIJARA_PROD_OPS_DEPENDENCY_SCAN_REF", ""))
    parser.add_argument("--container-scan-ref", default=os.environ.get("TIJARA_PROD_OPS_CONTAINER_SCAN_REF", ""))
    parser.add_argument("--allow-warning-exception", action="store_true", default=_truthy(os.environ.get("TIJARA_PROD_OPS_ALLOW_WARNING_EXCEPTION", "0")))
    parser.add_argument("--warning-exception-ref", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_REF", ""))
    parser.add_argument("--warning-exception-approved-by", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_APPROVED_BY", ""))
    parser.add_argument("--warning-exception-reason", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_REASON", ""))
    parser.add_argument("--warning-exception-expires-at", default=os.environ.get("TIJARA_PROD_OPS_WARNING_EXCEPTION_EXPIRES_AT", ""))
    parser.add_argument("--extra-evidence-path", action="append", default=[])
    parser.add_argument("--signoff-required-group", action="append", default=[])
    parser.add_argument("--signoff-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROTECTED_CHAIN_SIGNOFF_STRICT", "1")))
    parser.add_argument("--artifact-name", default=os.environ.get("TIJARA_PROTECTED_CHAIN_ARTIFACT_NAME", ""))
    parser.add_argument("--artifact-retention-days", default=os.environ.get("TIJARA_GITHUB_ARTIFACT_RETENTION_DAYS", "30"))
    args = parser.parse_args()
    if args.non_strict:
        args.strict = False
    args.tenant_artifact = _dedupe(args.tenant_artifact + _csv_items(os.environ.get("TIJARA_TENANT_OPS_ARTIFACTS")) + _csv_items(os.environ.get("TIJARA_PRODUCTION_INFRA_TENANT_ARTIFACTS")))
    args.provider_template = _dedupe(args.provider_template + _csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_PROVIDER_TEMPLATES")) + _csv_items(os.environ.get("TIJARA_PRODUCTION_INFRA_TEMPLATE"))) or DEFAULT_PROVIDER_TEMPLATES
    args.template_file = _dedupe(args.template_file + _csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_TEMPLATE_FILES")) + _csv_items(os.environ.get("TIJARA_PRODUCTION_INFRA_TEMPLATE_FILE")))
    args.infra_provider = _dedupe(args.infra_provider + _csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_INFRA_PROVIDERS")) + _csv_items(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_PROVIDERS"))) or DEFAULT_INFRA_PROVIDERS
    args.assume_provider = _dedupe(args.assume_provider) or (["all"] if args.allow_assumptions else [])
    args.metadata = _dedupe(args.metadata + _csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_METADATA")))
    args.extra_evidence_path = _dedupe(args.extra_evidence_path + _csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_EXTRA_EVIDENCE_PATHS")))
    args.signoff_required_group = _dedupe(args.signoff_required_group + _csv_items(os.environ.get("TIJARA_PROTECTED_CHAIN_SIGNOFF_REQUIRED_GROUPS")) + _csv_items(os.environ.get("TIJARA_PROTECTED_REQUIRED_EVIDENCE_GROUPS"))) or ["ops"]
    if not args.artifact_name:
        args.artifact_name = "tijara-protected-release-evidence-%s-%s" % (args.target_environment, args.run_id)
    if not args.operations_bundle:
        args.operations_bundle = _existing_or_empty(_default_path(args.run_id, "operations_bundle"))
    if not args.monitoring_evidence:
        args.monitoring_evidence = _existing_or_empty(_default_path(args.run_id, "monitoring"))
    if not args.incident_runbook_evidence:
        args.incident_runbook_evidence = _existing_or_empty(_default_path(args.run_id, "incident"))
    if not args.load_evidence:
        default_load = _existing_or_empty(_default_path(args.run_id, "load"))
        args.load_evidence = [default_load] if default_load else []
    if not args.load_profile_matrix:
        args.load_profile_matrix = _existing_or_empty(_default_path(args.run_id, "load_matrix"))
    if not args.release_retention_evidence:
        args.release_retention_evidence = _existing_or_empty(_default_path(args.run_id, "release_retention"))
    if not args.secret_manager_evidence:
        args.secret_manager_evidence = _existing_or_empty(_default_path(args.run_id, "secret_manager"))
    if not args.secret_runtime_evidence:
        args.secret_runtime_evidence = _existing_or_empty(_default_path(args.run_id, "secret_runtime"))
    if not args.deployment_environment_evidence:
        args.deployment_environment_evidence = _existing_or_empty(_default_path(args.run_id, "deployment_environment"))
    if not args.tenant_ops_evidence:
        args.tenant_ops_evidence = _existing_or_empty(_default_path(args.run_id, "tenant_ops"))
    if not args.ops_tool_evidence:
        args.ops_tool_evidence = _existing_or_empty(_default_path(args.run_id, "ops_tool"))
    if not args.ops_status:
        args.ops_status = _existing_or_empty(_default_path(args.run_id, "ops_status"))
    return args


def main() -> int:
    args = _parse_args()
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-release-chain" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    metadata, metadata_errors = _safe_metadata(args.metadata)
    steps: list[dict] = []
    generated_refs: dict[str, str] = {}
    production_infra_output = ROOT_DIR / "deploy/runtime/production-infra" / args.run_id
    infra_readiness_output = ROOT_DIR / "deploy/runtime/infra-provider-readiness" / args.run_id
    production_ops_output = ROOT_DIR / "deploy/runtime/production-ops-readiness" / args.run_id
    signoff_output = ROOT_DIR / "deploy/runtime/signoff-packages" / args.run_id
    deployment_gate_output = ROOT_DIR / "deploy/runtime/deployment-gates" / args.run_id
    rollback_output = ROOT_DIR / "deploy/runtime/rollback-runs" / args.run_id

    steps.append(_run_step("production-infra-plan", _production_infra_command(args, args.run_id, production_infra_output), output))
    generated_refs["production_infra"] = _repo_relative(production_infra_output / "production-infra-automation.json")

    deployment_decision = args.deployment_decision
    rollback_decision = args.rollback_decision
    steps.append(
        _run_step(
            "infra-provider-readiness",
            _infra_readiness_command(
                args,
                args.run_id,
                infra_readiness_output,
                production_infra_output,
                deployment_decision,
                rollback_decision,
            ),
            output,
        )
    )
    generated_refs["infra_provider_readiness"] = _repo_relative(infra_readiness_output / "infra-provider-readiness.json")

    steps.append(
        _run_step(
            "production-ops-readiness",
            _production_ops_command(args, args.run_id, production_ops_output, production_infra_output, infra_readiness_output),
            output,
        )
    )
    generated_refs["production_ops_readiness"] = _repo_relative(production_ops_output / "production-ops-readiness.json")

    evidence_paths = _dedupe(
        [
            str(production_infra_output),
            str(infra_readiness_output),
            str(production_ops_output),
            args.operations_bundle,
            args.monitoring_evidence,
            args.incident_runbook_evidence,
            args.load_profile_matrix,
            args.release_retention_evidence,
            args.secret_manager_evidence,
            args.secret_runtime_evidence,
            args.deployment_environment_evidence,
            args.tenant_ops_evidence,
            args.ops_tool_evidence,
        ]
        + args.load_evidence
        + _default_protected_evidence_paths(args.run_id)
        + args.extra_evidence_path
    )
    steps.append(_run_step("signoff-package", _signoff_command(args, args.run_id, signoff_output, evidence_paths), output))
    generated_refs["signoff_package"] = _repo_relative(signoff_output)
    generated_refs["release_readiness"] = _repo_relative(signoff_output / "release-readiness.json")

    if args.run_deployment_gate:
        readiness_file = str(signoff_output / "release-readiness.json")
        steps.append(
            _run_step(
                "production-deployment-gate",
                _deployment_gate_command(args, args.run_id, readiness_file, deployment_gate_output),
                output,
            )
        )
        deployment_decision = str(deployment_gate_output / "deployment-decision.json")
        generated_refs["deployment_decision"] = _repo_relative(deployment_decision)
    if args.run_rollback_drill:
        deployment_gate = deployment_decision or str(deployment_gate_output / "deployment-decision.json")
        steps.append(
            _run_step(
                "production-rollback-drill",
                _rollback_command(args, args.run_id, deployment_gate, rollback_output),
                output,
            )
        )
        rollback_decision = str(rollback_output / "rollback-decision.json")
        generated_refs["rollback_decision"] = _repo_relative(rollback_decision)

    if args.run_deployment_gate or args.run_rollback_drill or args.deployment_decision or args.rollback_decision:
        steps.append(
            _run_step(
                "infra-provider-readiness-final",
                _infra_readiness_command(
                    args,
                    args.run_id,
                    infra_readiness_output,
                    production_infra_output,
                    deployment_decision,
                    rollback_decision,
                ),
                output,
            )
        )
        steps.append(
            _run_step(
                "production-ops-readiness-final",
                _production_ops_command(args, args.run_id, production_ops_output, production_infra_output, infra_readiness_output),
                output,
            )
        )
        final_evidence_paths = _dedupe(evidence_paths + [str(deployment_gate_output), str(rollback_output)])
        steps.append(_run_step("signoff-package-final", _signoff_command(args, args.run_id, signoff_output, final_evidence_paths), output))
        evidence_paths = final_evidence_paths

    bundle = _artifact_bundle(args, output, evidence_paths + [str(signoff_output)], steps, generated_refs)
    if metadata_errors:
        bundle["blockers"].extend(metadata_errors)
        bundle["decision"] = "failed"
        bundle["ci_status"] = "fail"
    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": _repo_relative(output),
        "strict": bool(args.strict),
        "allow_assumptions": bool(args.allow_assumptions),
        "fail_on_warning": bool(args.fail_on_warning),
        "provider_templates": args.provider_template,
        "template_files": args.template_file,
        "infra_providers": args.infra_provider,
        "tenant_artifacts": args.tenant_artifact,
        "metadata_keys": sorted(metadata),
    }
    manifest = {
        "context": context,
        "decision": bundle["decision"],
        "ci_status": bundle["ci_status"],
        "steps": steps,
        "generated_refs": generated_refs,
        "artifact_bundle": {
            "path": _repo_relative(output / "ci-artifact-bundle.json"),
            "decision": bundle["decision"],
            "ci_status": bundle["ci_status"],
            "file_count": bundle["file_count"],
            "artifact": bundle["artifact"],
        },
        "metadata": metadata,
        "metadata_errors": metadata_errors,
        "blockers": bundle["blockers"],
        "warnings": bundle["warnings"],
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "strict=%s" % int(args.strict),
            "allow_assumptions=%s" % int(args.allow_assumptions),
            "fail_on_warning=%s" % int(args.fail_on_warning),
            "artifact_name=%s" % args.artifact_name,
            "artifact_retention_days=%s" % args.artifact_retention_days,
            "provider_templates=%s" % ",".join(args.provider_template),
            "infra_providers=%s" % ",".join(args.infra_provider),
            "tenant_artifacts=%s" % (",".join(args.tenant_artifact) or "<unset>"),
            "deployment_decision=%s" % (deployment_decision or "<unset>"),
            "rollback_decision=%s" % (rollback_decision or "<unset>"),
            "decision=%s" % bundle["decision"],
            "ci_status=%s" % bundle["ci_status"],
        ]
    )
    _write(output / "protected-release-chain.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "ci-artifact-bundle.json", json.dumps(bundle, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(steps, bundle))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, steps, bundle, metadata_errors))
    print("Protected release evidence chain written to %s" % output)
    print("decision=%s" % bundle["decision"])
    print("ci_status=%s" % bundle["ci_status"])
    return 1 if bundle["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
