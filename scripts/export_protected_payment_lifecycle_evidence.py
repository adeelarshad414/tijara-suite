#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
SOURCE_CONTRACTS = [
    {
        "name": "payment-webhook-route",
        "path": "addons/tijara_saas_control/controllers/payment_webhooks.py",
        "tokens": [
            "/tijara/saas/payment/webhook/<string:provider>",
            "hmac.compare_digest",
            "tijara_verify_provider_signature",
            "_require_native_signature",
        ],
    },
    {
        "name": "payment-webhook-event-model",
        "path": "addons/tijara_saas_control/models/payment_webhook_event.py",
        "tokens": [
            '_name = "tijara.saas.payment.webhook.event"',
            "payment_event_type",
            "refund_reference",
            "chargeback_reference",
            "signature_status",
            "tijara_from_payload",
            "tijara_verify_provider_signature",
            "action_apply",
        ],
    },
    {
        "name": "provider-adapter-contracts",
        "path": "addons/tijara_saas_control/models/payment_provider_adapter.py",
        "tokens": [
            "PROVIDER_CONTRACTS",
            "jazzcash-secure-hash",
            "easypaisa-hmac-sha256",
            "stripe-hmac-sha256",
            "refund_fields",
            "chargeback_fields",
            "settlement_fields",
        ],
    },
    {
        "name": "settlement-import-reconciliation",
        "path": "addons/tijara_saas_control/models/payment_settlement.py",
        "tokens": [
            '_name = "tijara.saas.payment.settlement.batch"',
            '_name = "tijara.saas.payment.settlement.line"',
            "SETTLEMENT_PARSER_PROFILES",
            "action_import_statement_payload",
            "action_create_dispute_cases",
            "action_generate_accounting_actions",
            "action_create_draft_accounting_moves",
            "action_mark_reconciled",
        ],
    },
    {
        "name": "refund-chargeback-cases",
        "path": "addons/tijara_saas_control/models/payment_dispute.py",
        "tokens": [
            '_name = "tijara.saas.payment.dispute"',
            '("refund", "Refund")',
            '("chargeback", "Chargeback")',
            "action_mark_refunded",
            "action_generate_accounting_actions",
        ],
    },
    {
        "name": "payment-accounting-actions",
        "path": "addons/tijara_saas_control/models/payment_accounting_action.py",
        "tokens": [
            '_name = "tijara.saas.payment.accounting.action"',
            "refund_credit_note",
            "refund_payment",
            "chargeback_receivable",
            "chargeback_fee",
            "action_create_draft_accounting_move",
            "action_approve",
        ],
    },
    {
        "name": "payment-lifecycle-views",
        "path": "addons/tijara_saas_control/views/payment_webhook_event_views.xml",
        "tokens": [
            "Invalid Signature",
            "Refunds",
            "Chargebacks",
            "Settlements",
            "Create Dispute Case",
        ],
    },
]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _dedupe(items):
    clean = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            clean.append(value)
    return clean


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s"
            % (row["name"], row["status"], row["message"], row.get("source") or "")
        )
    return "\n".join(lines)


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


def _run_command(command):
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command[:],
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _payload_status(payload, exit_code, fail_on_warning):
    decision = str(payload.get("decision") or "").strip().lower()
    ci_status = str(payload.get("ci_status") or "").strip().lower()
    if exit_code != 0 or decision in {"failed", "blocked"} or ci_status == "fail":
        return "failed"
    if fail_on_warning and (decision in {"warning", "warn"} or ci_status == "pass_with_warnings"):
        return "failed"
    if decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        return "warning"
    return "passed"


