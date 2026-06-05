#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PLACEHOLDER_PREFIXES = ("replace-", "replace_with", "change-me", "changeme")


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _value(cli_value, env_name, default=""):
    return cli_value if cli_value not in (None, "") else os.environ.get(env_name, default)


def _present(value):
    value = str(value or "").strip()
    if not value:
        return False
    normalized = value.lower()
    return not any(normalized.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _sha256(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest() if value else ""


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# FBR Readiness Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- FBR mode: {context["adapter_mode"]}
- Certification environment: {context["certification_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- FBR readiness manifest: fbr-readiness.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export redacted Tijara FBR readiness evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_FBR_READINESS_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_FBR_READINESS_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_FBR_READINESS_OUTPUT", ""))
    parser.add_argument("--adapter-mode", choices=["dry_run", "live"], default="")
    parser.add_argument("--certification-environment", choices=["sandbox", "uat", "production"], default="")
    parser.add_argument("--provider-name", default="")
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--client-id", default="")
    parser.add_argument("--credential-reference", default="")
    parser.add_argument("--sandbox-reference", default="")
    parser.add_argument("--fbr-pos-id", default="")
    parser.add_argument("--branch-code", default="")
    parser.add_argument("--payload-hash", default="")
    parser.add_argument("--client-secret-present", action="store_true")
    parser.add_argument("--allow-insecure-endpoint", action="store_true")
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_FBR_READINESS_NON_STRICT")))
    args = parser.parse_args()

    adapter_mode = _value(args.adapter_mode, "FBR_ADAPTER_MODE", "dry_run")
    certification_environment = _value(
        args.certification_environment,
        "FBR_CERTIFICATION_ENVIRONMENT",
        "sandbox",
    )
    provider_name = _value(args.provider_name, "FBR_PROVIDER_NAME")
    endpoint = _value(args.endpoint, "FBR_ADAPTER_ENDPOINT")
    client_id = _value(args.client_id, "FBR_CLIENT_ID")
    credential_reference = _value(args.credential_reference, "FBR_CREDENTIAL_REFERENCE")
    sandbox_reference = _value(args.sandbox_reference, "FBR_SANDBOX_REFERENCE")
    fbr_pos_id = _value(args.fbr_pos_id, "FBR_POS_ID")
    branch_code = _value(args.branch_code, "FBR_BRANCH_CODE")
    payload_hash = _value(args.payload_hash, "FBR_PAYLOAD_HASH")
    secret_present = args.client_secret_present or _present(os.environ.get("FBR_CLIENT_SECRET"))
    allow_insecure_endpoint = args.allow_insecure_endpoint or _truthy(os.environ.get("FBR_ALLOW_INSECURE_ENDPOINT"))
    require_live = args.require_live or _truthy(os.environ.get("TIJARA_FBR_REQUIRE_LIVE"))

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/fbr-readiness" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    def add(name, status, message):
        rows.append(_row(name, status, message))
        if status == "failed":
            blockers.append(message)
        elif status == "warning":
            warnings.append(message)

    if adapter_mode == "live":
        add("adapter-mode", "passed", "FBR adapter mode is live.")
    elif require_live or certification_environment == "production":
        add("adapter-mode", "failed", "FBR adapter must be live for production readiness.")
    else:
        add("adapter-mode", "warning", "FBR adapter mode is dry_run; use only for staging/sandbox evidence.")

    if certification_environment in {"sandbox", "uat", "production"}:
        add("certification-environment", "passed", "Certification environment is %s." % certification_environment)
    else:
        add("certification-environment", "failed", "Certification environment is invalid.")

    if _present(provider_name):
        add("certified-provider", "passed", "Certified provider name is recorded.")
    elif adapter_mode == "live" or require_live:
        add("certified-provider", "failed", "Certified provider name is required for live FBR readiness.")
    else:
        add("certified-provider", "warning", "Certified provider name is not recorded.")

    if endpoint.startswith("https://"):
        add("endpoint", "passed", "FBR endpoint uses HTTPS.")
    elif endpoint and allow_insecure_endpoint and certification_environment != "production":
        add("endpoint", "warning", "FBR endpoint is insecure but allowed for non-production testing.")
    elif adapter_mode == "live" or require_live:
        add("endpoint", "failed", "Live FBR endpoint must use HTTPS.")
    else:
        add("endpoint", "warning", "FBR endpoint is not configured for dry-run evidence.")

    if _present(client_id):
        add("client-id", "passed", "FBR client id presence is confirmed.")
    elif adapter_mode == "live" or require_live:
        add("client-id", "failed", "FBR client id is required for live readiness.")
    else:
        add("client-id", "warning", "FBR client id is not confirmed.")

    if _present(credential_reference) or secret_present:
        add("credential", "passed", "FBR credential presence is confirmed without exposing secret values.")
    elif adapter_mode == "live" or require_live:
        add("credential", "failed", "FBR credential presence is required for live readiness.")
    else:
        add("credential", "warning", "FBR credential presence is not confirmed.")

    if certification_environment in {"sandbox", "uat"}:
        if _present(sandbox_reference):
            add("sandbox-reference", "passed", "Sandbox/UAT reference is recorded.")
        else:
            add("sandbox-reference", "warning", "Sandbox/UAT reference is not recorded yet.")
    elif _present(sandbox_reference):
        add("sandbox-reference", "passed", "Certification reference is recorded.")
    else:
        add("sandbox-reference", "failed", "Production readiness requires sandbox/live certification reference.")

    if _present(fbr_pos_id):
        add("fbr-pos-id", "passed", "FBR POS ID is recorded.")
    else:
        add("fbr-pos-id", "warning", "FBR POS ID is not recorded in readiness evidence.")

    if _present(branch_code):
        add("branch-code", "passed", "Branch code is recorded.")
    else:
        add("branch-code", "warning", "Branch code is not recorded in readiness evidence.")

    if _present(payload_hash):
        add("payload-hash", "passed", "FBR payload hash is recorded.")
    elif adapter_mode == "live" or require_live:
        add("payload-hash", "warning", "FBR payload hash is not recorded yet.")
    else:
        add("payload-hash", "warning", "FBR payload hash is not recorded for dry-run evidence.")

    if blockers:
        decision = "warning" if args.non_strict else "failed"
        ci_status = "pass_with_warnings" if args.non_strict else "fail"
        if args.non_strict:
            warnings.extend(blockers)
            blockers = []
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "passed"
        ci_status = "pass"

    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "adapter_mode": adapter_mode,
        "certification_environment": certification_environment,
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "adapter": {
            "mode": adapter_mode,
            "provider_name_present": _present(provider_name),
            "endpoint_present": _present(endpoint),
            "endpoint_https": endpoint.startswith("https://"),
            "endpoint_hash": _sha256(endpoint),
            "allow_insecure_endpoint": bool(allow_insecure_endpoint),
            "client_id_present": _present(client_id),
            "credential_reference_present": _present(credential_reference),
            "client_secret_present": bool(secret_present),
        },
        "certification": {
            "environment": certification_environment,
            "sandbox_reference_present": _present(sandbox_reference),
            "fbr_pos_id_present": _present(fbr_pos_id),
            "branch_code_present": _present(branch_code),
            "payload_hash_present": _present(payload_hash),
            "payload_hash": payload_hash if _present(payload_hash) else "",
        },
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "adapter_mode=%s" % adapter_mode,
            "certification_environment=%s" % certification_environment,
            "provider_name_present=%s" % int(_present(provider_name)),
            "endpoint_present=%s" % int(_present(endpoint)),
            "endpoint_https=%s" % int(endpoint.startswith("https://")),
            "client_id_present=%s" % int(_present(client_id)),
            "credential_reference_present=%s" % int(_present(credential_reference)),
            "client_secret_present=%s" % int(secret_present),
            "sandbox_reference_present=%s" % int(_present(sandbox_reference)),
            "fbr_pos_id_present=%s" % int(_present(fbr_pos_id)),
            "branch_code_present=%s" % int(_present(branch_code)),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "fbr-readiness.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("FBR readiness evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
