#!/usr/bin/env python3
"""Export redacted infrastructure-provider readiness evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PROVIDERS = {
    "cloudflare": {
        "label": "Cloudflare DNS",
        "template": "deploy/config/production-infra-templates/cloudflare-dns.example.json",
        "runner": "deploy/production-infra/runners/cloudflare-dns.sh",
        "tools": ["curl"],
        "non_secret_env": ["CLOUDFLARE_ZONE_ID", "CLOUDFLARE_RECORD_ID"],
        "secret_env": ["CLOUDFLARE_API_TOKEN"],
        "source_keywords": ["cloudflare"],
        "actions": ["dns-apply", "dns-rollback"],
    },
    "route53": {
        "label": "AWS Route53 DNS",
        "template": "deploy/config/production-infra-templates/route53-dns.example.json",
        "runner": "deploy/production-infra/runners/route53-dns.sh",
        "tools": ["aws"],
        "non_secret_env": ["ROUTE53_HOSTED_ZONE_ID", "ROUTE53_PREVIOUS_TARGET"],
        "secret_env": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        "optional_secret_env": ["AWS_SESSION_TOKEN"],
        "source_keywords": ["route53"],
        "actions": ["dns-apply", "dns-rollback"],
    },
    "cert-manager": {
        "label": "Kubernetes cert-manager TLS",
        "template": "deploy/config/production-infra-templates/cert-manager-kubernetes-tls.example.json",
        "runner": "deploy/production-infra/runners/cert-manager-tls.sh",
        "tools": ["kubectl"],
        "non_secret_env": [],
        "secret_env": ["KUBECONFIG"],
        "source_keywords": ["cert-manager"],
        "actions": ["tls-apply", "tls-rollback"],
    },
    "postgres": {
        "label": "PostgreSQL backup/restore",
        "template": "deploy/config/production-infra-templates/postgres-backup-restore.example.json",
        "runner": "deploy/production-infra/runners/postgres-backup-runner.sh",
        "tools": ["bash"],
        "non_secret_env": ["POSTGRES_USER", "POSTGRES_DB"],
        "secret_env": ["POSTGRES_PASSWORD", "BACKUP_ENCRYPTION_KEY"],
        "source_keywords": ["postgres"],
        "actions": ["backup-run", "restore-drill"],
    },
}
GOOD_DECISIONS = {"approved", "dry-run", "executed", "pass", "passed", "ready"}
WARN_DECISIONS = {"passed-with-skips", "pass_with_warnings", "skipped", "warn", "warning"}
BAD_DECISIONS = {"blocked", "error", "fail", "failed"}
PLACEHOLDER_PREFIXES = ("replace-", "replace_with", "change-me", "changeme")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("infra-provider-%Y%m%dT%H%M%SZ")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _read_json(path: str | Path) -> tuple[dict, str]:
    target = _resolve(path)
    if target.is_dir():
        target = target / "production-infra-automation.json"
    if not target.is_file():
        return {}, str(target)
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        return {"_read_error": str(error)}, str(target)


def _present(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.lower()
    return not any(normalized.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _row(name: str, status: str, message: str, source: str = "") -> dict:
    return {"name": name, "status": status, "message": message, "source": source}


def _status_tsv(rows: list[dict]) -> str:
    lines = ["check\tstatus\tmessage\tsource"]
    lines.extend(
        "%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source", ""))
        for row in rows
    )
    return "\n".join(lines)


def _decision_status(payload: dict) -> str:
    if payload.get("_read_error"):
        return "failed"
    decision = str(payload.get("decision") or payload.get("status") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if decision in BAD_DECISIONS or ci_status == "fail":
        return "failed"
    if decision in WARN_DECISIONS or ci_status == "pass_with_warnings":
        return "warning"
    if decision in GOOD_DECISIONS and ci_status in {"", "pass"}:
        return "passed"
    return "warning" if decision else "missing"


def _evidence_paths(args: argparse.Namespace) -> list[str]:
    raw = list(args.production_infra_evidence or [])
    raw.extend(_csv_items(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_PRODUCTION_INFRA_EVIDENCE")))
    raw.extend(_csv_items(os.environ.get("TIJARA_PROD_OPS_PRODUCTION_INFRA_EVIDENCE")))
    seen: set[str] = set()
    paths: list[str] = []
    for item in raw:
        if item and item not in seen:
            seen.add(item)
            paths.append(item)
    return paths


def _production_infra_reviews(paths: list[str]) -> tuple[list[dict], set[str], set[str]]:
    reviews: list[dict] = []
    actions: set[str] = set()
    sources: set[str] = set()
    for raw_path in paths:
        payload, source = _read_json(raw_path)
        actions.update(payload.get("provider_template_actions") or [])
        sources.update(str(item).lower() for item in payload.get("provider_template_sources") or [])
        tenant_plans = payload.get("tenant_plans") or []
        reviews.append(
            {
                "path": source,
                "status": _decision_status(payload),
                "decision": payload.get("decision") or "",
                "ci_status": payload.get("ci_status") or "",
                "provider_template_sources": payload.get("provider_template_sources") or [],
                "provider_template_actions": payload.get("provider_template_actions") or [],
                "tenant_plan_count": len(tenant_plans),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
                "read_error": payload.get("_read_error", ""),
            }
        )
    return reviews, actions, sources


def _approval_review(label: str, payload: dict, source: str, require_real: bool, allow_assumptions: bool) -> dict:
    if not payload:
        return {
            "name": label,
            "status": "failed" if require_real else "warning",
            "message": "%s evidence is missing." % label,
            "source": source,
        }
    if payload.get("_read_error"):
        return {
            "name": label,
            "status": "failed",
            "message": "Could not read %s evidence: %s" % (label, payload["_read_error"]),
            "source": source,
        }
    status = _decision_status(payload)
    assumption_mode = bool(payload.get("assumption_mode"))
    if assumption_mode and require_real and not allow_assumptions:
        status = "failed"
        message = "%s is assumption-mode; real protected-runner approval is required." % label
    elif assumption_mode:
        message = "%s is assumption-mode and explicitly allowed for this run." % label
        status = "passed" if allow_assumptions else "warning"
    else:
        message = "%s decision is %s/%s." % (
            label,
            payload.get("decision") or payload.get("status") or "empty",
            payload.get("ci_status") or "empty",
        )
    return {"name": label, "status": status, "message": message, "source": source}


def _provider_review(provider: str, config: dict, args: argparse.Namespace, infra_actions: set[str], infra_sources: set[str]) -> dict:
    rows: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []
    assumed = provider in args.assume_provider or "all" in args.assume_provider

    def add(name: str, status: str, message: str, source: str = "") -> None:
        rows.append(_row("%s-%s" % (provider, name), status, message, source))
        if status == "failed":
            blockers.append(message)
        elif status == "warning":
            warnings.append(message)

    template = _resolve(config["template"])
    runner = _resolve(config["runner"])
    add("template", "passed" if template.is_file() else "failed", "Template file %s." % ("exists" if template.is_file() else "is missing"), _repo_relative(template))
    add("runner", "passed" if runner.is_file() else "failed", "Runner script %s." % ("exists" if runner.is_file() else "is missing"), _repo_relative(runner))
    if runner.is_file():
        add("runner-executable", "passed" if os.access(runner, os.X_OK) else "failed", "Runner executable bit %s." % ("is set" if os.access(runner, os.X_OK) else "is missing"), _repo_relative(runner))

    missing_tools = [tool for tool in config.get("tools") or [] if shutil.which(tool) is None]
    if missing_tools:
        status = "passed" if assumed and args.allow_assumptions else ("failed" if args.require_tools else "warning")
        suffix = " Assumed for this run." if status == "passed" and assumed else ""
        add("tools", status, "Missing tool(s): %s.%s" % (", ".join(missing_tools), suffix))
    else:
        add("tools", "passed", "Required CLI tool(s) found: %s." % ", ".join(config.get("tools") or []))

    missing_non_secret = [name for name in config.get("non_secret_env") or [] if not _present(os.environ.get(name))]
    if missing_non_secret:
        status = "passed" if assumed and args.allow_assumptions else ("failed" if args.require_provider_credentials else "warning")
        suffix = " Assumed for this run." if status == "passed" and assumed else ""
        add("non-secret-vars", status, "Missing non-secret variable(s): %s.%s" % (", ".join(missing_non_secret), suffix))
    else:
        add("non-secret-vars", "passed", "Required non-secret variable(s) are present or not required.")

    missing_secret = [name for name in config.get("secret_env") or [] if not _present(os.environ.get(name))]
    if missing_secret:
        status = "passed" if assumed and args.allow_assumptions else ("failed" if args.require_provider_credentials else "warning")
        suffix = " Assumed for this run." if status == "passed" and assumed else ""
        add("secret-presence", status, "Missing secret presence for: %s.%s" % (", ".join(missing_secret), suffix))
    else:
        add("secret-presence", "passed", "Required secret presence is confirmed without exposing values.")

    missing_actions = [action for action in config.get("actions") or [] if action not in infra_actions]
    if missing_actions:
        status = "failed" if args.require_production_infra_evidence else "warning"
        add("production-infra-actions", status, "Production infra evidence is missing action(s): %s." % ", ".join(missing_actions))
    else:
        add("production-infra-actions", "passed", "Production infra evidence includes required actions.")

    keywords = config.get("source_keywords") or []
    source_match = any(keyword in source for keyword in keywords for source in infra_sources)
    if source_match:
        add("production-infra-template-source", "passed", "Production infra evidence includes a provider-specific template source.")
    else:
        status = "failed" if args.require_production_infra_evidence else "warning"
        add("production-infra-template-source", status, "Production infra evidence does not include a template source for %s." % provider)

    decision = "failed" if blockers else "warning" if warnings else "passed"
    return {
        "provider": provider,
        "label": config["label"],
        "decision": decision,
        "ci_status": "fail" if blockers else "pass_with_warnings" if warnings else "pass",
        "assumption_mode": bool(assumed),
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }


def _summary(context: dict, rows: list[dict], provider_reviews: list[dict], blockers: list[str], warnings: list[str]) -> str:
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    provider_lines = "\n".join(
        "- %s: %s (%s)" % (review["provider"], review["decision"], "assumed" if review["assumption_mode"] else "real")
        for review in provider_reviews
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Infrastructure Provider Readiness

- Decision: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Strict: {context["strict"]}
- Allow assumptions: {context["allow_assumptions"]}
- Require real approvals: {context["require_real_approvals"]}
- Generated: {context["generated_at"]}
- Output: {context["output"]}

## Providers

{provider_lines or "- No providers reviewed."}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Infrastructure provider readiness manifest: infra-provider-readiness.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Tijara infrastructure provider readiness evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_OUTPUT", ""))
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument("--production-infra-evidence", action="append", default=[])
    parser.add_argument("--deployment-decision", default=os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_DEPLOYMENT_DECISION", ""))
    parser.add_argument("--rollback-decision", default=os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_ROLLBACK_DECISION", ""))
    parser.add_argument("--assume-provider", action="append", default=_csv_items(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_ASSUME_PROVIDERS")))
    parser.add_argument("--allow-assumptions", action="store_true", default=_truthy(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_ALLOW_ASSUMPTIONS")))
    parser.add_argument("--require-provider-credentials", action="store_true", default=_truthy(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_REQUIRE_CREDENTIALS")))
    parser.add_argument("--require-tools", action="store_true", default=_truthy(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_REQUIRE_TOOLS")))
    parser.add_argument("--require-production-infra-evidence", action="store_true", default=_truthy(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_REQUIRE_PRODUCTION_INFRA", "1")))
    parser.add_argument("--require-real-approvals", action="store_true", default=_truthy(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_REQUIRE_REAL_APPROVALS")))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict
    selected = args.provider or _csv_items(os.environ.get("TIJARA_INFRA_PROVIDER_READINESS_PROVIDERS")) or list(PROVIDERS)
    selected = [provider.strip().lower() for provider in selected if provider.strip()]
    args.assume_provider = [provider.strip().lower() for provider in args.assume_provider if provider.strip()]

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/infra-provider-readiness" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []

    infra_paths = _evidence_paths(args)
    infra_reviews, infra_actions, infra_sources = _production_infra_reviews(infra_paths)
    if infra_reviews:
        for review in infra_reviews:
            rows.append(_row("production-infra-evidence", review["status"], "Production infra decision is %s/%s." % (review["decision"] or "empty", review["ci_status"] or "empty"), review["path"]))
            if review["status"] == "failed":
                blockers.append("Production infra evidence failed: %s" % review["path"])
            elif review["status"] == "warning":
                warnings.append("Production infra evidence is warning: %s" % review["path"])
    elif args.require_production_infra_evidence:
        message = "Production infra evidence is required but not attached."
        rows.append(_row("production-infra-evidence", "failed" if strict else "warning", message))
        if strict:
            blockers.append(message)
        else:
            warnings.append(message)

    deployment_payload, deployment_source = _read_json(args.deployment_decision) if args.deployment_decision else ({}, "")
    rollback_payload, rollback_source = _read_json(args.rollback_decision) if args.rollback_decision else ({}, "")
    approval_rows = [
        _approval_review("deployment-decision", deployment_payload, deployment_source, args.require_real_approvals, args.allow_assumptions),
        _approval_review("rollback-decision", rollback_payload, rollback_source, args.require_real_approvals, args.allow_assumptions),
    ]
    for approval in approval_rows:
        rows.append(approval)
        if approval["status"] == "failed":
            blockers.append(approval["message"])
        elif approval["status"] == "warning":
            warnings.append(approval["message"])

    provider_reviews: list[dict] = []
    for provider in selected:
        config = PROVIDERS.get(provider)
        if not config:
            message = "Unknown infrastructure provider: %s" % provider
            rows.append(_row("provider-%s" % provider, "failed", message))
            blockers.append(message)
            continue
        review = _provider_review(provider, config, args, infra_actions, infra_sources)
        provider_reviews.append(review)
        rows.extend(review["checks"])
        blockers.extend("%s: %s" % (provider, item) for item in review["blockers"])
        warnings.extend("%s: %s" % (provider, item) for item in review["warnings"])

    if not strict and blockers:
        warnings.extend(blockers)
        blockers = []
        for row in rows:
            if row["status"] == "failed":
                row["status"] = "warning"

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
        "output": _repo_relative(output),
        "strict": bool(strict),
        "allow_assumptions": bool(args.allow_assumptions),
        "require_real_approvals": bool(args.require_real_approvals),
        "require_provider_credentials": bool(args.require_provider_credentials),
        "require_tools": bool(args.require_tools),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "providers": provider_reviews,
        "production_infra_reviews": infra_reviews,
        "deployment_decision": {
            "source": deployment_source,
            "attached": bool(deployment_payload),
            "assumption_mode": bool(deployment_payload.get("assumption_mode")),
        },
        "rollback_decision": {
            "source": rollback_source,
            "attached": bool(rollback_payload),
            "assumption_mode": bool(rollback_payload.get("assumption_mode")),
        },
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "providers=%s" % ",".join(selected),
            "assume_provider=%s" % (",".join(args.assume_provider) or "<none>"),
            "allow_assumptions=%s" % int(args.allow_assumptions),
            "require_real_approvals=%s" % int(args.require_real_approvals),
            "production_infra_evidence=%s" % (",".join(infra_paths) or "<unset>"),
            "deployment_decision=%s" % (deployment_source or "<unset>"),
            "rollback_decision=%s" % (rollback_source or "<unset>"),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "infra-provider-readiness.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, provider_reviews, blockers, warnings))
    print("Infrastructure provider readiness written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
