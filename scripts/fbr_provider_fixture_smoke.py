#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests/fixtures/fbr_provider_responses"
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
SUCCESS_STATUSES = {"accepted", "success", "successful", "submitted", "ok"}
REJECTED_STATUSES = {"rejected", "failed", "failure", "error", "declined"}
INVOICE_KEYS = ("fbr_invoice_number", "invoiceNumber", "invoice_number")
QR_KEYS = ("qr_payload", "qrCode", "qr")
UUID_KEYS = ("provider_invoice_uuid", "invoice_uuid", "uuid")
REFERENCE_KEYS = ("sandbox_reference", "certification_reference", "reference")
ERROR_KEYS = ("error", "error_message", "message", "detail")


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


def _fixture_paths(values):
    if values:
        paths = []
        for value in values:
            path = Path(value)
            paths.append(path if path.is_absolute() else ROOT_DIR / path)
        return paths
    return sorted(FIXTURE_DIR.glob("*.json"))


def _load_fixture(path):
    if not path.is_file():
        raise ValueError("Fixture does not exist: %s" % path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("FBR fixture must be a JSON object: %s" % path)
    responses = payload.get("responses") or []
    if not isinstance(responses, list) or not responses:
        raise ValueError("FBR fixture must contain a non-empty responses list: %s" % path)
    if not all(isinstance(item, dict) for item in responses):
        raise ValueError("Every FBR fixture response entry must be an object: %s" % path)
    return payload, responses


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


def _status(response):
    return str(
        response.get("status")
        or response.get("Status")
        or response.get("result")
        or response.get("Result")
        or ""
    ).strip()


def _normalized_response(entry, provider, environment, sequence):
    response = entry.get("response") or entry
    if not isinstance(response, dict):
        response = {}
    status = _status(response)
    normalized_status = status.lower()
    expected = str(entry.get("expected_result") or "accepted").strip().lower()
    invoice_number = _first(response, INVOICE_KEYS)
    qr_payload = _first(response, QR_KEYS)
    provider_invoice_uuid = _first(response, UUID_KEYS)
    certification_reference = _first(response, REFERENCE_KEYS)
    error_message = _first(response, ERROR_KEYS)
    return {
        "sequence": sequence,
        "provider": provider,
        "environment": environment,
        "name": entry.get("name") or "response-%s" % sequence,
        "expected_result": expected,
        "status": status,
        "normalized_status": normalized_status,
        "invoice_number_present": bool(invoice_number),
        "qr_payload_present": bool(qr_payload),
        "provider_invoice_uuid_present": bool(provider_invoice_uuid),
        "certification_reference_present": bool(certification_reference),
        "error_message_present": bool(error_message),
        "response_hash": _hash_payload(response),
    }


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _validate_response(normalized):
    checks = []
    name = "%s-%s" % (normalized["provider"], normalized["name"])
    expected = normalized["expected_result"]
    status = normalized["normalized_status"]
    if expected == "accepted":
        if status in SUCCESS_STATUSES:
            checks.append(_row("%s-status" % name, "passed", "Accepted response status is %s." % status))
        else:
            checks.append(_row("%s-status" % name, "failed", "Accepted response has invalid status %s." % (status or "<empty>")))
        if normalized["invoice_number_present"]:
            checks.append(_row("%s-invoice-number" % name, "passed", "FBR invoice number is present."))
        else:
            checks.append(_row("%s-invoice-number" % name, "failed", "Accepted response is missing FBR invoice number."))
        if normalized["qr_payload_present"]:
            checks.append(_row("%s-qr-payload" % name, "passed", "QR payload is present."))
        else:
            checks.append(_row("%s-qr-payload" % name, "failed", "Accepted response is missing QR payload."))
        if normalized["provider_invoice_uuid_present"]:
            checks.append(_row("%s-provider-uuid" % name, "passed", "Provider invoice UUID is present."))
        else:
            checks.append(_row("%s-provider-uuid" % name, "warning", "Provider invoice UUID is not present."))
        if normalized["certification_reference_present"]:
            checks.append(_row("%s-cert-reference" % name, "passed", "Certification reference is present."))
        else:
            checks.append(_row("%s-cert-reference" % name, "warning", "Certification reference is not present."))
    elif expected == "rejected":
        if status in REJECTED_STATUSES or (status and status not in SUCCESS_STATUSES):
            checks.append(_row("%s-rejection-status" % name, "passed", "Rejected response status is %s." % status))
        else:
            checks.append(_row("%s-rejection-status" % name, "failed", "Rejected response is missing a rejection/non-success status."))
        if normalized["error_message_present"]:
            checks.append(_row("%s-rejection-error" % name, "passed", "Rejected response includes actionable error text."))
        else:
            checks.append(_row("%s-rejection-error" % name, "failed", "Rejected response is missing actionable error text."))
        if normalized["invoice_number_present"]:
            checks.append(_row("%s-rejection-invoice" % name, "warning", "Rejected response unexpectedly includes invoice number."))
        else:
            checks.append(_row("%s-rejection-invoice" % name, "passed", "Rejected response does not include invoice number."))
    else:
        checks.append(_row("%s-expected-result" % name, "failed", "Unknown expected_result %s." % expected))
    return checks


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
# FBR Provider Fixture Smoke

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

- Fixture smoke manifest: fbr-fixture-smoke.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Validate Tijara FBR provider response fixtures.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_FBR_FIXTURE_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_FBR_FIXTURE_ENVIRONMENT", "staging"))
    parser.add_argument("--fixture", action="append", default=[])
    parser.add_argument("--output", default=os.environ.get("TIJARA_FBR_FIXTURE_OUTPUT", ""))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_FBR_FIXTURE_NON_STRICT")))
    args = parser.parse_args()
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/fbr-fixture-smoke" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []
    fixtures = []
    response_count = 0
    accepted_count = 0
    rejected_count = 0

    for path in _fixture_paths(args.fixture):
        try:
            payload, responses = _load_fixture(path)
            provider = payload.get("provider") or "unknown"
            environment = payload.get("environment") or "sandbox"
            flagged_keys = _secret_like_keys(payload)
            fixture_hash = _hash_payload(payload)
            normalized_responses = [
                _normalized_response(entry, provider, environment, sequence)
                for sequence, entry in enumerate(responses, start=1)
            ]
            fixture_rows = []
            for normalized in normalized_responses:
                fixture_rows.extend(_validate_response(normalized))
                if normalized["expected_result"] == "accepted":
                    accepted_count += 1
                if normalized["expected_result"] == "rejected":
                    rejected_count += 1
            response_count += len(normalized_responses)
            if flagged_keys:
                fixture_rows.append(
                    _row(
                        "%s-secret-safety" % payload.get("profile", path.stem),
                        "failed",
                        "Secret-like keys are not allowed: %s" % ", ".join(flagged_keys),
                    )
                )
            else:
                fixture_rows.append(
                    _row(
                        "%s-secret-safety" % payload.get("profile", path.stem),
                        "passed",
                        "No secret-like keys found.",
                    )
                )
            rows.extend(fixture_rows)
            fixtures.append(
                {
                    "path": _repo_relative(path),
                    "provider": provider,
                    "environment": environment,
                    "profile": payload.get("profile") or path.stem,
                    "fixture_hash": fixture_hash,
                    "response_count": len(normalized_responses),
                    "responses": normalized_responses,
                }
            )
        except Exception as error:
            message = "%s: %s" % (_repo_relative(path), error)
            blockers.append(message)
            rows.append(_row("%s-load" % path.stem, "failed", message))

    if not fixtures:
        blockers.append("No FBR response fixtures were loaded.")
        rows.append(_row("fixture-count", "failed", "No FBR response fixtures were loaded."))
    else:
        rows.append(_row("fixture-count", "passed", "%s fixture(s) loaded." % len(fixtures)))
    if accepted_count == 0:
        blockers.append("At least one accepted FBR provider response fixture is required.")
        rows.append(_row("accepted-response-coverage", "failed", "No accepted response fixture found."))
    else:
        rows.append(_row("accepted-response-coverage", "passed", "%s accepted response(s) found." % accepted_count))
    if rejected_count == 0:
        warnings.append("No rejected FBR provider response fixture is attached.")
        rows.append(_row("rejected-response-coverage", "warning", "No rejected response fixture found."))
    else:
        rows.append(_row("rejected-response-coverage", "passed", "%s rejected response(s) found." % rejected_count))

    for row in rows:
        if row["status"] == "failed" and row["message"] not in blockers:
            blockers.append(row["message"])
        elif row["status"] == "warning" and row["message"] not in warnings:
            warnings.append(row["message"])

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
        "fixture_count": len(fixtures),
        "response_count": response_count,
        "accepted_response_count": accepted_count,
        "rejected_response_count": rejected_count,
        "fixtures": fixtures,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    providers = sorted({fixture["provider"] for fixture in fixtures})
    environments = sorted({fixture["environment"] for fixture in fixtures})
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "fixture_count=%s" % len(fixtures),
            "response_count=%s" % response_count,
            "accepted_response_count=%s" % accepted_count,
            "rejected_response_count=%s" % rejected_count,
            "providers=%s" % ",".join(providers),
            "environments=%s" % ",".join(environments),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "fbr-fixture-smoke.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("FBR fixture smoke evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
