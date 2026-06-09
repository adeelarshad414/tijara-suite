#!/usr/bin/env python3
"""Generate production DNS, TLS, backup, and restore-drill automation wrappers."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
SCRIPT_NAMES = {
    "dns-apply": "dns-apply",
    "dns-rollback": "dns-rollback",
    "tls-apply": "tls-apply",
    "tls-rollback": "tls-rollback",
    "backup-run": "backup-run",
    "restore-drill": "restore-drill",
}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("infra-%Y%m%dT%H%M%SZ")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _resolve(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _csv_items(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _metadata_items(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError("Metadata must use key=value format: %s" % raw)
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Metadata key cannot be blank.")
        parsed[key] = value.strip()
    return parsed


def _secret_like_keys(values: dict[str, str]) -> list[str]:
    flagged = []
    for key in values:
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _tenant_artifact_paths(args: argparse.Namespace) -> list[Path]:
    raw = list(args.tenant_artifact or [])
    raw.extend(_csv_items(os.environ.get("TIJARA_PRODUCTION_INFRA_TENANT_ARTIFACTS")))
    raw.extend(_csv_items(os.environ.get("TIJARA_TENANT_OPS_ARTIFACTS")))
    seen: set[str] = set()
    paths: list[Path] = []
    for item in raw:
        if not item or item in seen:
            continue
        seen.add(item)
        paths.append(_resolve(item))
    return paths


def _load_tenant_manifest(path: Path) -> tuple[Path, Path, dict]:
    tenant_dir = path if path.is_dir() else path.parent
    manifest_path = path if path.is_file() else tenant_dir / "ops-manifest.json"
    return tenant_dir, manifest_path, _load_json(manifest_path)


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-") or "tenant"


def _shell_quote(value: str) -> str:
    return shlex.quote(str(value or ""))


def _ps_quote(value: str) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def _format_template(template: str, values: dict[str, str]) -> str:
    if not template:
        return ""
    try:
        return template.format(**values)
    except KeyError as error:
        raise ValueError("Command template references unknown placeholder: %s" % error) from error


def _values(manifest: dict) -> dict[str, str]:
    tenant = manifest.get("tenant") or {}
    dns = manifest.get("dns") or {}
    ingress = manifest.get("ingress") or {}
    backup = manifest.get("backup") or {}
    return {
        "tenant_name": str(tenant.get("name") or ""),
        "tenant_db": str(tenant.get("database") or backup.get("database") or ""),
        "domain": str(tenant.get("domain") or dns.get("hostname") or ingress.get("host") or ""),
        "dns_provider": str(dns.get("provider") or "manual"),
        "dns_target": str(dns.get("target") or ""),
        "record_type": str(dns.get("record_type") or "CNAME"),
        "ttl": str(dns.get("ttl") or 300),
        "namespace": str(ingress.get("namespace") or "tijara"),
        "tls_issuer": str(ingress.get("tls_issuer") or "letsencrypt-prod"),
        "tls_secret": str(ingress.get("tls_secret") or ""),
        "backup_policy": str(backup.get("policy") or "daily"),
        "backup_retention_days": str(backup.get("retention_days") or ""),
        "restore_drill_ref": str(backup.get("restore_drill_ref") or ""),
        "backup_database": str(backup.get("database") or tenant.get("database") or ""),
    }


def _default_shell_commands(values: dict[str, str]) -> dict[str, str]:
    return {
        "dns-apply": "printf '%%s\\n' %s" % (
            _shell_quote(
                "Create or update %s %s -> %s using %s"
                % (values["record_type"], values["domain"], values["dns_target"], values["dns_provider"])
            )
        ),
        "dns-rollback": "printf '%%s\\n' %s" % (
            _shell_quote("Rollback DNS %s to the previous approved value" % values["domain"])
        ),
        "tls-apply": "printf '%%s\\n' %s" % (
            _shell_quote(
                "Apply TLS certificate for %s with issuer %s and secret %s"
                % (values["domain"], values["tls_issuer"], values["tls_secret"])
            )
        ),
        "tls-rollback": "printf '%%s\\n' %s" % (
            _shell_quote("Rollback TLS certificate resources for %s after release-owner approval" % values["domain"])
        ),
        "backup-run": "bash deploy/postgres/backup.sh %s" % _shell_quote(values["backup_database"]),
        "restore-drill": "printf '%%s\\n' %s" % (
            _shell_quote(
                "Run restore drill for %s using the latest backup artifact; reference=%s"
                % (values["backup_database"], values["restore_drill_ref"] or "operator-selected-backup")
            )
        ),
    }


def _default_ps_commands(values: dict[str, str]) -> dict[str, str]:
    return {
        "dns-apply": "Write-Host %s" % _ps_quote(
            "Create or update %s %s -> %s using %s"
            % (values["record_type"], values["domain"], values["dns_target"], values["dns_provider"])
        ),
        "dns-rollback": "Write-Host %s" % _ps_quote("Rollback DNS %s to the previous approved value" % values["domain"]),
        "tls-apply": "Write-Host %s" % _ps_quote(
            "Apply TLS certificate for %s with issuer %s and secret %s"
            % (values["domain"], values["tls_issuer"], values["tls_secret"])
        ),
        "tls-rollback": "Write-Host %s" % _ps_quote("Rollback TLS certificate resources for %s after release-owner approval" % values["domain"]),
        "backup-run": "Write-Host %s" % _ps_quote("Run backup script for %s from a Bash-capable host." % values["backup_database"]),
        "restore-drill": "Write-Host %s" % _ps_quote(
            "Run restore drill for %s using latest backup; reference=%s"
            % (values["backup_database"], values["restore_drill_ref"] or "operator-selected-backup")
        ),
    }


def _operator_templates(args: argparse.Namespace, values: dict[str, str]) -> dict[str, str]:
    templates = {
        "dns-apply": args.dns_apply_command_template,
        "dns-rollback": args.dns_rollback_command_template,
        "tls-apply": args.tls_apply_command_template,
        "tls-rollback": args.tls_rollback_command_template,
        "backup-run": args.backup_command_template,
        "restore-drill": args.restore_drill_command_template,
    }
    rendered: dict[str, str] = {}
    for name, template in templates.items():
        rendered[name] = _format_template(template, values) if template else ""
    return rendered


def _script_header_shell(context: dict[str, str], action: str) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "# Generated by scripts/run_production_infra_automation.py",
            "# Run ID: %s" % context["run_id"],
            "# Tenant DB: %s" % context["tenant_db"],
            "# Action: %s" % action,
            "",
        ]
    )


def _script_header_ps(context: dict[str, str], action: str) -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = \"Stop\"",
            "# Generated by scripts/run_production_infra_automation.py",
            "# Run ID: %s" % context["run_id"],
            "# Tenant DB: %s" % context["tenant_db"],
            "# Action: %s" % action,
            "",
        ]
    )


def _write_scripts(
    tenant_output: Path,
    run_id: str,
    values: dict[str, str],
    shell_commands: dict[str, str],
    ps_commands: dict[str, str],
) -> list[dict]:
    scripts: list[dict] = []
    tenant_output.mkdir(parents=True, exist_ok=True)
    context = {"run_id": run_id, "tenant_db": values["tenant_db"]}
    for action, basename in SCRIPT_NAMES.items():
        shell_path = tenant_output / ("%s.sh" % basename)
        ps_path = tenant_output / ("%s.ps1" % basename)
        shell_command = shell_commands[action]
        ps_command = ps_commands[action]
        _write(shell_path, _script_header_shell(context, action) + shell_command)
        _write(ps_path, _script_header_ps(context, action) + ps_command)
        shell_path.chmod(0o755)
        scripts.append(
            {
                "action": action,
                "shell_script": _repo_relative(shell_path),
                "powershell_script": _repo_relative(ps_path),
                "shell_command": shell_command,
                "powershell_command": ps_command,
                "tenant_db": values["tenant_db"],
            }
        )
    return scripts


def _run_script(script_path: Path, action: str, output: Path) -> dict:
    log_path = output / ("%s.log" % action)
    with log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=str(ROOT_DIR),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return {"action": action, "exit_code": result.returncode, "log_file": _repo_relative(log_path)}


def _status_tsv(rows: list[dict]) -> str:
    lines = ["check\tstatus\ttenant_db\tmessage\tsource"]
    lines.extend(
        "%s\t%s\t%s\t%s\t%s"
        % (row["name"], row["status"], row.get("tenant_db", ""), row["message"], row.get("source", ""))
        for row in rows
    )
    return "\n".join(lines)


def _summary(context: dict, rows: list[dict], tenant_plans: list[dict], blockers: list[str], warnings: list[str]) -> str:
    tenant_lines = "\n".join(
        "- %s: %s script pair(s), execute_status=%s"
        % (plan["tenant_db"], len(plan.get("scripts") or []), plan.get("execute_status", "plan"))
        for plan in tenant_plans
    )
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Production Infrastructure Automation

- Decision: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Mode: {context["mode"]}
- Execute: {context["execute"]}
- Generated: {context["generated_at"]}
- Output: {context["output"]}

## Tenant Plans

{tenant_lines or "- No tenant plans generated."}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Root manifest: production-infra-automation.json
- Status table: status.tsv
- Tenant scripts: tenants/<tenant-db>/*.sh and tenants/<tenant-db>/*.ps1
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate production DNS/TLS/backup automation wrappers from tenant ops artifacts.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PRODUCTION_INFRA_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_PRODUCTION_INFRA_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PRODUCTION_INFRA_OUTPUT", ""))
    parser.add_argument("--tenant-artifact", action="append", default=[])
    parser.add_argument("--minimum-tenants", type=int, default=int(os.environ.get("TIJARA_PRODUCTION_INFRA_MINIMUM_TENANTS", "1")))
    parser.add_argument("--mode", choices=["plan", "apply"], default=os.environ.get("TIJARA_PRODUCTION_INFRA_MODE", "plan"))
    parser.add_argument("--execute", action="store_true", default=_truthy(os.environ.get("TIJARA_PRODUCTION_INFRA_EXECUTE")))
    parser.add_argument("--confirm", default=os.environ.get("CONFIRM_PRODUCTION_INFRA", ""))
    parser.add_argument("--dns-apply-command-template", default=os.environ.get("TIJARA_DNS_APPLY_COMMAND_TEMPLATE", ""))
    parser.add_argument("--dns-rollback-command-template", default=os.environ.get("TIJARA_DNS_ROLLBACK_COMMAND_TEMPLATE", ""))
    parser.add_argument("--tls-apply-command-template", default=os.environ.get("TIJARA_TLS_APPLY_COMMAND_TEMPLATE", ""))
    parser.add_argument("--tls-rollback-command-template", default=os.environ.get("TIJARA_TLS_ROLLBACK_COMMAND_TEMPLATE", ""))
    parser.add_argument("--backup-command-template", default=os.environ.get("TIJARA_BACKUP_COMMAND_TEMPLATE", ""))
    parser.add_argument("--restore-drill-command-template", default=os.environ.get("TIJARA_RESTORE_DRILL_COMMAND_TEMPLATE", ""))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PRODUCTION_INFRA_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/production-infra" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []
    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append({"name": "metadata-format", "status": "failed", "tenant_db": "", "message": str(error), "source": ""})
    else:
        rows.append({"name": "metadata-format", "status": "passed", "tenant_db": "", "message": "%s metadata item(s) parsed." % len(metadata), "source": ""})
    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append({"name": "metadata-secret-safety", "status": "failed", "tenant_db": "", "message": message, "source": ""})
    else:
        rows.append({"name": "metadata-secret-safety", "status": "passed", "tenant_db": "", "message": "No secret-like metadata keys found.", "source": ""})

    tenant_paths = _tenant_artifact_paths(args)
    if len(tenant_paths) < max(args.minimum_tenants, 0):
        message = "At least %s tenant artifact(s) are required; %s provided." % (max(args.minimum_tenants, 0), len(tenant_paths))
        if strict:
            blockers.append(message)
            rows.append({"name": "minimum-tenants", "status": "failed", "tenant_db": "", "message": message, "source": ""})
        else:
            warnings.append(message)
            rows.append({"name": "minimum-tenants", "status": "warning", "tenant_db": "", "message": message, "source": ""})
    else:
        rows.append({"name": "minimum-tenants", "status": "passed", "tenant_db": "", "message": "%s tenant artifact(s) attached." % len(tenant_paths), "source": ""})

    tenant_plans: list[dict] = []
    for tenant_path in tenant_paths:
        tenant_dir, manifest_path, manifest = _load_tenant_manifest(tenant_path)
        values = _values(manifest)
        tenant_db = values["tenant_db"] or _safe_slug(tenant_dir.name)
        values["tenant_db"] = tenant_db
        tenant_output = output / "tenants" / _safe_slug(tenant_db)
        if not manifest:
            message = "Tenant ops manifest missing or invalid: %s" % manifest_path
            if strict:
                blockers.append(message)
                status = "failed"
            else:
                warnings.append(message)
                status = "warning"
            rows.append({"name": "tenant-manifest", "status": status, "tenant_db": tenant_db, "message": message, "source": _repo_relative(manifest_path)})
            continue
        rows.append({"name": "tenant-manifest", "status": "passed", "tenant_db": tenant_db, "message": "Tenant ops manifest loaded.", "source": _repo_relative(manifest_path)})
        if not values["domain"] or not values["backup_database"]:
            message = "Tenant domain and backup database are required for production infra automation."
            if strict:
                blockers.append("%s: %s" % (tenant_db, message))
                status = "failed"
            else:
                warnings.append("%s: %s" % (tenant_db, message))
                status = "warning"
            rows.append({"name": "tenant-required-values", "status": status, "tenant_db": tenant_db, "message": message, "source": _repo_relative(manifest_path)})
        else:
            rows.append({"name": "tenant-required-values", "status": "passed", "tenant_db": tenant_db, "message": "Domain and backup database present.", "source": _repo_relative(manifest_path)})

        try:
            operator_templates = _operator_templates(args, values)
        except ValueError as error:
            blockers.append(str(error))
            rows.append({"name": "command-template", "status": "failed", "tenant_db": tenant_db, "message": str(error), "source": _repo_relative(manifest_path)})
            continue
        shell_commands = _default_shell_commands(values)
        ps_commands = _default_ps_commands(values)
        for action, command in operator_templates.items():
            if command:
                shell_commands[action] = command
                ps_commands[action] = "Write-Host %s" % _ps_quote("Run configured shell template from a Bash-capable host: %s" % command)

        scripts = _write_scripts(tenant_output, args.run_id, values, shell_commands, ps_commands)
        rows.append({"name": "automation-scripts", "status": "passed", "tenant_db": tenant_db, "message": "%s shell/PowerShell script pair(s) generated." % len(scripts), "source": _repo_relative(tenant_output)})
        execution_results: list[dict] = []
        execute_status = "plan"
        if args.execute or args.mode == "apply":
            if not args.execute:
                execute_status = "planned-apply"
                warnings.append("%s: apply mode requested without --execute; scripts were generated but not run." % tenant_db)
            elif args.confirm != "YES":
                execute_status = "blocked"
                message = "CONFIRM_PRODUCTION_INFRA=YES or --confirm YES is required before executing production infra scripts."
                blockers.append("%s: %s" % (tenant_db, message))
                rows.append({"name": "execution-confirmation", "status": "failed", "tenant_db": tenant_db, "message": message, "source": _repo_relative(tenant_output)})
            else:
                execute_status = "executed"
                for action in ("dns-apply", "tls-apply", "backup-run", "restore-drill"):
                    script_path = tenant_output / ("%s.sh" % SCRIPT_NAMES[action])
                    result = _run_script(script_path, action, tenant_output)
                    execution_results.append(result)
                    status = "passed" if result["exit_code"] == 0 else "failed"
                    if result["exit_code"] != 0:
                        blockers.append("%s: %s exited %s" % (tenant_db, action, result["exit_code"]))
                    rows.append({"name": "execute-%s" % action, "status": status, "tenant_db": tenant_db, "message": "Exit code %s." % result["exit_code"], "source": result["log_file"]})

        plan = {
            "tenant_db": tenant_db,
            "tenant_domain": values["domain"],
            "manifest": _repo_relative(manifest_path),
            "output": _repo_relative(tenant_output),
            "values": {key: values[key] for key in sorted(values)},
            "scripts": scripts,
            "execution": execution_results,
            "execute_status": execute_status,
        }
        _write(tenant_output / "tenant-infra-plan.json", json.dumps(plan, indent=2, sort_keys=True))
        tenant_plans.append(plan)

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
        "mode": args.mode,
        "execute": bool(args.execute),
        "generated_at": _utc_now(),
        "output": _repo_relative(output),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "metadata": metadata,
        "tenant_artifacts": [_repo_relative(path) for path in tenant_paths],
        "tenant_plans": tenant_plans,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    _write(output / "production-infra-automation.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "summary.md", _summary(context, rows, tenant_plans, blockers, warnings))
    print("Production infrastructure automation evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
