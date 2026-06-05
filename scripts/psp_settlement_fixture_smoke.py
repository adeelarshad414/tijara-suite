#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests/fixtures/psp_settlements"
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
REQUIRED_EVENT_TYPES = {"payment", "refund", "chargeback", "settlement"}
PROFILE_FIXTURES = {
    "jazzcash_merchant_v1": {
        "provider": "jazzcash",
        "format": "json",
        "path": FIXTURE_DIR / "jazzcash_merchant_v1.json",
        "cents": False,
    },
    "easypaisa_merchant_v1": {
        "provider": "easypaisa",
        "format": "json",
        "path": FIXTURE_DIR / "easypaisa_merchant_v1.json",
        "cents": False,
    },
    "stripe_balance_v1": {
        "provider": "stripe",
        "format": "csv",
        "path": FIXTURE_DIR / "stripe_balance_v1.csv",
        "cents": True,
    },
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _hash_payload(payload):
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _repo_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _profile_from_path(path):
    name = path.name.lower()
    for profile in PROFILE_FIXTURES:
        if profile in name:
            return profile
    raise ValueError("Cannot infer PSP parser profile from fixture name: %s" % path)


def _fixture_paths(values):
    if values:
        paths = []
        for value in values:
            path = Path(value)
            if not path.is_absolute():
                path = ROOT_DIR / path
            paths.append(path)
        return paths
    return [config["path"] for config in PROFILE_FIXTURES.values()]


def _load_fixture(path, profile):
    config = PROFILE_FIXTURES[profile]
    if not path.is_file():
        raise ValueError("Fixture does not exist: %s" % path)
    if config["format"] == "csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            lines = [dict(row) for row in csv.DictReader(handle)]
        payload = {"format": "csv", "profile": profile, "lines": lines}
    else:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            lines = payload
        elif isinstance(payload, dict):
            lines = payload.get("lines") or payload.get("transactions") or payload.get("data") or []
        else:
            lines = []
    if not isinstance(lines, list) or not lines:
        raise ValueError("Fixture must contain a non-empty list of settlement lines: %s" % path)
    if not all(isinstance(line, dict) for line in lines):
        raise ValueError("Every settlement fixture line must be an object: %s" % path)
    return payload, lines


def _secret_like_keys(value, prefix=""):
    flagged = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = "%s.%s" % (prefix, key) if prefix else str(key)
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in SECRET_KEY_PARTS):
                flagged.append(key_path)
            flagged.extend(_secret_like_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            flagged.extend(_secret_like_keys(child, "%s[%s]" % (prefix, index)))
    return flagged


def _first(payload, keys):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return ""


def _float(value):
    try:
        if isinstance(value, str):
            value = (
                value.replace(",", "")
                .replace("PKR", "")
                .replace("Rs.", "")
                .replace("Rs", "")
                .strip()
            )
            if value.startswith("(") and value.endswith(")"):
                value = "-%s" % value[1:-1]
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _amount(payload, keys, cents=False):
    for key in keys:
        if payload.get(key) in (None, ""):
            continue
        value = _float(payload.get(key))
        return value / 100.0 if cents else value
    return 0.0


def _event_type(line):
    raw_type = str(
        _first(
            line,
            [
                "payment_event_type",
                "event_type",
                "eventType",
                "type",
                "transaction_type",
                "pp_TxnType",
                "reporting_category",
                "source_type",
            ],
        )
    ).lower()
    status = str(
        _first(
            line,
            [
                "status",
                "payment_status",
                "transactionStatus",
                "pp_ResponseMessage",
                "description",
            ],
        )
    ).lower()
    combined = "%s %s" % (raw_type, status)
    if "chargeback" in combined or "dispute" in combined:
        return "chargeback"
    if "refund" in combined or "reversal" in combined or "reversed" in combined:
        return "refund"
    if "settlement" in combined or "payout" in combined:
        return "settlement"
    if raw_type in {"charge", "payment", "paid", "sale", "capture", "captured"}:
        return "payment"
    if status in {"paid", "success", "succeeded", "completed", "settled"}:
        return "payment"
    return "unknown"


def _normalize_line(line, profile, sequence):
    config = PROFILE_FIXTURES[profile]
    provider = config["provider"]
    cents = config["cents"]
    event_reference = _first(
        line,
        [
            "event_reference",
            "event_id",
            "id",
            "balance_transaction",
            "pp_TxnRefNo",
            "transactionId",
            "transaction_id",
            "bank_reference",
            "deposit_reference",
            "settlement_reference",
            "reference",
        ],
    )
    transaction_id = _first(
        line,
        [
            "transaction_id",
            "transactionId",
            "payment_intent",
            "charge",
            "source",
            "pp_RetreivalReferenceNo",
            "pp_TxnRefNo",
            "rrn",
            "bank_trace",
        ],
    ) or event_reference
    gross = _amount(
        line,
        [
            "gross_amount",
            "amount",
            "amount_total",
            "pp_Amount",
            "transactionAmount",
            "deposit_amount",
            "credit_amount",
            "debit_amount",
        ],
        cents=cents,
    )
    fee = _amount(
        line,
        [
            "provider_fee_amount",
            "fee_amount",
            "fee",
            "pp_FeeAmount",
            "serviceCharges",
            "bank_fee",
            "charges",
        ],
        cents=cents,
    )
    explicit_net = _amount(line, ["net_amount", "net", "settled_amount"], cents=cents)
    net = explicit_net if explicit_net else gross - fee
    signed_payload = {
        "provider": provider,
        "profile": profile,
        "sequence": sequence,
        "line": line,
    }
    return {
        "sequence": sequence,
        "provider": provider,
        "profile": profile,
        "provider_event_reference": str(event_reference or ""),
        "provider_transaction_id": str(transaction_id or ""),
        "payment_event_type": _event_type(line),
        "gross_amount": gross,
        "fee_amount": fee,
        "net_amount": net,
        "line_hash": _hash_payload(signed_payload),
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
# PSP Settlement Fixture Smoke

- Status: {decision}
- Run ID: {context["run_id"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Fixture smoke manifest: psp-fixture-smoke.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Validate Tijara PSP settlement parser fixtures.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PSP_FIXTURE_RUN_ID", _default_run_id()))
    parser.add_argument("--fixture", action="append", default=[])
    parser.add_argument("--output", default=os.environ.get("TIJARA_PSP_FIXTURE_OUTPUT", ""))
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PSP_FIXTURE_NON_STRICT")),
    )
    args = parser.parse_args()
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/psp-fixture-smoke" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    fixtures = []
    for path in _fixture_paths(args.fixture):
        try:
            profile = _profile_from_path(path)
            payload, lines = _load_fixture(path, profile)
            flagged_keys = _secret_like_keys(payload)
            normalized = [
                _normalize_line(line, profile, sequence)
                for sequence, line in enumerate(lines, start=1)
            ]
            event_types = {line["payment_event_type"] for line in normalized}
            missing_types = sorted(REQUIRED_EVENT_TYPES - event_types)
            fixture_hash = _hash_payload(payload)
            fixture = {
                "path": _repo_relative(path),
                "profile": profile,
                "provider": PROFILE_FIXTURES[profile]["provider"],
                "format": PROFILE_FIXTURES[profile]["format"],
                "fixture_hash": fixture_hash,
                "line_count": len(normalized),
                "event_types": sorted(event_types),
                "totals": {
                    "gross_amount": sum(line["gross_amount"] for line in normalized),
                    "fee_amount": sum(line["fee_amount"] for line in normalized),
                    "net_amount": sum(line["net_amount"] for line in normalized),
                },
                "lines": normalized,
            }
            fixtures.append(fixture)
            if flagged_keys:
                message = "%s contains secret-like keys: %s" % (fixture["path"], ", ".join(flagged_keys))
                blockers.append(message)
                rows.append({"name": "%s-secret-safety" % profile, "status": "failed", "message": message})
            else:
                rows.append(
                    {
                        "name": "%s-secret-safety" % profile,
                        "status": "passed",
                        "message": "No secret-like keys found.",
                    }
                )
            if missing_types:
                message = "%s missing event type(s): %s" % (fixture["path"], ", ".join(missing_types))
                if args.non_strict:
                    warnings.append(message)
                    status = "warning"
                else:
                    blockers.append(message)
                    status = "failed"
                rows.append({"name": "%s-event-coverage" % profile, "status": status, "message": message})
            else:
                rows.append(
                    {
                        "name": "%s-event-coverage" % profile,
                        "status": "passed",
                        "message": "Payment, refund, chargeback, and settlement lines are present.",
                    }
                )
            if any(not line["provider_event_reference"] for line in normalized):
                message = "%s contains a line without provider event reference." % fixture["path"]
                blockers.append(message)
                rows.append({"name": "%s-reference" % profile, "status": "failed", "message": message})
            else:
                rows.append(
                    {
                        "name": "%s-reference" % profile,
                        "status": "passed",
                        "message": "%s provider event reference(s) present." % len(normalized),
                    }
                )
            rows.append(
                {
                    "name": "%s-hash" % profile,
                    "status": "passed",
                    "message": "Fixture and %s line hash(es) generated." % len(normalized),
                }
            )
        except Exception as error:
            message = "%s failed: %s" % (_repo_relative(path), error)
            blockers.append(message)
            rows.append({"name": "%s-load" % path.name, "status": "failed", "message": message})

    if not fixtures:
        message = "No PSP settlement fixtures were validated."
        blockers.append(message)
        rows.append({"name": "fixture-count", "status": "failed", "message": message})

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
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "required_event_types": sorted(REQUIRED_EVENT_TYPES),
        "fixtures": fixtures,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "fixture_count=%s" % len(fixtures),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "psp-fixture-smoke.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("PSP settlement fixture smoke written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