def _summary(context, rows, blockers, warnings):
    status = "failed" if blockers else "warning" if warnings else "passed"
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    provider_lines = "\n".join("- %s" % provider for provider in context["providers"]) or "- None"
    return f"""
# Protected Payment Lifecycle Evidence

- Status: {status}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}
- Require native signatures: {context["require_native_signatures"]}
- Require provider certification: {context["require_provider_certification"]}

## Providers

{provider_lines}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Payment lifecycle manifest: protected-payment-lifecycle-evidence.json
- PSP readiness folder: psp-readiness/
- PSP fixture smoke folder: psp-fixture-smoke/
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export protected PSP payment lifecycle evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PAYMENT_LIFECYCLE_OUTPUT", ""))
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument(
        "--providers",
        default=os.environ.get("TIJARA_PAYMENT_LIFECYCLE_PROVIDERS", "jazzcash,easypaisa,stripe"),
    )
    parser.add_argument(
        "--require-native-signatures",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PAYMENT_LIFECYCLE_REQUIRE_NATIVE_SIGNATURES"))
        or _truthy(os.environ.get("TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES")),
    )
    parser.add_argument(
        "--require-provider-certification",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PAYMENT_LIFECYCLE_REQUIRE_PROVIDER_CERTIFICATION")),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PAYMENT_LIFECYCLE_FAIL_ON_WARNING")),
    )
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PAYMENT_LIFECYCLE_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False

    certification_groups = set(_csv_items(os.environ.get("TIJARA_PROTECTED_CERTIFICATION_GROUPS", "")))
    require_provider_certification = args.require_provider_certification or "psp" in certification_groups
    providers = _dedupe(args.provider + _csv_items(args.providers))

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-payment-lifecycle" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    try:
        metadata = _metadata_items(args.metadata)
        rows.append(_row("metadata-format", "passed", "%s metadata item(s) parsed." % len(metadata)))
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append(_row("metadata-format", "failed", str(error)))

    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append(_row("metadata-secret-safety", "failed", message))
    else:
        rows.append(_row("metadata-secret-safety", "passed", "No secret-like metadata keys found."))

    source_reviews = []
    for contract in SOURCE_CONTRACTS:
        path = ROOT_DIR / contract["path"]
        content = _read_text(path)
        missing = [token for token in contract["tokens"] if token not in content]
        source_reviews.append(
            {
                "name": contract["name"],
                "path": contract["path"],
                "missing_tokens": missing,
                "token_count": len(contract["tokens"]),
            }
        )
        if missing:
            message = "Missing source contract token(s): %s" % ", ".join(missing)
            blockers.append("%s: %s" % (contract["name"], message))
            rows.append(_row(contract["name"], "failed", message, contract["path"]))
        else:
            rows.append(_row(contract["name"], "passed", "Source contract is present.", contract["path"]))

    psp_output = output / "psp-readiness"
    psp_command = [
        "python3",
        "scripts/export_psp_readiness.py",
        "--run-id",
        args.run_id,
        "--target-environment",
        args.target_environment,
        "--output",
        str(psp_output),
    ]
    for provider in providers:
        psp_command.extend(["--provider", provider])
    if args.require_native_signatures or require_provider_certification:
        psp_command.append("--require-native-signatures")
    if args.non_strict:
        psp_command.append("--non-strict")
    psp_run = _run_command(psp_command)
    psp_payload = _read_json(psp_output / "psp-readiness.json")
    psp_status = _payload_status(psp_payload, psp_run["exit_code"], args.fail_on_warning)
    rows.append(
        _row(
            "psp-readiness",
            psp_status,
            "PSP readiness decision is %s/%s."
            % (psp_payload.get("decision") or "unknown", psp_payload.get("ci_status") or "unknown"),
            str(psp_output),
        )
    )
    if psp_status == "failed" and (args.require_native_signatures or require_provider_certification or not args.non_strict):
        blockers.append("PSP readiness evidence is failed.")
    elif psp_status != "passed":
        warnings.append("PSP readiness evidence is %s." % psp_status)

    provider_reviews = psp_payload.get("providers") or []
    if require_provider_certification:
        not_certified = []
        for review in provider_reviews:
            certification = review.get("certification") or {}
            if certification.get("required") and (
                not certification.get("reference_present")
                or str(certification.get("status") or "").lower() not in {"approved", "passed", "certified"}
            ):
                not_certified.append(review.get("provider") or "unknown")
        if not_certified:
            message = "Provider certification is not approved for: %s" % ", ".join(sorted(not_certified))
            blockers.append(message)
            rows.append(_row("provider-certification", "failed", message, str(psp_output)))
        else:
            rows.append(_row("provider-certification", "passed", "Required provider certifications are approved.", str(psp_output)))
    else:
        rows.append(_row("provider-certification", "passed", "Provider certification is not required for this protected run."))

    fixture_output = output / "psp-fixture-smoke"
    fixture_command = [
        "python3",
        "scripts/psp_settlement_fixture_smoke.py",
        "--run-id",
        args.run_id,
        "--output",
        str(fixture_output),
    ]
    fixture_run = _run_command(fixture_command)
    fixture_payload = _read_json(fixture_output / "psp-fixture-smoke.json")
    fixture_status = _payload_status(fixture_payload, fixture_run["exit_code"], args.fail_on_warning)
    rows.append(
        _row(
            "psp-fixture-smoke",
            fixture_status,
            "PSP fixture smoke decision is %s/%s."
            % (fixture_payload.get("decision") or "unknown", fixture_payload.get("ci_status") or "unknown"),
            str(fixture_output),
        )
    )
    if fixture_status == "failed":
        blockers.append("PSP settlement fixture smoke is failed.")
    elif fixture_status != "passed":
        warnings.append("PSP settlement fixture smoke is %s." % fixture_status)

    required_events = set(fixture_payload.get("required_event_types") or ["payment", "refund", "chargeback", "settlement"])
    fixture_reviews = fixture_payload.get("fixtures") or []
    providers_with_full_events = []
    for fixture in fixture_reviews:
        event_types = set(fixture.get("event_types") or [])
        if required_events.issubset(event_types):
            providers_with_full_events.append(fixture.get("provider"))
    missing_event_providers = sorted(set(providers) - set(providers_with_full_events))
    if missing_event_providers:
        message = "Settlement fixtures do not prove full lifecycle events for: %s" % ", ".join(missing_event_providers)
        blockers.append(message)
        rows.append(_row("fixture-lifecycle-coverage", "failed", message, str(fixture_output)))
    else:
        rows.append(
            _row(
                "fixture-lifecycle-coverage",
                "passed",
                "Payment, refund, chargeback, and settlement fixtures are present for all providers.",
                str(fixture_output),
            )
        )

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    if args.fail_on_warning and warnings:
        blockers.extend("Warning treated as blocker: %s" % warning for warning in warnings)
        blockers = _dedupe(blockers)

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
        "providers": providers,
        "require_native_signatures": bool(args.require_native_signatures),
        "require_provider_certification": bool(require_provider_certification),
        "fail_on_warning": bool(args.fail_on_warning),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
        "source_reviews": source_reviews,
        "psp_readiness": {
            "status": psp_status,
            "output": str(psp_output),
            "payload": psp_payload,
            "run": psp_run,
        },
        "fixture_smoke": {
            "status": fixture_status,
            "output": str(fixture_output),
            "payload": fixture_payload,
            "run": fixture_run,
        },
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "providers=%s" % ",".join(providers),
            "require_native_signatures=%s" % int(args.require_native_signatures),
            "require_provider_certification=%s" % int(require_provider_certification),
            "fail_on_warning=%s" % int(args.fail_on_warning),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-payment-lifecycle-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Protected payment lifecycle evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
