#!/usr/bin/env python3
import argparse
import ast
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ADAPTER_SOURCE = ROOT_DIR / "addons/tijara_saas_control/models/payment_provider_adapter.py"


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _load_provider_contracts():
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(ADAPTER_SOURCE))
    for node in module.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "PROVIDER_CONTRACTS" in names:
                return ast.literal_eval(node.value)
    raise RuntimeError("PROVIDER_CONTRACTS not found in %s" % ADAPTER_SOURCE)


def _parse_key_value(items, name):
    values = {}
    for raw in items or []:
        if "=" not in raw:
            raise ValueError("%s must use provider=value format: %s" % (name, raw))
        key, value = raw.split("=", 1)
        key = key.strip().lower()
        if not key:
            raise ValueError("%s provider cannot be blank." % name)
        values[key] = value.strip()
    return values


def _provider_env_prefix(provider):
    return "TIJARA_%s" % provider.upper()


def _certification_value(provider, field, overrides):
    provider = provider.lower()
    if provider in overrides:
        return overrides[provider]
    return os.environ.get("%s_CERTIFICATION_%s" % (_provider_env_prefix(provider), field.upper()), "")


def _secret_present(provider, contract, overrides):
    provider = provider.lower()
    if provider in overrides:
        return _truthy(overrides[provider])
    env_name = contract.get("secret_env")
    return bool(str(os.environ.get(env_name, "")).strip()) if env_name else False


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _provider_readiness(provider, contract, require_native, secret_overrides, cert_refs, cert_statuses):
    rows = []
    blockers = []
    warnings = []

    def add(name, status, message):
        rows.append(_row("%s-%s" % (provider, name), status, message))
        if status == "failed":
            blockers.append(message)
        elif status == "warning":
            warnings.append(message)

    secret_configured = _secret_present(provider, contract, secret_overrides)
    certification_reference = _certification_value(provider, "reference", cert_refs)
    certification_status = _certification_value(provider, "status", cert_statuses).lower()

    add("webhook-route", "passed", "Provider webhook route is %s." % contract["webhook_route"])
    add(
        "settlement-parser",
        "passed" if contract.get("settlement_parser_profile") else "warning",
        "Settlement parser profile is %s." % (contract.get("settlement_parser_profile") or "not configured"),
    )
    if contract.get("signature_required"):
        if secret_configured:
            add("native-signature-secret", "passed", "Native signature secret presence is confirmed.")
        elif require_native:
            add(
                "native-signature-secret",
                "failed",
                "Native signatures are required, but secret presence is not confirmed.",
            )
        else:
            add(
                "native-signature-secret",
                "warning",
                "Native signature secret presence is not confirmed.",
            )
    else:
        add(
            "native-signature-secret",
            "passed",
            "Native provider signature is not required for this provider profile.",
        )

    if {"refund", "chargeback", "settlement"}.issubset(set(contract.get("event_types") or [])):
        add("event-coverage", "passed", "Refund, chargeback, and settlement event mapping is declared.")
    else:
        add("event-coverage", "failed", "Refund, chargeback, and settlement event mapping is incomplete.")

    if contract.get("certification_required"):
        if certification_reference and certification_status in {"approved", "passed", "certified"}:
            add("certification", "passed", "Provider certification reference is present and approved.")
        elif certification_reference:
            add("certification", "warning", "Provider certification reference is present but not approved.")
        else:
            add("certification", "warning", "Provider certification reference is missing.")
    else:
        add("certification", "passed", "External PSP certification is not required for this profile.")

    decision = "failed" if blockers else "warning" if warnings else "passed"
    return {
        "provider": provider,
        "label": contract.get("label"),
        "decision": decision,
        "ci_status": "fail" if blockers else "pass_with_warnings" if warnings else "pass",
        "signature": {
            "required": bool(contract.get("signature_required")),
            "algorithm": contract.get("signature_algorithm"),
            "secret_present": secret_configured,
            "secret_env": contract.get("secret_env"),
            "secret_param": contract.get("secret_param"),
        },
        "certification": {
            "required": bool(contract.get("certification_required")),
            "reference_present": bool(certification_reference),
            "status": certification_status or "",
        },
        "contract": {
            "webhook_route": contract.get("webhook_route"),
            "settlement_parser_profile": contract.get("settlement_parser_profile"),
            "event_types": contract.get("event_types") or [],
            "refund_fields": contract.get("refund_fields") or [],
            "chargeback_fields": contract.get("chargeback_fields") or [],
            "settlement_fields": contract.get("settlement_fields") or [],
        },
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }


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
# PSP Readiness Evidence

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

- PSP readiness manifest: psp-readiness.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export redacted Tijara PSP provider readiness evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PSP_READINESS_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_PSP_READINESS_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PSP_READINESS_OUTPUT", ""))
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument("--secret-present", action="append", default=[])
    parser.add_argument("--certification-reference", action="append", default=[])
    parser.add_argument("--certification-status", action="append", default=[])
    parser.add_argument(
        "--require-native-signatures",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PSP_READINESS_NON_STRICT")),
    )
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/psp-readiness" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    contracts = _load_provider_contracts()
    secret_overrides = _parse_key_value(args.secret_present, "--secret-present")
    cert_refs = _parse_key_value(args.certification_reference, "--certification-reference")
    cert_statuses = _parse_key_value(args.certification_status, "--certification-status")
    providers = [provider.lower() for provider in args.provider] or sorted(contracts)

    provider_results = []
    rows = []
    blockers = []
    warnings = []
    for provider in providers:
        if provider not in contracts:
            message = "Unknown PSP provider profile: %s" % provider
            blockers.append(message)
            rows.append(_row("%s-contract" % provider, "failed", message))
            continue
        result = _provider_readiness(
            provider,
            contracts[provider],
            args.require_native_signatures,
            secret_overrides,
            cert_refs,
            cert_statuses,
        )
        provider_results.append(result)
        rows.extend(result["checks"])
        blockers.extend("%s: %s" % (provider, item) for item in result["blockers"])
        warnings.extend("%s: %s" % (provider, item) for item in result["warnings"])

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
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "require_native_signatures": bool(args.require_native_signatures),
        "providers": provider_results,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "provider_count=%s" % len(provider_results),
            "require_native_signatures=%s" % int(args.require_native_signatures),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "psp-readiness.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("PSP readiness evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
