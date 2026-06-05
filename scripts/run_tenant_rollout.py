#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
EXPECTED_ARTIFACTS = {
    "manifest": "ops-manifest.json",
    "nginx": "nginx-location.conf",
    "ingress": "k8s-ingress.yaml",
    "certificate": "cert-manager-certificate.yaml",
    "dns": "external-dns-record.json",
    "backup": "backup-policy.json",
    "monitoring": "prometheus-blackbox-target.json",
    "admin": "admin-bootstrap.md",
    "smoke": "smoke-checklist.md",
}
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _resolve_path(raw_path):
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _safe_relative(path):
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _hash_file(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


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


def _tenant_paths(args):
    values = list(args.tenant_artifact or [])
    values.extend(_csv_items(os.environ.get("TIJARA_TENANT_ROLLOUT_ARTIFACTS")))
    values.extend(_csv_items(os.environ.get("TIJARA_TENANT_OPS_ARTIFACTS")))
    deduped = []
    seen = set()
    for raw in values:
        if raw and raw not in seen:
            seen.add(raw)
            deduped.append(raw)
    return [_resolve_path(raw) for raw in deduped]


def _load_manifest(path):
    tenant_dir = path if path.is_dir() else path.parent
    manifest_path = path if path.is_file() else tenant_dir / "ops-manifest.json"
    return tenant_dir, manifest_path, _read_json(manifest_path)


def _artifact_paths(tenant_dir):
    return {name: tenant_dir / filename for name, filename in EXPECTED_ARTIFACTS.items()}


def _command_text(command):
    return " ".join(command)


def _action(
    name,
    tenant_db,
    provider,
    command,
    artifact,
    message,
    execute,
    rollback_command=None,
    rollback_message="",
):
    rollback_command = rollback_command or []
    return {
        "name": name,
        "tenant_db": tenant_db,
        "provider": provider,
        "command": command,
        "command_text": _command_text(command) if command else "",
        "rollback_command": rollback_command,
        "rollback_command_text": _command_text(rollback_command) if rollback_command else "",
        "rollback_message": rollback_message,
        "rollback_required": bool(rollback_command or rollback_message),
        "artifact": _safe_relative(artifact) if artifact else "",
        "artifact_sha256": _hash_file(artifact) if artifact and artifact.is_file() else "",
        "status": "pending" if execute else "dry-run",
        "exit_code": None,
        "message": message,
    }


def _copy_command(source, target_dir, tenant_db, suffix=".json"):
    target = Path(target_dir) / ("%s%s" % (tenant_db, suffix))
    return ["cp", str(source), str(target)]


def _tenant_actions(args, tenant_dir, manifest):
    artifacts = _artifact_paths(tenant_dir)
    tenant = manifest.get("tenant") or {}
    dns = manifest.get("dns") or {}
    monitoring = manifest.get("monitoring") or {}
    tenant_db = tenant.get("database") or tenant_dir.name
    provider = args.platform
    execute = bool(args.execute)
    actions = []

    if provider in {"manifest", "kubernetes"}:
        actions.append(
            _action(
                "kubernetes-apply-ingress",
                tenant_db,
                "kubernetes",
                [args.kubectl, "apply", "-f", str(artifacts["ingress"])],
                artifacts["ingress"],
                "Apply tenant Kubernetes ingress.",
                execute,
                rollback_command=[args.kubectl, "delete", "-f", str(artifacts["ingress"]), "--ignore-not-found=true"],
                rollback_message="Delete tenant Kubernetes ingress if cutover is aborted.",
            )
        )
        actions.append(
            _action(
                "kubernetes-apply-certificate",
                tenant_db,
                "cert-manager",
                [args.kubectl, "apply", "-f", str(artifacts["certificate"])],
                artifacts["certificate"],
                "Apply tenant cert-manager certificate.",
                execute,
                rollback_command=[args.kubectl, "delete", "-f", str(artifacts["certificate"]), "--ignore-not-found=true"],
                rollback_message="Delete tenant cert-manager certificate if TLS cutover is reverted.",
            )
        )
    if provider in {"manifest", "nginx"}:
        command = []
        rollback_command = []
        if args.nginx_available_dir:
            target = Path(args.nginx_available_dir) / ("%s.conf" % tenant_db)
            command = ["cp", str(artifacts["nginx"]), str(target)]
            rollback_command = ["rm", "-f", str(target)]
        actions.append(
            _action(
                "nginx-tenant-location",
                tenant_db,
                "nginx",
                command,
                artifacts["nginx"],
                "Install or review tenant Nginx database-isolation location snippet.",
                execute and bool(command),
                rollback_command=rollback_command,
                rollback_message="Remove tenant Nginx location snippet and reload Nginx after review.",
            )
        )
        enable_command = []
        enable_rollback_command = []
        if args.nginx_available_dir and args.nginx_enabled_dir:
            available = Path(args.nginx_available_dir) / ("%s.conf" % tenant_db)
            enabled = Path(args.nginx_enabled_dir) / ("%s.conf" % tenant_db)
            enable_command = ["ln", "-sf", str(available), str(enabled)]
            enable_rollback_command = ["rm", "-f", str(enabled)]
        actions.append(
            _action(
                "nginx-enable-location",
                tenant_db,
                "nginx",
                enable_command,
                artifacts["nginx"],
                "Enable tenant Nginx snippet after operator review.",
                execute and bool(enable_command),
                rollback_command=enable_rollback_command,
                rollback_message="Remove enabled tenant Nginx snippet symlink and reload Nginx after review.",
            )
        )
    if provider in {"manifest", "external-dns", "kubernetes"}:
        message = "Publish DNS record %s -> %s." % (
            dns.get("hostname") or tenant.get("domain") or "<unset>",
            dns.get("target") or "<unset>",
        )
        actions.append(
            _action(
                "dns-record",
                tenant_db,
                dns.get("provider") or "external-dns",
                [],
                artifacts["dns"],
                message,
                False,
                rollback_message="Remove or revert DNS record %s and wait for TTL propagation." % (
                    dns.get("hostname") or tenant.get("domain") or "<unset>"
                ),
            )
        )
    if provider in {"manifest", "monitoring"}:
        command = []
        rollback_command = []
        if args.prometheus_target_dir:
            command = _copy_command(artifacts["monitoring"], args.prometheus_target_dir, tenant_db)
            rollback_command = ["rm", "-f", str(Path(args.prometheus_target_dir) / ("%s.json" % tenant_db))]
        actions.append(
            _action(
                "prometheus-blackbox-target",
                tenant_db,
                "prometheus-blackbox",
                command,
                artifacts["monitoring"],
                "Install or review tenant Blackbox target %s." % (monitoring.get("blackbox_url") or "<unset>"),
                execute and bool(command),
                rollback_command=rollback_command,
                rollback_message="Remove tenant Prometheus Blackbox target and reload monitoring config.",
            )
        )
    if provider in {"manifest", "backup"}:
        actions.append(
            _action(
                "backup-policy-register",
                tenant_db,
                "postgres-backup",
                [],
                artifacts["backup"],
                "Register or review tenant backup policy.",
                False,
                rollback_message="Keep existing backup restore point; pause new tenant backup policy if cutover is cancelled.",
            )
        )
    return actions


def _validate_artifacts(tenant_dir, require_all):
    rows = []
    blockers = []
    warnings = []
    for name, path in _artifact_paths(tenant_dir).items():
        if path.is_file():
            rows.append({"name": "artifact:%s" % name, "status": "passed", "message": _safe_relative(path)})
            continue
        message = "Missing tenant rollout artifact: %s" % path
        rows.append({"name": "artifact:%s" % name, "status": "failed" if require_all else "warning", "message": message})
        if require_all:
            blockers.append(message)
        else:
            warnings.append(message)
    return rows, blockers, warnings


def _run_action(action, execute, confirm, output):
    if not action.get("command"):
        action["status"] = "dry-run"
        action["exit_code"] = 0
        return action
    if not execute:
        action["status"] = "dry-run"
        action["exit_code"] = 0
        return action
    if confirm != "YES":
        action["status"] = "failed"
        action["exit_code"] = 2
        action["message"] = "%s Confirmation CONFIRM_TENANT_ROLLOUT=YES is required." % action["message"]
        return action
    log_file = output / ("%s-%s.log" % (action["tenant_db"], action["name"]))
    with log_file.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            action["command"],
            cwd=str(ROOT_DIR),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    action["exit_code"] = result.returncode
    action["log_file"] = str(log_file)
    action["status"] = "executed" if result.returncode == 0 else "failed"
    return action


def _status_tsv(rows, actions):
    lines = ["check\tstatus\ttenant_db\tprovider\tmessage\tcommand"]
    for row in rows:
        lines.append("%s\t%s\t\t\t%s\t" % (row["name"], row["status"], row["message"]))
    for action in actions:
        lines.append(
            "%s\t%s\t%s\t%s\t%s\t%s"
            % (
                action["name"],
                action["status"],
                action["tenant_db"],
                action["provider"],
                action["message"],
                action.get("command_text") or "",
            )
        )
    return "\n".join(lines)


def _summary(context, tenant_reviews, decision, ci_status, blockers, warnings):
    status = "failed" if blockers else "warning" if warnings else "passed"
    tenant_lines = []
    for review in tenant_reviews:
        tenant_lines.append(
            "- %s: %s, actions dry-run/executed/failed=%s/%s/%s, rollback actions=%s"
            % (
                review.get("tenant_db") or "unknown",
                review.get("decision") or "unknown",
                review.get("dry_run_count", 0),
                review.get("executed_count", 0),
                review.get("failed_count", 0),
                review.get("rollback_action_count", 0),
            )
        )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Tenant Rollout Evidence

- Status: {status}
- Decision: {decision}
- CI status: {ci_status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Platform: {context["platform"]}
- Execute: {context["execute"]}
- Strict: {context["strict"]}
- Require all artifacts: {context["require_all_artifacts"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Tenant Reviews

{chr(10).join(tenant_lines) or "- No tenant rollout actions were generated."}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Tenant rollout evidence: tenant-rollout-evidence.json
- Rollback plan: rollback-plan.md
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _rollback_plan(context, tenant_reviews):
    lines = [
        "# Tenant Rollout Rollback Plan",
        "",
        "- Run ID: %s" % context["run_id"],
        "- Target environment: %s" % context["target_environment"],
        "- Platform: %s" % context["platform"],
        "- Generated: %s" % context["generated_at"],
        "",
        "## Rollback Actions",
        "",
    ]
    action_count = 0
    for review in tenant_reviews:
        lines.append("### `%s`" % (review.get("tenant_db") or "unknown"))
        for action in review.get("actions") or []:
            if not action.get("rollback_required"):
                continue
            action_count += 1
            lines.append("- `%s` (%s)" % (action.get("name") or "unknown", action.get("provider") or "unknown"))
            if action.get("rollback_command_text"):
                lines.append("  - Command: `%s`" % action["rollback_command_text"])
            if action.get("rollback_message"):
                lines.append("  - Review: %s" % action["rollback_message"])
        lines.append("")
    if action_count < 1:
        lines.append("- No rollback actions were generated.")
        lines.append("")
    lines.extend(
        [
            "## Operator Notes",
            "",
            "- Run rollback commands only after release-owner approval.",
            "- Capture command logs and updated monitoring status in the production rollback package.",
            "- Keep DNS, TLS, Nginx, and monitoring rollback evidence with the deployment gate package.",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run or dry-run tenant DNS/ingress rollout actions.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_TENANT_ROLLOUT_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TENANT_ROLLOUT_ENVIRONMENT", "production"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_TENANT_ROLLOUT_OUTPUT", ""))
    parser.add_argument("--tenant-artifact", action="append", default=[])
    platform_default = os.environ.get("TIJARA_TENANT_ROLLOUT_PLATFORM") or os.environ.get("TIJARA_TENANT_ROLLOUT_PROVIDER", "manifest")
    parser.add_argument("--platform", default=platform_default, choices=["manifest", "kubernetes", "nginx", "external-dns", "monitoring", "backup"])
    parser.add_argument("--provider", dest="platform", choices=["manifest", "kubernetes", "nginx", "external-dns", "monitoring", "backup"], help=argparse.SUPPRESS)
    parser.add_argument("--kubectl", default=os.environ.get("TIJARA_TENANT_ROLLOUT_KUBECTL", "kubectl"))
    parser.add_argument("--nginx-available-dir", default=os.environ.get("TIJARA_TENANT_ROLLOUT_NGINX_AVAILABLE_DIR", ""))
    parser.add_argument("--nginx-enabled-dir", default=os.environ.get("TIJARA_TENANT_ROLLOUT_NGINX_ENABLED_DIR", ""))
    parser.add_argument("--prometheus-target-dir", default=os.environ.get("TIJARA_TENANT_ROLLOUT_PROMETHEUS_TARGET_DIR", ""))
    parser.add_argument("--minimum-tenants", type=int, default=int(os.environ.get("TIJARA_TENANT_ROLLOUT_MINIMUM_TENANTS", "1")))
    parser.add_argument("--require-all-artifacts", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_ROLLOUT_REQUIRE_ALL_ARTIFACTS")))
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--execute", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_ROLLOUT_EXECUTE")))
    parser.add_argument("--confirm", default=os.environ.get("CONFIRM_TENANT_ROLLOUT", ""))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_TENANT_ROLLOUT_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true", help="Fail when tenant rollout evidence is incomplete.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/tenant-rollouts" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    flagged = _secret_like_keys(metadata)
    if flagged:
        print("Secret-like metadata keys are not allowed: %s" % ", ".join(flagged), file=sys.stderr)
        return 2

    blockers = []
    warnings = []
    status_rows = []
    all_actions = []
    tenant_reviews = []
    tenant_paths = _tenant_paths(args)
    if len(tenant_paths) < max(args.minimum_tenants, 0):
        message = "At least %s tenant artifact(s) are required; %s provided." % (
            max(args.minimum_tenants, 0),
            len(tenant_paths),
        )
        if strict:
            blockers.append(message)
            status_rows.append({"name": "minimum-tenants", "status": "failed", "message": message})
        else:
            warnings.append(message)
            status_rows.append({"name": "minimum-tenants", "status": "warning", "message": message})
    else:
        status_rows.append({"name": "minimum-tenants", "status": "passed", "message": "%s tenant artifact(s)." % len(tenant_paths)})

    for tenant_path in tenant_paths:
        tenant_dir, manifest_path, manifest = _load_manifest(tenant_path)
        tenant_db = ((manifest.get("tenant") or {}).get("database")) or tenant_dir.name
        require_all_artifacts = strict or bool(args.require_all_artifacts)
        artifact_rows, artifact_blockers, artifact_warnings = _validate_artifacts(tenant_dir, require_all_artifacts)
        status_rows.extend(
            {
                "name": "tenant:%s:%s" % (tenant_db, row["name"]),
                "status": row["status"],
                "message": row["message"],
            }
            for row in artifact_rows
        )
        blockers.extend(artifact_blockers)
        warnings.extend(artifact_warnings)
        if not manifest:
            message = "Tenant operations manifest is missing or unreadable: %s" % manifest_path
            blockers.append(message)
            tenant_reviews.append(
                {
                    "tenant_db": tenant_db,
                    "path": _safe_relative(tenant_dir),
                    "decision": "failed",
                    "ci_status": "fail",
                    "blockers": [message],
                    "warnings": [],
                    "actions": [],
                }
            )
            continue
        actions = [_run_action(action, args.execute, args.confirm, output) for action in _tenant_actions(args, tenant_dir, manifest)]
        all_actions.extend(actions)
        failed_actions = [action for action in actions if action["status"] == "failed"]
        dry_run_count = sum(1 for action in actions if action["status"] == "dry-run")
        executed_count = sum(1 for action in actions if action["status"] == "executed")
        rollback_action_count = sum(1 for action in actions if action.get("rollback_required"))
        tenant_blockers = ["%s failed." % action["name"] for action in failed_actions]
        blockers.extend("tenant:%s: %s" % (tenant_db, item) for item in tenant_blockers)
        tenant_decision = "failed" if tenant_blockers else "executed" if executed_count else "dry-run"
        tenant_reviews.append(
            {
                "tenant_db": tenant_db,
                "domain": (manifest.get("tenant") or {}).get("domain") or "",
                "path": _safe_relative(tenant_dir),
                "manifest_path": _safe_relative(manifest_path),
                "manifest_sha256": _hash_file(manifest_path),
                "decision": tenant_decision,
                "ci_status": "fail" if tenant_blockers else "pass",
                "dry_run_count": dry_run_count,
                "executed_count": executed_count,
                "failed_count": len(failed_actions),
                "rollback_action_count": rollback_action_count,
                "actions": actions,
                "blockers": tenant_blockers,
                "warnings": [],
            }
        )

    if blockers:
        decision = "failed"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    elif args.execute:
        decision = "executed"
        ci_status = "pass"
    else:
        decision = "dry-run"
        ci_status = "pass"

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "platform": args.platform,
        "provider": args.platform,
        "execute": bool(args.execute),
        "strict": bool(strict),
        "require_all_artifacts": bool(strict or args.require_all_artifacts),
        "minimum_tenants": max(args.minimum_tenants, 0),
        "tenant_count": len(tenant_reviews),
        "rollback_action_count": sum(1 for action in all_actions if action.get("rollback_required")),
        "generated_at": _utc_now(),
        "output": str(output),
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "metadata": metadata,
        "tenants": tenant_reviews,
        "actions": all_actions,
        "rollback_action_count": sum(1 for action in all_actions if action.get("rollback_required")),
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "platform=%s" % args.platform,
            "execute=%s" % int(args.execute),
            "strict=%s" % int(strict),
            "require_all_artifacts=%s" % int(strict or args.require_all_artifacts),
            "minimum_tenants=%s" % max(args.minimum_tenants, 0),
            "tenant_count=%s" % len(tenant_reviews),
            "rollback_action_count=%s" % sum(1 for action in all_actions if action.get("rollback_required")),
            "nginx_available_dir=%s" % (args.nginx_available_dir or "<unset>"),
            "nginx_enabled_dir=%s" % (args.nginx_enabled_dir or "<unset>"),
            "prometheus_target_dir=%s" % (args.prometheus_target_dir or "<unset>"),
        ]
    )

    _write(output / "tenant-rollout-evidence.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "rollback-plan.md", _rollback_plan(context, tenant_reviews))
    _write(output / "status.tsv", _status_tsv(status_rows, all_actions))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, tenant_reviews, decision, ci_status, blockers, warnings))

    print("Tenant rollout evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
