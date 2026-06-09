#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "client_secret",
    "integrity_salt",
    "encryption_key",
}
DEFAULT_NON_SECRET_FILES = [".env.example"]
DEFAULT_SECRET_EXAMPLE_FILES = ["secrets/.env.secrets.example"]
DEFAULT_CONFIG_FILES = [
    "docker-compose.yml",
    "deploy/config/odoo.conf.template",
    "deploy/bin/start-odoo.sh",
]
DEFAULT_REQUIRED_SECRETS = [
    "POSTGRES_PASSWORD",
    "ODOO_DB_PASSWORD",
    "ODOO_MASTER_PASSWORD",
    "BACKUP_ENCRYPTION_KEY",
    "ODOO_SESSION_SECRET",
    "GRAFANA_ADMIN_PASSWORD",
    "TIJARA_PAYMENT_WEBHOOK_SECRET",
    "TIJARA_BRIDGE_SHARED_SECRET",
]
COMPOSE_GUARDED_SECRETS = [
    "POSTGRES_PASSWORD",
    "ODOO_DB_PASSWORD",
    "ODOO_MASTER_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
]
PLACEHOLDER_PREFIXES = (
    "replace-",
    "change-me",
    "example-",
    "dummy-",
    "test-",
)


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


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


def _is_secret_key(key):
    normalized = str(key or "").lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _is_placeholder(value):
    text = str(value or "").strip()
    lowered = text.lower()
    if not text:
        return False
    if lowered.startswith(PLACEHOLDER_PREFIXES):
        return True
    return "${" in text or "vault:" in lowered or "secret:" in lowered


def _env_items(path):
    items = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        items[key.strip()] = value.strip()
    return items


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _add_required(rows, blockers, warnings, strict, name, value, label):
    if _present(value):
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is required for production secret-manager readiness." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _git_tracked_files(pathspec):
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", pathspec],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Secret Manager Evidence

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

- Secret manager manifest: secret-manager-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _scan_non_secret_files(paths):
    files = []
    violations = []
    for raw_path in paths:
        path = _resolve(raw_path)
        if not path.is_file():
            violations.append("%s is missing." % raw_path)
            files.append({"path": str(raw_path), "exists": False, "secret_key_count": 0})
            continue
        items = _env_items(path)
        secret_keys = sorted(key for key in items if _is_secret_key(key))
        if secret_keys:
            violations.append(
                "%s defines secret-like key(s): %s" % (_repo_relative(path), ", ".join(secret_keys))
            )
        files.append(
            {
                "path": _repo_relative(path),
                "exists": True,
                "key_count": len(items),
                "secret_keys": secret_keys,
            }
        )
    return files, violations


def _scan_secret_examples(paths, required_secrets):
    files = []
    missing_required = []
    unsafe_placeholders = []
    combined_items = {}
    for raw_path in paths:
        path = _resolve(raw_path)
        if not path.is_file():
            files.append({"path": str(raw_path), "exists": False, "secret_key_count": 0})
            continue
        items = _env_items(path)
        combined_items.update(items)
        secret_keys = sorted(key for key in items if _is_secret_key(key))
        unsafe = sorted(
            key
            for key in secret_keys
            if not _is_placeholder(items.get(key))
        )
        for key in unsafe:
            unsafe_placeholders.append("%s has non-placeholder value for %s" % (_repo_relative(path), key))
        files.append(
            {
                "path": _repo_relative(path),
                "exists": True,
                "key_count": len(items),
                "secret_keys": secret_keys,
                "unsafe_placeholder_keys": unsafe,
            }
        )
    for key in required_secrets:
        if key not in combined_items:
            missing_required.append(key)
    return files, missing_required, unsafe_placeholders


def _scan_config_files(paths):
    files = []
    issues = []
    for raw_path in paths:
        path = _resolve(raw_path)
        if not path.is_file():
            files.append({"path": str(raw_path), "exists": False})
            issues.append("%s is missing." % raw_path)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        files.append(
            {
                "path": _repo_relative(path),
                "exists": True,
                "secret_reference_count": sum(1 for part in SECRET_KEY_PARTS if part.upper() in text.upper()),
            }
        )
    return files, issues


def _compose_guardrails(compose_path):
    path = _resolve(compose_path)
    if not path.is_file():
        return [], ["Compose file is missing: %s" % compose_path]
    text = path.read_text(encoding="utf-8", errors="replace")
    checks = []
    issues = []
    for key in COMPOSE_GUARDED_SECRETS:
        guarded = "${%s:?" % key in text
        checks.append({"secret": key, "guarded": guarded})
        if not guarded:
            issues.append("Compose does not require %s with :? guard." % key)
    return checks, issues


def _startup_guardrails(start_script):
    path = _resolve(start_script)
    if not path.is_file():
        return {"exists": False}, ["Startup script is missing: %s" % start_script]
    text = path.read_text(encoding="utf-8", errors="replace")
    checks = {
        "exists": True,
        "requires_odoo_db_password": "ODOO_DB_PASSWORD is required" in text,
        "requires_odoo_master_password": "ODOO_MASTER_PASSWORD is required" in text,
        "refuses_production_placeholders": "Refusing to start production" in text,
    }
    issues = []
    if not checks["requires_odoo_db_password"]:
        issues.append("Startup script does not require ODOO_DB_PASSWORD.")
    if not checks["requires_odoo_master_password"]:
        issues.append("Startup script does not require ODOO_MASTER_PASSWORD.")
    if not checks["refuses_production_placeholders"]:
        issues.append("Startup script does not refuse placeholder production secrets.")
    return checks, issues


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Export Tijara runtime secret-manager and configuration evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_SECRET_MANAGER_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_SECRET_MANAGER_ENVIRONMENT", "production"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_SECRET_MANAGER_OUTPUT", ""))
    parser.add_argument(
        "--secret-manager-provider",
        default=os.environ.get("TIJARA_SECRET_MANAGER_PROVIDER", ""),
    )
    parser.add_argument(
        "--secret-manager-reference",
        default=os.environ.get("TIJARA_SECRET_MANAGER_REFERENCE", ""),
    )
    parser.add_argument(
        "--secret-rotation-policy-ref",
        default=os.environ.get("TIJARA_SECRET_ROTATION_POLICY_REF", ""),
    )
    parser.add_argument(
        "--secret-access-review-ref",
        default=os.environ.get("TIJARA_SECRET_ACCESS_REVIEW_REF", ""),
    )
    parser.add_argument("--non-secret-file", action="append", default=[])
    parser.add_argument("--secret-example-file", action="append", default=[])
    parser.add_argument("--config-file", action="append", default=[])
    parser.add_argument("--required-secret", action="append", default=[])
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_SECRET_MANAGER_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when secret-manager evidence is missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    non_secret_files = args.non_secret_file or DEFAULT_NON_SECRET_FILES
    secret_example_files = args.secret_example_file or DEFAULT_SECRET_EXAMPLE_FILES
    config_files = args.config_file or DEFAULT_CONFIG_FILES
    required_secrets = list(dict.fromkeys(DEFAULT_REQUIRED_SECRETS + args.required_secret))
    required_secrets.extend(_csv_items(os.environ.get("TIJARA_SECRET_MANAGER_REQUIRED_SECRETS")))
    required_secrets = list(dict.fromkeys(required_secrets))

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/secret-manager-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-manager-provider",
        args.secret_manager_provider,
        "Secret manager provider",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-manager-reference",
        args.secret_manager_reference,
        "Secret manager reference",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-rotation-policy",
        args.secret_rotation_policy_ref,
        "Secret rotation policy",
    )
    _add_required(
        rows,
        blockers,
        warnings,
        strict,
        "secret-access-review",
        args.secret_access_review_ref,
        "Secret access review",
    )

    non_secret, non_secret_violations = _scan_non_secret_files(non_secret_files)
    if non_secret_violations:
        blockers.extend(non_secret_violations)
        rows.append(_row("non-secret-template-safety", "failed", "; ".join(non_secret_violations)))
    else:
        rows.append(
            _row(
                "non-secret-template-safety",
                "passed",
                "%s non-secret template(s) contain no secret-like assignments." % len(non_secret),
            )
        )

    secret_examples, missing_required, unsafe_placeholders = _scan_secret_examples(
        secret_example_files,
        required_secrets,
    )
    if missing_required:
        blockers.append("Required secret placeholder(s) missing: %s" % ", ".join(missing_required))
        rows.append(_row("required-secret-placeholders", "failed", ", ".join(missing_required)))
    else:
        rows.append(
            _row(
                "required-secret-placeholders",
                "passed",
                "%s required secret placeholder(s) are present." % len(required_secrets),
            )
        )
    if unsafe_placeholders:
        blockers.extend(unsafe_placeholders)
        rows.append(_row("secret-example-placeholder-safety", "failed", "; ".join(unsafe_placeholders)))
    else:
        rows.append(
            _row(
                "secret-example-placeholder-safety",
                "passed",
                "%s secret example file(s) use placeholder/reference values." % len(secret_examples),
            )
        )

    config_files_manifest, config_issues = _scan_config_files(config_files)
    if config_issues:
        blockers.extend(config_issues)
        rows.append(_row("config-file-presence", "failed", "; ".join(config_issues)))
    else:
        rows.append(
            _row("config-file-presence", "passed", "%s runtime config file(s) are present." % len(config_files_manifest))
        )

    compose_guardrails, compose_issues = _compose_guardrails("docker-compose.yml")
    if compose_issues:
        blockers.extend(compose_issues)
        rows.append(_row("compose-secret-guardrails", "failed", "; ".join(compose_issues)))
    else:
        rows.append(
            _row(
                "compose-secret-guardrails",
                "passed",
                "%s critical Compose secret(s) use required :? guards." % len(compose_guardrails),
            )
        )

    startup_guardrails, startup_issues = _startup_guardrails("deploy/bin/start-odoo.sh")
    if startup_issues:
        blockers.extend(startup_issues)
        rows.append(_row("startup-secret-guardrails", "failed", "; ".join(startup_issues)))
    else:
        rows.append(_row("startup-secret-guardrails", "passed", "Odoo startup refuses missing or placeholder secrets."))

    tracked_secret_files = []
    local_secret_files = []
    secrets_dir = ROOT_DIR / "secrets"
    tracked_files = _git_tracked_files("secrets")
    if secrets_dir.is_dir():
        for path in sorted(secrets_dir.rglob("*")):
            if path.is_file() and not path.name.endswith(".example"):
                rel_path = _repo_relative(path)
                if tracked_files is None or rel_path in tracked_files:
                    tracked_secret_files.append(rel_path)
                else:
                    local_secret_files.append(rel_path)
    if tracked_secret_files:
        blockers.append("Tracked non-example secret file(s): %s" % ", ".join(tracked_secret_files))
        rows.append(_row("committed-secret-files", "failed", ", ".join(tracked_secret_files)))
    else:
        rows.append(_row("committed-secret-files", "passed", "No non-example secret files are tracked by git."))
    if local_secret_files:
        warnings.append("Ignored local runtime secret file(s) present: %s" % ", ".join(local_secret_files))
        rows.append(_row("local-runtime-secret-files", "warning", ", ".join(local_secret_files)))
    else:
        rows.append(_row("local-runtime-secret-files", "passed", "No ignored local runtime secret files detected."))

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
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "secret_manager": {
            "provider_present": _present(args.secret_manager_provider),
            "provider": args.secret_manager_provider.strip(),
            "reference_present": _present(args.secret_manager_reference),
            "rotation_policy_reference_present": _present(args.secret_rotation_policy_ref),
            "access_review_reference_present": _present(args.secret_access_review_ref),
        },
        "required_secrets": required_secrets,
        "non_secret_templates": non_secret,
        "secret_example_templates": secret_examples,
        "runtime_config_files": config_files_manifest,
        "compose_guardrails": compose_guardrails,
        "startup_guardrails": startup_guardrails,
        "real_secret_files": tracked_secret_files,
        "local_runtime_secret_files": local_secret_files,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "secret_manager_provider=%s" % (args.secret_manager_provider.strip() or "<unset>"),
            "secret_manager_reference_present=%s" % int(_present(args.secret_manager_reference)),
            "secret_rotation_policy_present=%s" % int(_present(args.secret_rotation_policy_ref)),
            "secret_access_review_present=%s" % int(_present(args.secret_access_review_ref)),
            "required_secret_count=%s" % len(required_secrets),
            "non_secret_template_count=%s" % len(non_secret),
            "secret_example_template_count=%s" % len(secret_examples),
            "config_file_count=%s" % len(config_files_manifest),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "secret-manager-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Secret manager evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
