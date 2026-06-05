#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
GROUP_ALIASES = {
    "release": "Release Candidate",
    "release candidate": "Release Candidate",
    "release-candidate": "Release Candidate",
    "rc": "Release Candidate",
    "browser": "Browser E2E",
    "browser e2e": "Browser E2E",
    "browser-e2e": "Browser E2E",
    "e2e": "Browser E2E",
    "playwright": "Browser E2E",
    "ops": "Operations",
    "operations": "Operations",
    "hardware": "Hardware",
    "fbr": "FBR",
    "psp": "PSP",
    "settlement": "PSP",
    "security": "Security",
    "general": "General",
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _git_value(args):
    try:
        import subprocess

        return (
            subprocess.check_output(args, cwd=ROOT_DIR, text=True, stderr=subprocess.DEVNULL)
            .strip()
        )
    except Exception:
        return "unknown"


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_evidence_files(paths):
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT_DIR / path
        if path.is_file():
            yield path
        elif path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file():
                    yield candidate


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _read_lines(path, limit=400):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = []
            for index, line in enumerate(handle):
                if index >= limit:
                    break
                lines.append(line.rstrip("\n"))
            return lines
    except OSError:
        return []


def _checklist(items):
    return "\n".join("- [ ] %s" % item for item in items)


def _signature_block():
    return """
## Sign-Off

- [ ] Approved
- [ ] Approved with exceptions
- [ ] Rejected

Reviewer name:

Reviewer role:

Reviewer organization:

Signature or approval reference:

Approval date:

Exceptions / follow-up actions:
"""


def _release_go_no_go(context):
    return f"""
# Release Go/No-Go

- Package ID: {context["run_id"]}
- Generated: {context["generated_at"]}
- Git branch: {context["git_branch"]}
- Git head: {context["git_head"]}
- Target environment: {context["target_environment"]}

## Required Evidence

{_checklist([
    "Release candidate gate summary reviewed.",
    "Staging browser E2E evidence reviewed.",
    "Staging operations evidence reviewed.",
    "Odoo transaction tests reviewed.",
    "Security audit baseline reviewed.",
    "Backup and restore evidence reviewed.",
    "Rollback plan reviewed.",
    "Known exceptions documented with owner and due date.",
])}

## Decision Checklist

{_checklist([
    "No unresolved P0/P1 functional defects.",
    "No unresolved critical/high security findings without approved exception.",
    "No unresolved data-loss or accounting integrity risk.",
    "Tenant provisioning and rollback instructions are current.",
    "Support, monitoring, and incident contacts are assigned.",
    "Finance/tax, PSP, FBR, and hardware sign-offs are attached or waived by owner.",
])}

{_signature_block()}
"""


def _psp_certification(context):
    return f"""
# PSP Certification Sign-Off

- Package ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Provider: JazzCash / Easypaisa / Stripe / Bank / Other

## Provider Contract and Credentials

{_checklist([
    "Provider contract or sandbox agreement is attached.",
    "Webhook URL registered with provider.",
    "Native signature secret configured in secret manager.",
    "Provider callback IP/rate-limit rules documented.",
    "Settlement file/API access enabled.",
])}

## Payment Flow Evidence

{_checklist([
    "Successful payment webhook payload captured.",
    "Failed payment webhook payload captured.",
    "Refund webhook or refund statement line captured.",
    "Chargeback/dispute payload or statement line captured.",
    "Native signature validation passes for valid payload.",
    "Native signature validation rejects invalid payload.",
    "Settlement import matches payment, fee, refund, and chargeback lines.",
    "Finance actions generate reviewed accounting entries or documents.",
])}

## Reconciliation and Finance

{_checklist([
    "Provider gross/fee/net totals match settlement batch.",
    "Bank payout amount reconciles to PSP clearing account.",
    "Refund and chargeback cases have evidence hashes.",
    "Dunning/suspension behavior reviewed for failed/refunded tenants.",
    "Finance posting policy signed by accounting owner.",
])}

{_signature_block()}
"""


def _fbr_certification(context):
    return f"""
# FBR Certification Sign-Off

- Package ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Certified provider:
- FBR POS ID:
- Branch code:

## Provider Setup

{_checklist([
    "Certified provider endpoint configured with HTTPS.",
    "Client ID and client secret configured in secret manager.",
    "Sandbox/UAT certification environment selected.",
    "Provider name, certification reference, and payload hash fields reviewed.",
    "FBR queue cron remains disabled until sandbox sign-off is complete.",
])}

## Invoice Submission Evidence

{_checklist([
    "Dry-run invoice queue submission passes.",
    "Sandbox/live adapter rejects missing endpoint or credentials.",
    "Sandbox submission returns provider invoice number.",
    "QR payload is generated and appears on receipt/invoice output.",
    "Signed payload hash and compliance status are stored.",
    "Failed submissions remain queued with actionable error text.",
    "Retry behavior is reviewed by tax/compliance owner.",
])}

## Compliance Decision

{_checklist([
    "Invoice schema reviewed against certified provider requirements.",
    "Tax fields, NTN, STRN, POS ID, and branch code reviewed.",
    "Receipt template reviewed for FBR invoice number and QR payload.",
    "Sandbox sign-off reference attached.",
    "Live cutover window and rollback plan approved.",
])}

{_signature_block()}
"""


def _hardware_certification(context):
    return f"""
# Hardware Certification Sign-Off

- Package ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Store / branch:
- Device type: Receipt printer / label printer / cash drawer / scanner / scale / customer display
- Manufacturer / model:
- Serial number:
- Driver / firmware:

## Physical Test Evidence

{_checklist([
    "Device is registered in Tijara hardware devices.",
    "Hardware bridge health check passes from the store network.",
    "Receipt print job succeeds with response code and bridge job ID.",
    "Cash drawer pulse succeeds where applicable.",
    "Scanner event capture succeeds where applicable.",
    "Scale reading succeeds where applicable.",
    "Customer display state update succeeds where applicable.",
    "ZPL/label output succeeds where applicable.",
    "Evidence attachments and observed serial are captured.",
    "Hardware certification evidence hash is refreshed.",
])}

## Operational Readiness

{_checklist([
    "Store fallback process is documented.",
    "Cashier/operator has signed the physical test.",
    "Network/firewall requirements are documented.",
    "Support contact and spare-device plan are documented.",
    "Known device limitations are listed.",
])}

{_signature_block()}
"""


def _finance_tax(context):
    return f"""
# Finance and Tax Sign-Off

- Package ID: {context["run_id"]}
- Target environment: {context["target_environment"]}

## Accounting Configuration

{_checklist([
    "PSP clearing account configured.",
    "Payment counterpart account configured.",
    "Provider fee expense account configured.",
    "Refund/credit-note account configured.",
    "Refund payment journal and outstanding account configured.",
    "Chargeback receivable and chargeback fee accounts configured.",
    "Write-off expense account configured.",
])}

## Review Evidence

{_checklist([
    "Settlement batch creates approved finance actions.",
    "Draft journal entries balance.",
    "Refund credit note workflow reviewed.",
    "Outbound refund payment workflow reviewed.",
    "Chargeback won/lost/write-off workflow reviewed.",
    "Month-end settlement close SOP reviewed.",
    "Tax treatment and invoice template reviewed.",
])}

{_signature_block()}
"""


def _security_review(context):
    return f"""
# Security Review Sign-Off

- Package ID: {context["run_id"]}
- Target environment: {context["target_environment"]}

## Baseline Evidence

{_checklist([
    "Security audit baseline passed.",
    "Dependency scan reviewed.",
    "Container/config scan reviewed.",
    "Secret files and committed config reviewed.",
    "Rate limiting and reverse proxy rules reviewed.",
    "RBAC and manager/user access reviewed.",
    "Audit logs for refunds, discounts, settlements, and disputes reviewed.",
    "Backup/restore evidence reviewed.",
])}

## Exception Handling

{_checklist([
    "Critical/high findings have no open unapproved exceptions.",
    "Approved exceptions include owner and due date.",
    "Incident contacts and escalation path are documented.",
    "Log retention and alert routing are documented.",
])}

{_signature_block()}
"""


def _normalize_group_name(name):
    cleaned = " ".join(str(name or "").replace("_", " ").split()).strip()
    return GROUP_ALIASES.get(cleaned.lower(), cleaned)


def _evidence_group(entry):
    relative = entry["relative_path"].replace("\\", "/")
    relative_lower = relative.lower()
    filename = Path(entry["path"]).name
    if "release-evidence/" in relative:
        return "Release Candidate"
    if "e2e-evidence/" in relative:
        return "Browser E2E"
    if (
        "ops-evidence/" in relative
        or "monitoring-evidence/" in relative
        or "monitoring" in relative_lower
        or "incident-runbook" in relative_lower
        or "load-evidence/" in relative
        or "load-evidence" in relative_lower
        or "load-profile-matrix" in relative_lower
        or "operations-release-bundle" in relative_lower
        or "release-retention-evidence" in relative_lower
        or "deployment-environment-evidence" in relative_lower
        or "deployment-environments" in relative_lower
        or "tenant-ops-evidence" in relative_lower
        or "tenant-rollout" in relative_lower
        or "tenant-smoke" in relative_lower
        or "tenant-ops" in relative_lower
        or "deploy/runtime/tenants/" in relative_lower
        or filename == "monitoring-evidence.json"
        or filename == "incident-runbook-evidence.json"
        or filename == "load-evidence.json"
        or filename == "load-profile-matrix.json"
        or filename == "operations-release-bundle.json"
        or filename == "release-retention-evidence.json"
        or filename == "deployment-environment-evidence.json"
        or filename == "tenant-ops-evidence.json"
        or filename == "tenant-rollout-evidence.json"
        or filename == "tenant-smoke-evidence.json"
        or filename == "ops-manifest.json"
    ):
        return "Operations"
    if "hardware" in relative_lower:
        return "Hardware"
    if (
        "secret-manager-evidence" in relative_lower
        or "secret-runtime-evidence" in relative_lower
        or filename == "secret-manager-evidence.json"
        or filename == "secret-runtime-evidence.json"
    ):
        return "Security"
    if "fbr" in relative_lower:
        return "FBR"
    if "psp" in relative_lower or "settlement" in relative_lower:
        return "PSP"
    if "security" in relative_lower:
        return "Security"
    return "General"


def _group_counts(evidence_entries):
    counts = {}
    for entry in evidence_entries:
        group = _evidence_group(entry)
        counts[group] = counts.get(group, 0) + 1
    return counts


def _summary_fields(lines):
    fields = {}
    wanted = {
        "Status",
        "Exit code",
        "Run ID",
        "Scope",
        "Base URL",
        "Evidence directory",
        "Started",
        "Finished",
    }
    for line in lines:
        text = line.strip()
        if not text.startswith("- "):
            continue
        label, separator, value = text[2:].partition(":")
        if separator and label in wanted:
            fields[label] = value.strip()
    return fields


def _status_counts(lines):
    counts = {}
    rows = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2 or parts[0] == "check":
            continue
        name, status = parts[0], parts[1]
        counts[status] = counts.get(status, 0) + 1
        message = parts[5] if len(parts) >= 6 else parts[4] if len(parts) >= 5 else parts[2] if len(parts) >= 3 else ""
        rows.append({"name": name, "status": status, "message": message})
    return counts, rows


def _environment_lines(lines):
    safe_lines = []
    for line in lines:
        if not line or "=" not in line:
            continue
        key = line.split("=", 1)[0].upper()
        if "PASSWORD" in key or "SECRET" in key or "TOKEN" in key:
            continue
        safe_lines.append(line)
    return safe_lines[:24]


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _psp_readiness_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "psp-readiness.json":
            continue
        payload = _read_json(path)
        provider_reviews = []
        for provider in payload.get("providers") or []:
            provider_reviews.append(
                {
                    "provider": provider.get("provider", ""),
                    "label": provider.get("label", ""),
                    "decision": provider.get("decision", ""),
                    "ci_status": provider.get("ci_status", ""),
                    "secret_present": bool((provider.get("signature") or {}).get("secret_present")),
                    "certification_required": bool(
                        (provider.get("certification") or {}).get("required")
                    ),
                    "certification_reference_present": bool(
                        (provider.get("certification") or {}).get("reference_present")
                    ),
                    "certification_status": (provider.get("certification") or {}).get("status", ""),
                    "settlement_parser_profile": (provider.get("contract") or {}).get(
                        "settlement_parser_profile",
                        "",
                    ),
                }
            )
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "require_native_signatures": bool(payload.get("require_native_signatures")),
                "providers": provider_reviews,
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _fbr_readiness_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "fbr-readiness.json":
            continue
        payload = _read_json(path)
        adapter = payload.get("adapter") or {}
        certification = payload.get("certification") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "adapter_mode": adapter.get("mode", ""),
                "provider_name_present": bool(adapter.get("provider_name_present")),
                "endpoint_present": bool(adapter.get("endpoint_present")),
                "endpoint_https": bool(adapter.get("endpoint_https")),
                "client_id_present": bool(adapter.get("client_id_present")),
                "credential_present": bool(
                    adapter.get("credential_reference_present")
                    or adapter.get("client_secret_present")
                ),
                "certification_environment": certification.get("environment", ""),
                "sandbox_reference_present": bool(certification.get("sandbox_reference_present")),
                "fbr_pos_id_present": bool(certification.get("fbr_pos_id_present")),
                "branch_code_present": bool(certification.get("branch_code_present")),
                "payload_hash_present": bool(certification.get("payload_hash_present")),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _fbr_fixture_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "fbr-fixture-smoke.json":
            continue
        payload = _read_json(path)
        fixtures = payload.get("fixtures") or []
        providers = sorted({fixture.get("provider", "") for fixture in fixtures if fixture.get("provider")})
        environments = sorted(
            {fixture.get("environment", "") for fixture in fixtures if fixture.get("environment")}
        )
        accepted_count = 0
        rejected_count = 0
        for fixture in fixtures:
            for response in fixture.get("responses") or []:
                expected = str(response.get("expected_result") or "").lower()
                if expected == "accepted":
                    accepted_count += 1
                elif expected == "rejected":
                    rejected_count += 1
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "fixture_count": payload.get("fixture_count", len(fixtures)),
                "response_count": payload.get("response_count", accepted_count + rejected_count),
                "accepted_response_count": payload.get("accepted_response_count", accepted_count),
                "rejected_response_count": payload.get("rejected_response_count", rejected_count),
                "providers": providers,
                "environments": environments,
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _monitoring_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "monitoring-evidence.json":
            continue
        payload = _read_json(path)
        refs = payload.get("evidence_refs") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "smoke_decision_attached": bool(refs.get("smoke_decision")),
                "tenant_smoke_attached": bool(refs.get("tenant_smoke_evidence")),
                "deployment_decision_attached": bool(refs.get("deployment_decision")),
                "rollback_decision_attached": bool(refs.get("rollback_decision")),
                "check_count": len(payload.get("checks") or []),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _incident_runbook_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "incident-runbook-evidence.json":
            continue
        payload = _read_json(path)
        owners = payload.get("owners") or {}
        refs = payload.get("references") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "owners": owners,
                "references": refs,
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _load_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "load-evidence.json":
            continue
        payload = _read_json(path)
        metrics = payload.get("metrics") or {}
        profile = payload.get("load_profile") or {}
        payload_context = payload.get("context") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "base_url": payload_context.get("base_url", ""),
                "profile_name": profile.get("profile_name", ""),
                "vus": profile.get("vus", ""),
                "duration": profile.get("duration", ""),
                "p95_ms": metrics.get("p95_ms"),
                "fail_rate": metrics.get("fail_rate"),
                "checks_rate": metrics.get("checks_rate"),
                "max_p95_ms": metrics.get("max_p95_ms"),
                "max_fail_rate": metrics.get("max_fail_rate"),
                "min_checks_rate": metrics.get("min_checks_rate"),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _load_matrix_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "load-profile-matrix.json":
            continue
        payload = _read_json(path)
        payload_context = payload.get("context") or {}
        profiles = payload.get("profiles") or []
        verticals = sorted(
            {
                vertical
                for profile in profiles
                for vertical in (profile.get("verticals") or [])
            }
        )
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "profile_count": payload.get("profile_count", len(profiles)),
                "verticals": verticals,
                "approved_by_present": bool(payload_context.get("approved_by")),
                "approval_reference_present": bool(payload_context.get("approval_reference")),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _operations_bundle_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "operations-release-bundle.json":
            continue
        payload = _read_json(path)
        payload_context = payload.get("context") or {}
        steps = payload.get("steps") or []
        status_counts = {}
        step_refs = {}
        for step in steps:
            status = step.get("status") or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
            step_refs[step.get("name") or step.get("label") or "unknown"] = bool(step.get("manifest"))
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "target_environment": payload_context.get("target_environment", ""),
                "strict": bool(payload_context.get("strict")),
                "fail_on_warning": bool(payload_context.get("fail_on_warning")),
                "step_count": len(steps),
                "status_counts": status_counts,
                "step_refs": step_refs,
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _release_retention_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "release-retention-evidence.json":
            continue
        payload = _read_json(path)
        artifact_store = payload.get("artifact_store") or {}
        secret_manager = payload.get("secret_manager") or {}
        evidence = payload.get("evidence") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "artifact_store_reference_present": bool(artifact_store.get("reference_present")),
                "artifact_policy_reference_present": bool(
                    artifact_store.get("retention_policy_reference_present")
                ),
                "certification_policy_reference_present": bool(
                    artifact_store.get("certification_policy_reference_present")
                ),
                "secret_manager_provider_present": bool(secret_manager.get("provider_present")),
                "secret_manager_provider": secret_manager.get("provider", ""),
                "secret_manager_reference_present": bool(secret_manager.get("reference_present")),
                "secret_rotation_policy_reference_present": bool(
                    secret_manager.get("rotation_policy_reference_present")
                ),
                "retention_days": payload.get("retention_days") or {},
                "minimum_retention_days": payload.get("minimum_retention_days") or {},
                "evidence_file_count": evidence.get("file_count", 0),
                "evidence_total_bytes": evidence.get("total_bytes", 0),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _secret_manager_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "secret-manager-evidence.json":
            continue
        payload = _read_json(path)
        secret_manager = payload.get("secret_manager") or {}
        non_secret_templates = payload.get("non_secret_templates") or []
        secret_examples = payload.get("secret_example_templates") or []
        compose_guardrails = payload.get("compose_guardrails") or []
        startup_guardrails = payload.get("startup_guardrails") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "secret_manager_provider_present": bool(secret_manager.get("provider_present")),
                "secret_manager_provider": secret_manager.get("provider", ""),
                "secret_manager_reference_present": bool(secret_manager.get("reference_present")),
                "secret_rotation_policy_reference_present": bool(
                    secret_manager.get("rotation_policy_reference_present")
                ),
                "secret_access_review_reference_present": bool(
                    secret_manager.get("access_review_reference_present")
                ),
                "required_secret_count": len(payload.get("required_secrets") or []),
                "non_secret_template_count": len(non_secret_templates),
                "secret_example_template_count": len(secret_examples),
                "compose_guarded_count": sum(1 for item in compose_guardrails if item.get("guarded")),
                "compose_guardrail_count": len(compose_guardrails),
                "startup_requires_db_password": bool(
                    startup_guardrails.get("requires_odoo_db_password")
                ),
                "startup_requires_master_password": bool(
                    startup_guardrails.get("requires_odoo_master_password")
                ),
                "startup_refuses_placeholders": bool(
                    startup_guardrails.get("refuses_production_placeholders")
                ),
                "real_secret_file_count": len(payload.get("real_secret_files") or []),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _secret_runtime_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "secret-runtime-evidence.json":
            continue
        payload = _read_json(path)
        secret_manager = payload.get("secret_manager") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "secret_manager_provider_present": bool(secret_manager.get("provider_present")),
                "secret_manager_provider": secret_manager.get("provider", ""),
                "secret_manager_reference_present": bool(secret_manager.get("reference_present")),
                "secret_access_review_reference_present": bool(
                    secret_manager.get("access_review_reference_present")
                ),
                "minimum_probes": payload.get("minimum_probes", 0),
                "probe_count": payload.get("probe_count", 0),
                "resolved_probe_count": payload.get("resolved_probe_count", 0),
                "unresolved_probe_count": payload.get("unresolved_probe_count", 0),
                "expected_secret_count": len(payload.get("expected_secrets") or []),
                "sources": sorted({probe.get("source", "") for probe in payload.get("probes") or [] if probe.get("source")}),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _deployment_environment_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "deployment-environment-evidence.json":
            continue
        payload = _read_json(path)
        environment = payload.get("environment") or {}
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "target_environment": (payload.get("context") or {}).get("target_environment", ""),
                "platform": environment.get("platform", ""),
                "environment_name": environment.get("name", ""),
                "branch_policy_ref_present": bool(environment.get("branch_policy_ref_present")),
                "approver_group_ref_present": bool(environment.get("approver_group_ref_present")),
                "minimum_approvers": environment.get("minimum_approvers", 0),
                "approver_count": environment.get("approver_count", 0),
                "promotion_runbook_ref_present": bool(environment.get("promotion_runbook_ref_present")),
                "rollback_runbook_ref_present": bool(environment.get("rollback_runbook_ref_present")),
                "deployment_gate_ref_present": bool(environment.get("deployment_gate_ref_present")),
                "incident_runbook_ref_present": bool(environment.get("incident_runbook_ref_present")),
                "backup_policy_ref_present": bool(environment.get("backup_policy_ref_present")),
                "monitoring_ref_present": bool(environment.get("monitoring_ref_present")),
                "change_ticket_ref_present": bool(environment.get("change_ticket_ref_present")),
                "freeze_window_ref_present": bool(environment.get("freeze_window_ref_present")),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _tenant_ops_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "tenant-ops-evidence.json":
            continue
        payload = _read_json(path)
        context = payload.get("context") or {}
        tenant_reviews = []
        for tenant in payload.get("tenants") or []:
            tenant_reviews.append(
                {
                    "tenant_db": tenant.get("tenant_db", ""),
                    "domain": tenant.get("domain", ""),
                    "decision": tenant.get("decision", ""),
                    "ci_status": tenant.get("ci_status", ""),
                    "dns_provider": tenant.get("dns_provider", ""),
                    "dns_target_present": bool(tenant.get("dns_target_present")),
                    "ingress_host_present": bool(tenant.get("ingress_host_present")),
                    "tls_secret_present": bool(tenant.get("tls_secret_present")),
                    "admin_email_present": bool(tenant.get("admin_email_present")),
                    "backup_policy": tenant.get("backup_policy", ""),
                    "backup_retention_days": tenant.get("backup_retention_days", 0),
                    "restore_drill_reference_present": bool(
                        tenant.get("restore_drill_reference_present")
                    ),
                    "monitoring_enabled": bool(tenant.get("monitoring_enabled")),
                    "monitoring_blackbox_url_present": bool(
                        tenant.get("monitoring_blackbox_url_present")
                    ),
                    "smoke_check_count": tenant.get("smoke_check_count", 0),
                    "artifact_count": tenant.get("artifact_count", 0),
                    "expected_artifact_count": tenant.get("expected_artifact_count", 0),
                    "missing_artifacts": tenant.get("missing_artifacts") or [],
                    "blockers": tenant.get("blockers") or [],
                    "warnings": tenant.get("warnings") or [],
                }
            )
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "target_environment": context.get("target_environment", ""),
                "strict": bool(context.get("strict")),
                "tenant_count": context.get("tenant_count", len(tenant_reviews)),
                "minimum_tenants": context.get("minimum_tenants", 0),
                "requirements": payload.get("requirements") or {},
                "tenants": tenant_reviews,
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _tenant_smoke_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "tenant-smoke-evidence.json":
            continue
        payload = _read_json(path)
        context = payload.get("context") or {}
        tenant_reviews = []
        for tenant in payload.get("tenants") or []:
            tenant_reviews.append(
                {
                    "tenant_db": tenant.get("tenant_db", ""),
                    "domain": tenant.get("domain", ""),
                    "base_url": tenant.get("base_url", ""),
                    "decision": tenant.get("decision", ""),
                    "ci_status": tenant.get("ci_status", ""),
                    "check_count": tenant.get("check_count", 0),
                    "passed_count": tenant.get("passed_count", 0),
                    "failed_count": tenant.get("failed_count", 0),
                    "smoke_check_count": tenant.get("smoke_check_count", 0),
                    "dbfilter_header_used": bool(tenant.get("dbfilter_header_used")),
                    "blockers": tenant.get("blockers") or [],
                    "warnings": tenant.get("warnings") or [],
                }
            )
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "target_environment": context.get("target_environment", ""),
                "strict": bool(context.get("strict")),
                "tenant_count": context.get("tenant_count", len(tenant_reviews)),
                "minimum_tenants": context.get("minimum_tenants", 0),
                "minimum_routes_per_tenant": context.get("minimum_routes_per_tenant", 0),
                "requirements": payload.get("requirements") or {},
                "tenants": tenant_reviews,
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _tenant_rollout_reviews(evidence_entries):
    reviews = []
    for entry in evidence_entries:
        path = Path(entry["path"])
        if path.name != "tenant-rollout-evidence.json":
            continue
        payload = _read_json(path)
        context = payload.get("context") or {}
        tenant_reviews = []
        for tenant in payload.get("tenants") or []:
            action_statuses = {}
            for action in tenant.get("actions") or []:
                status = action.get("status", "") or "unknown"
                action_statuses[status] = action_statuses.get(status, 0) + 1
            tenant_reviews.append(
                {
                    "tenant_db": tenant.get("tenant_db", ""),
                    "domain": tenant.get("domain", ""),
                    "decision": tenant.get("decision", ""),
                    "ci_status": tenant.get("ci_status", ""),
                    "dry_run_count": tenant.get("dry_run_count", action_statuses.get("dry-run", 0)),
                    "executed_count": tenant.get("executed_count", action_statuses.get("executed", 0)),
                    "failed_count": tenant.get("failed_count", action_statuses.get("failed", 0)),
                    "rollback_action_count": tenant.get("rollback_action_count", 0),
                    "action_statuses": action_statuses,
                    "blockers": tenant.get("blockers") or [],
                    "warnings": tenant.get("warnings") or [],
                }
            )
        reviews.append(
            {
                "path": entry["relative_path"],
                "decision": payload.get("decision", ""),
                "ci_status": payload.get("ci_status", ""),
                "target_environment": context.get("target_environment", ""),
                "platform": context.get("platform") or context.get("provider", ""),
                "strict": bool(context.get("strict")),
                "execute": bool(context.get("execute")),
                "require_all_artifacts": bool(context.get("require_all_artifacts")),
                "tenant_count": context.get("tenant_count", len(tenant_reviews)),
                "minimum_tenants": context.get("minimum_tenants", 0),
                "tenants": tenant_reviews,
                "action_count": len(payload.get("actions") or []),
                "rollback_action_count": payload.get("rollback_action_count", 0),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            }
        )
    return reviews


def _evidence_summary(context, evidence_entries):
    by_group = _group_counts(evidence_entries)
    summary_blocks = []
    status_blocks = []
    environment_blocks = []
    psp_readiness_reviews = _psp_readiness_reviews(evidence_entries)
    fbr_readiness_reviews = _fbr_readiness_reviews(evidence_entries)
    fbr_fixture_reviews = _fbr_fixture_reviews(evidence_entries)
    monitoring_reviews = _monitoring_reviews(evidence_entries)
    incident_runbook_reviews = _incident_runbook_reviews(evidence_entries)
    load_reviews = _load_reviews(evidence_entries)
    load_matrix_reviews = _load_matrix_reviews(evidence_entries)
    operations_bundle_reviews = _operations_bundle_reviews(evidence_entries)
    release_retention_reviews = _release_retention_reviews(evidence_entries)
    secret_manager_reviews = _secret_manager_reviews(evidence_entries)
    secret_runtime_reviews = _secret_runtime_reviews(evidence_entries)
    deployment_environment_reviews = _deployment_environment_reviews(evidence_entries)
    tenant_ops_reviews = _tenant_ops_reviews(evidence_entries)
    tenant_smoke_reviews = _tenant_smoke_reviews(evidence_entries)
    tenant_rollout_reviews = _tenant_rollout_reviews(evidence_entries)

    for entry in evidence_entries:
        path = Path(entry["path"])
        name = path.name
        lines = _read_lines(path)
        if name == "summary.md":
            fields = _summary_fields(lines)
            summary_blocks.append((entry, fields))
        elif name == "status.tsv":
            counts, rows = _status_counts(lines)
            status_blocks.append((entry, counts, rows))
        elif name == "env-summary.txt":
            safe_lines = _environment_lines(lines)
            environment_blocks.append((entry, safe_lines))

    group_lines = "\n".join(
        "- %s: %s file(s)" % (group, count) for group, count in sorted(by_group.items())
    )
    if not group_lines:
        group_lines = "- No evidence files were attached by this generator run."

    required_groups = context.get("required_evidence_groups") or []
    missing_groups = context.get("missing_evidence_groups") or []
    if required_groups:
        required_lines = [
            "- Mode: %s" % ("strict" if context.get("strict_required_evidence") else "warn"),
            "- Required groups: %s" % ", ".join(required_groups),
            "- Missing groups: %s" % (", ".join(missing_groups) if missing_groups else "none"),
        ]
    else:
        required_lines = ["- No required evidence groups configured for this run."]

    summary_lines = []
    for entry, fields in summary_blocks:
        summary_lines.append("### `%s`" % entry["relative_path"])
        if fields:
            for label in sorted(fields):
                summary_lines.append("- %s: %s" % (label, fields[label]))
        else:
            summary_lines.append("- No structured summary fields were found.")
        summary_lines.append("")
    if not summary_lines:
        summary_lines = ["- No `summary.md` files were attached.", ""]

    status_lines = []
    for entry, counts, rows in status_blocks:
        count_text = ", ".join("%s=%s" % (status, count) for status, count in sorted(counts.items()))
        status_lines.append("### `%s`" % entry["relative_path"])
        status_lines.append("- Counts: %s" % (count_text or "none"))
        for row in rows[:20]:
            message = " - %s" % row["message"] if row["message"] else ""
            status_lines.append("- `%s`: %s%s" % (row["name"], row["status"], message))
        status_lines.append("")
    if not status_lines:
        status_lines = ["- No `status.tsv` files were attached.", ""]

    env_lines = []
    for entry, safe_lines in environment_blocks:
        env_lines.append("### `%s`" % entry["relative_path"])
        if safe_lines:
            env_lines.extend("- `%s`" % line for line in safe_lines)
        else:
            env_lines.append("- No non-secret environment lines were found.")
        env_lines.append("")
    if not env_lines:
        env_lines = ["- No `env-summary.txt` files were attached.", ""]

    psp_lines = []
    for review in psp_readiness_reviews:
        psp_lines.append("### `%s`" % review["path"])
        psp_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        psp_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        psp_lines.append(
            "- Native signatures required: %s"
            % ("yes" if review["require_native_signatures"] else "no")
        )
        for provider in review["providers"]:
            psp_lines.append(
                "- `%s`: decision=%s, secret_present=%s, certification=%s/%s, parser=%s"
                % (
                    provider["provider"],
                    provider["decision"] or "unknown",
                    "yes" if provider["secret_present"] else "no",
                    "yes" if provider["certification_reference_present"] else "no",
                    provider["certification_status"] or "unset",
                    provider["settlement_parser_profile"] or "unset",
                )
            )
        psp_lines.append("")
    if not psp_lines:
        psp_lines = ["- No `psp-readiness.json` files were attached.", ""]

    fbr_lines = []
    for review in fbr_readiness_reviews:
        fbr_lines.append("### `%s`" % review["path"])
        fbr_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        fbr_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        fbr_lines.append("- Adapter mode: %s" % (review["adapter_mode"] or "unknown"))
        fbr_lines.append(
            "- Provider/endpoint/client/credential: %s/%s/%s/%s"
            % (
                "yes" if review["provider_name_present"] else "no",
                "https" if review["endpoint_https"] else "no",
                "yes" if review["client_id_present"] else "no",
                "yes" if review["credential_present"] else "no",
            )
        )
        fbr_lines.append(
            "- Certification: environment=%s, reference=%s, pos_id=%s, branch=%s, payload_hash=%s"
            % (
                review["certification_environment"] or "unset",
                "yes" if review["sandbox_reference_present"] else "no",
                "yes" if review["fbr_pos_id_present"] else "no",
                "yes" if review["branch_code_present"] else "no",
                "yes" if review["payload_hash_present"] else "no",
            )
        )
        fbr_lines.append("")
    if not fbr_lines:
        fbr_lines = ["- No `fbr-readiness.json` files were attached.", ""]

    fbr_fixture_lines = []
    for review in fbr_fixture_reviews:
        fbr_fixture_lines.append("### `%s`" % review["path"])
        fbr_fixture_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        fbr_fixture_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        fbr_fixture_lines.append(
            "- Fixtures/responses: %s/%s"
            % (review["fixture_count"], review["response_count"])
        )
        fbr_fixture_lines.append(
            "- Accepted/rejected responses: %s/%s"
            % (review["accepted_response_count"], review["rejected_response_count"])
        )
        fbr_fixture_lines.append(
            "- Providers/environments: %s/%s"
            % (
                ", ".join(review["providers"]) or "unset",
                ", ".join(review["environments"]) or "unset",
            )
        )
        fbr_fixture_lines.append("")
    if not fbr_fixture_lines:
        fbr_fixture_lines = ["- No `fbr-fixture-smoke.json` files were attached.", ""]

    monitoring_lines = []
    for review in monitoring_reviews:
        monitoring_lines.append("### `%s`" % review["path"])
        monitoring_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        monitoring_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        monitoring_lines.append(
            "- Smoke/tenant-smoke/deployment/rollback refs: %s/%s/%s/%s"
            % (
                "yes" if review["smoke_decision_attached"] else "no",
                "yes" if review["tenant_smoke_attached"] else "no",
                "yes" if review["deployment_decision_attached"] else "no",
                "yes" if review["rollback_decision_attached"] else "no",
            )
        )
        monitoring_lines.append("- Check count: %s" % review["check_count"])
        monitoring_lines.append("")
    if not monitoring_lines:
        monitoring_lines = ["- No `monitoring-evidence.json` files were attached.", ""]

    incident_lines = []
    for review in incident_runbook_reviews:
        owners = review["owners"]
        refs = review["references"]
        incident_lines.append("### `%s`" % review["path"])
        incident_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        incident_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        incident_lines.append(
            "- Owners release/devops/support/business/oncall: %s/%s/%s/%s/%s"
            % (
                "yes" if owners.get("release_owner_present") else "no",
                "yes" if owners.get("devops_owner_present") else "no",
                "yes" if owners.get("support_owner_present") else "no",
                "yes" if owners.get("business_owner_present") else "no",
                "yes" if owners.get("oncall_contact_present") else "no",
            )
        )
        incident_lines.append(
            "- References alert/runbook/backup/restore/rollback/monitoring: %s/%s/%s/%s/%s/%s"
            % (
                "yes" if refs.get("alert_route_present") else "no",
                "yes" if refs.get("runbook_url_present") else "no",
                "yes" if refs.get("backup_reference_present") else "no",
                "yes" if refs.get("restore_drill_reference_present") else "no",
                "yes" if refs.get("rollback_reference_present") else "no",
                "yes" if refs.get("monitoring_reference_present") else "no",
            )
        )
        incident_lines.append("")
    if not incident_lines:
        incident_lines = ["- No `incident-runbook-evidence.json` files were attached.", ""]

    load_lines = []
    for review in load_reviews:
        load_lines.append("### `%s`" % review["path"])
        load_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        load_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        load_lines.append(
            "- Profile: name=%s, vus=%s, duration=%s, base_url=%s"
            % (
                review["profile_name"] or "unset",
                review["vus"] or "unset",
                review["duration"] or "unset",
                review["base_url"] or "unset",
            )
        )
        load_lines.append(
            "- Metrics: p95=%s/%s ms, fail_rate=%s/%s, checks_rate=%s/%s"
            % (
                review["p95_ms"],
                review["max_p95_ms"],
                review["fail_rate"],
                review["max_fail_rate"],
                review["checks_rate"],
                review["min_checks_rate"],
            )
        )
        load_lines.append("")
    if not load_lines:
        load_lines = ["- No `load-evidence.json` files were attached.", ""]

    load_matrix_lines = []
    for review in load_matrix_reviews:
        load_matrix_lines.append("### `%s`" % review["path"])
        load_matrix_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        load_matrix_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        load_matrix_lines.append("- Profile count: %s" % review["profile_count"])
        load_matrix_lines.append("- Verticals: %s" % (", ".join(review["verticals"]) or "unset"))
        load_matrix_lines.append(
            "- Approval owner/reference: %s/%s"
            % (
                "yes" if review["approved_by_present"] else "no",
                "yes" if review["approval_reference_present"] else "no",
            )
        )
        load_matrix_lines.append("")
    if not load_matrix_lines:
        load_matrix_lines = ["- No `load-profile-matrix.json` files were attached.", ""]

    operations_bundle_lines = []
    for review in operations_bundle_reviews:
        counts = ", ".join(
            "%s=%s" % (status, count)
            for status, count in sorted((review["status_counts"] or {}).items())
        )
        refs = review["step_refs"] or {}
        operations_bundle_lines.append("### `%s`" % review["path"])
        operations_bundle_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        operations_bundle_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        operations_bundle_lines.append(
            "- Target/strict/fail-on-warning: %s/%s/%s"
            % (
                review["target_environment"] or "unset",
                "yes" if review["strict"] else "no",
                "yes" if review["fail_on_warning"] else "no",
            )
        )
        operations_bundle_lines.append("- Step count/statuses: %s/%s" % (review["step_count"], counts or "none"))
        operations_bundle_lines.append(
            "- Evidence refs load-matrix/load-enterprise/smoke/tenant-smoke/monitoring/incident/retention: %s/%s/%s/%s/%s/%s/%s"
            % (
                "yes" if refs.get("load-matrix") else "no",
                "yes" if refs.get("load-enterprise") else "no",
                "yes" if refs.get("smoke") else "no",
                "yes" if refs.get("tenant-smoke") else "no",
                "yes" if refs.get("monitoring") else "no",
                "yes" if refs.get("incident") else "no",
                "yes" if refs.get("retention") else "no",
            )
        )
        operations_bundle_lines.append("")
    if not operations_bundle_lines:
        operations_bundle_lines = ["- No `operations-release-bundle.json` files were attached.", ""]

    release_retention_lines = []
    for review in release_retention_reviews:
        retention_days = review["retention_days"] or {}
        release_retention_lines.append("### `%s`" % review["path"])
        release_retention_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        release_retention_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        release_retention_lines.append(
            "- Artifact store/policies: %s/%s/%s"
            % (
                "yes" if review["artifact_store_reference_present"] else "no",
                "yes" if review["artifact_policy_reference_present"] else "no",
                "yes" if review["certification_policy_reference_present"] else "no",
            )
        )
        release_retention_lines.append(
            "- Secret manager/provider/rotation: %s/%s/%s"
            % (
                review["secret_manager_provider"] or (
                    "yes" if review["secret_manager_provider_present"] else "no"
                ),
                "yes" if review["secret_manager_reference_present"] else "no",
                "yes" if review["secret_rotation_policy_reference_present"] else "no",
            )
        )
        release_retention_lines.append(
            "- Retention days ci/release/cert/logs/backups: %s/%s/%s/%s/%s"
            % (
                retention_days.get("ci-artifacts", "unset"),
                retention_days.get("release-evidence", "unset"),
                retention_days.get("certification-evidence", "unset"),
                retention_days.get("logs", "unset"),
                retention_days.get("backups", "unset"),
            )
        )
        release_retention_lines.append(
            "- Evidence fingerprints: %s file(s), %s byte(s)"
            % (review["evidence_file_count"], review["evidence_total_bytes"])
        )
        release_retention_lines.append("")
    if not release_retention_lines:
        release_retention_lines = ["- No `release-retention-evidence.json` files were attached.", ""]

    secret_manager_lines = []
    for review in secret_manager_reviews:
        secret_manager_lines.append("### `%s`" % review["path"])
        secret_manager_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        secret_manager_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        secret_manager_lines.append(
            "- Secret manager/provider/reference/rotation/access review: %s/%s/%s/%s"
            % (
                review["secret_manager_provider"] or (
                    "yes" if review["secret_manager_provider_present"] else "no"
                ),
                "yes" if review["secret_manager_reference_present"] else "no",
                "yes" if review["secret_rotation_policy_reference_present"] else "no",
                "yes" if review["secret_access_review_reference_present"] else "no",
            )
        )
        secret_manager_lines.append(
            "- Templates required/non-secret/secret-example: %s/%s/%s"
            % (
                review["required_secret_count"],
                review["non_secret_template_count"],
                review["secret_example_template_count"],
            )
        )
        secret_manager_lines.append(
            "- Guardrails compose/db/master/placeholders/real-secret-files: %s/%s/%s/%s/%s"
            % (
                "%s of %s" % (review["compose_guarded_count"], review["compose_guardrail_count"]),
                "yes" if review["startup_requires_db_password"] else "no",
                "yes" if review["startup_requires_master_password"] else "no",
                "yes" if review["startup_refuses_placeholders"] else "no",
                review["real_secret_file_count"],
            )
        )
        secret_manager_lines.append("")
    if not secret_manager_lines:
        secret_manager_lines = ["- No `secret-manager-evidence.json` files were attached.", ""]

    secret_runtime_lines = []
    for review in secret_runtime_reviews:
        secret_runtime_lines.append("### `%s`" % review["path"])
        secret_runtime_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        secret_runtime_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        secret_runtime_lines.append(
            "- Secret manager/provider/reference/access review: %s/%s/%s"
            % (
                review["secret_manager_provider"] or (
                    "yes" if review["secret_manager_provider_present"] else "no"
                ),
                "yes" if review["secret_manager_reference_present"] else "no",
                "yes" if review["secret_access_review_reference_present"] else "no",
            )
        )
        secret_runtime_lines.append(
            "- Probes resolved/total/minimum/unresolved: %s/%s/%s/%s"
            % (
                review["resolved_probe_count"],
                review["probe_count"],
                review["minimum_probes"],
                review["unresolved_probe_count"],
            )
        )
        secret_runtime_lines.append(
            "- Sources/expected secrets: %s/%s"
            % (", ".join(review["sources"]) or "unset", review["expected_secret_count"])
        )
        secret_runtime_lines.append("")
    if not secret_runtime_lines:
        secret_runtime_lines = ["- No `secret-runtime-evidence.json` files were attached.", ""]

    tenant_ops_lines = []
    for review in tenant_ops_reviews:
        tenant_ops_lines.append("### `%s`" % review["path"])
        tenant_ops_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        tenant_ops_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        tenant_ops_lines.append(
            "- Target/strict/tenants/minimum: %s/%s/%s/%s"
            % (
                review["target_environment"] or "unset",
                "yes" if review["strict"] else "no",
                review["tenant_count"],
                review["minimum_tenants"],
            )
        )
        for tenant in review["tenants"]:
            tenant_ops_lines.append(
                "- `%s`: decision=%s, domain=%s, artifacts=%s/%s, dns/ingress/admin/backup/monitoring=%s/%s/%s/%s/%s, missing=%s"
                % (
                    tenant["tenant_db"] or "unknown",
                    tenant["decision"] or "unknown",
                    tenant["domain"] or "unset",
                    tenant["artifact_count"],
                    tenant["expected_artifact_count"],
                    tenant["dns_provider"] or ("yes" if tenant["dns_target_present"] else "no"),
                    "yes" if tenant["ingress_host_present"] and tenant["tls_secret_present"] else "no",
                    "yes" if tenant["admin_email_present"] else "no",
                    "%s/%s" % (
                        tenant["backup_policy"] or "unset",
                        tenant["backup_retention_days"] or "unset",
                    ),
                    "yes" if tenant["monitoring_enabled"] and tenant["monitoring_blackbox_url_present"] else "no",
                    ", ".join(tenant["missing_artifacts"]) or "none",
                )
            )
        tenant_ops_lines.append("")
    if not tenant_ops_lines:
        tenant_ops_lines = ["- No `tenant-ops-evidence.json` files were attached.", ""]

    tenant_smoke_lines = []
    for review in tenant_smoke_reviews:
        tenant_smoke_lines.append("### `%s`" % review["path"])
        tenant_smoke_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        tenant_smoke_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        tenant_smoke_lines.append(
            "- Target/strict/tenants/minimum/routes-minimum: %s/%s/%s/%s/%s"
            % (
                review["target_environment"] or "unset",
                "yes" if review["strict"] else "no",
                review["tenant_count"],
                review["minimum_tenants"],
                review["minimum_routes_per_tenant"],
            )
        )
        for tenant in review["tenants"]:
            tenant_smoke_lines.append(
                "- `%s`: decision=%s, domain=%s, passed/failed/checks=%s/%s/%s, checklist=%s, dbfilter=%s"
                % (
                    tenant["tenant_db"] or "unknown",
                    tenant["decision"] or "unknown",
                    tenant["domain"] or "unset",
                    tenant["passed_count"],
                    tenant["failed_count"],
                    tenant["check_count"],
                    tenant["smoke_check_count"],
                    "yes" if tenant["dbfilter_header_used"] else "no",
                )
            )
        tenant_smoke_lines.append("")
    if not tenant_smoke_lines:
        tenant_smoke_lines = ["- No `tenant-smoke-evidence.json` files were attached.", ""]

    tenant_rollout_lines = []
    for review in tenant_rollout_reviews:
        tenant_rollout_lines.append("### `%s`" % review["path"])
        tenant_rollout_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        tenant_rollout_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        tenant_rollout_lines.append(
            "- Target/platform/strict/execute/tenants/minimum/actions/rollback-actions: %s/%s/%s/%s/%s/%s/%s/%s"
            % (
                review["target_environment"] or "unset",
                review["platform"] or "unset",
                "yes" if review["strict"] else "no",
                "yes" if review["execute"] else "no",
                review["tenant_count"],
                review["minimum_tenants"],
                review["action_count"],
                review["rollback_action_count"],
            )
        )
        for tenant in review["tenants"]:
            tenant_rollout_lines.append(
                "- `%s`: decision=%s, domain=%s, dry-run/executed/failed=%s/%s/%s, rollback-actions=%s"
                % (
                    tenant["tenant_db"] or "unknown",
                    tenant["decision"] or "unknown",
                    tenant["domain"] or "unset",
                    tenant["dry_run_count"],
                    tenant["executed_count"],
                    tenant["failed_count"],
                    tenant["rollback_action_count"],
                )
            )
        tenant_rollout_lines.append("")
    if not tenant_rollout_lines:
        tenant_rollout_lines = ["- No `tenant-rollout-evidence.json` files were attached.", ""]

    deployment_environment_lines = []
    for review in deployment_environment_reviews:
        deployment_environment_lines.append("### `%s`" % review["path"])
        deployment_environment_lines.append("- Decision: %s" % (review["decision"] or "unknown"))
        deployment_environment_lines.append("- CI status: %s" % (review["ci_status"] or "unknown"))
        deployment_environment_lines.append(
            "- Environment/platform/name: %s/%s/%s"
            % (
                review["target_environment"] or "unset",
                review["platform"] or "unset",
                review["environment_name"] or "unset",
            )
        )
        deployment_environment_lines.append(
            "- Policy/approvers: branch=%s, group=%s, approvers=%s/%s"
            % (
                "yes" if review["branch_policy_ref_present"] else "no",
                "yes" if review["approver_group_ref_present"] else "no",
                review["approver_count"],
                review["minimum_approvers"],
            )
        )
        deployment_environment_lines.append(
            "- Runbooks promotion/rollback/gate/incident/backup/monitoring/change/window: %s/%s/%s/%s/%s/%s/%s/%s"
            % (
                "yes" if review["promotion_runbook_ref_present"] else "no",
                "yes" if review["rollback_runbook_ref_present"] else "no",
                "yes" if review["deployment_gate_ref_present"] else "no",
                "yes" if review["incident_runbook_ref_present"] else "no",
                "yes" if review["backup_policy_ref_present"] else "no",
                "yes" if review["monitoring_ref_present"] else "no",
                "yes" if review["change_ticket_ref_present"] else "no",
                "yes" if review["freeze_window_ref_present"] else "no",
            )
        )
        deployment_environment_lines.append("")
    if not deployment_environment_lines:
        deployment_environment_lines = ["- No `deployment-environment-evidence.json` files were attached.", ""]

    return f"""
# Evidence Summary

- Package ID: {context["run_id"]}
- Generated: {context["generated_at"]}
- Target environment: {context["target_environment"]}

## Evidence Groups

{group_lines}

## Required Evidence Guardrails

{chr(10).join(required_lines)}

## Run Summaries

{chr(10).join(summary_lines)}
## Check Status Tables

{chr(10).join(status_lines)}
## Environment Snapshots

{chr(10).join(env_lines)}
## PSP Readiness Evidence

{chr(10).join(psp_lines)}
## FBR Readiness Evidence

{chr(10).join(fbr_lines)}
## FBR Fixture Evidence

{chr(10).join(fbr_fixture_lines)}
## Monitoring Evidence

{chr(10).join(monitoring_lines)}
## Incident Runbook Evidence

{chr(10).join(incident_lines)}
## Load Test Evidence

{chr(10).join(load_lines)}
## Load Profile Matrix Evidence

{chr(10).join(load_matrix_lines)}
## Operations Release Bundle Evidence

{chr(10).join(operations_bundle_lines)}
## Release Retention Evidence

{chr(10).join(release_retention_lines)}
## Secret Manager Evidence

{chr(10).join(secret_manager_lines)}
## Secret Runtime Evidence

{chr(10).join(secret_runtime_lines)}
## Tenant Operations Evidence

{chr(10).join(tenant_ops_lines)}
## Tenant Smoke Evidence

{chr(10).join(tenant_smoke_lines)}
## Tenant Rollout Evidence

{chr(10).join(tenant_rollout_lines)}
## Deployment Environment Evidence

{chr(10).join(deployment_environment_lines)}
## Approver Focus

{_checklist([
    "Every attached summary has a passing or approved-exception status.",
    "Every failed/skipped check has an owner, business impact, and due date.",
    "Browser E2E evidence includes the enterprise POS journey result.",
    "Operations evidence includes monitoring, load, dependency, restore, and container decisions.",
    "Release evidence links back to the git head and staging environment under review.",
    "No secret values are copied into this package.",
])}
"""


def _release_readiness(context, evidence_entries, group_counts):
    summary_reviews = []
    check_rows = []
    psp_readiness_reviews = _psp_readiness_reviews(evidence_entries)
    fbr_readiness_reviews = _fbr_readiness_reviews(evidence_entries)
    fbr_fixture_reviews = _fbr_fixture_reviews(evidence_entries)
    monitoring_reviews = _monitoring_reviews(evidence_entries)
    incident_runbook_reviews = _incident_runbook_reviews(evidence_entries)
    load_reviews = _load_reviews(evidence_entries)
    load_matrix_reviews = _load_matrix_reviews(evidence_entries)
    operations_bundle_reviews = _operations_bundle_reviews(evidence_entries)
    release_retention_reviews = _release_retention_reviews(evidence_entries)
    secret_manager_reviews = _secret_manager_reviews(evidence_entries)
    secret_runtime_reviews = _secret_runtime_reviews(evidence_entries)
    deployment_environment_reviews = _deployment_environment_reviews(evidence_entries)
    tenant_ops_reviews = _tenant_ops_reviews(evidence_entries)
    tenant_smoke_reviews = _tenant_smoke_reviews(evidence_entries)
    tenant_rollout_reviews = _tenant_rollout_reviews(evidence_entries)
    blockers = []
    warnings = []

    if not evidence_entries:
        warnings.append("No evidence files were attached.")

    missing_groups = context.get("missing_evidence_groups") or []
    if missing_groups:
        message = "Missing required evidence groups: %s" % ", ".join(missing_groups)
        if context.get("strict_required_evidence"):
            blockers.append(message)
        else:
            warnings.append(message)

    for entry in evidence_entries:
        path = Path(entry["path"])
        lines = _read_lines(path)
        if path.name == "summary.md":
            fields = _summary_fields(lines)
            status = fields.get("Status", "").strip().lower()
            review = {
                "path": entry["relative_path"],
                "status": fields.get("Status", ""),
                "exit_code": fields.get("Exit code", ""),
                "run_id": fields.get("Run ID", ""),
                "scope": fields.get("Scope", ""),
            }
            summary_reviews.append(review)
            if status in {"warning", "warn", "pass_with_warnings", "skipped"}:
                warnings.append(
                    "Summary %s has warning status %s"
                    % (entry["relative_path"], fields.get("Status", "unknown"))
                )
            elif status and status not in {"passed", "ready", "approved"}:
                blockers.append(
                    "Summary %s has non-passing status %s"
                    % (entry["relative_path"], fields.get("Status", "unknown"))
                )
        elif path.name == "status.tsv":
            _counts, rows = _status_counts(lines)
            for row in rows:
                status = row["status"].strip().lower()
                check = {
                    "path": entry["relative_path"],
                    "name": row["name"],
                    "status": row["status"],
                    "message": row["message"],
                }
                check_rows.append(check)
                if status in {"failed", "error", "blocked"}:
                    blockers.append(
                        "Check %s in %s is %s"
                        % (row["name"], entry["relative_path"], row["status"])
                    )
                elif status in {"skipped", "warning", "warn"}:
                    warnings.append(
                        "Check %s in %s is %s"
                        % (row["name"], entry["relative_path"], row["status"])
                    )

    for review in psp_readiness_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("PSP readiness %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("PSP readiness %s is %s" % (review["path"], review["decision"]))
        for provider in review.get("providers") or []:
            provider_decision = str(provider.get("decision") or "").lower()
            label = provider.get("provider") or "unknown"
            if provider_decision in {"failed", "blocked"}:
                blockers.append(
                    "PSP provider %s in %s is %s"
                    % (label, review["path"], provider.get("decision"))
                )
            elif provider_decision in {"warning", "warn"}:
                warnings.append(
                    "PSP provider %s in %s is %s"
                    % (label, review["path"], provider.get("decision"))
                )

    for review in fbr_readiness_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("FBR readiness %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("FBR readiness %s is %s" % (review["path"], review["decision"]))

    for review in fbr_fixture_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("FBR fixture smoke %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("FBR fixture smoke %s is %s" % (review["path"], review["decision"]))

    for review in monitoring_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Monitoring evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Monitoring evidence %s is %s" % (review["path"], review["decision"]))

    for review in incident_runbook_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Incident runbook evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Incident runbook evidence %s is %s" % (review["path"], review["decision"]))

    for review in load_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Load evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Load evidence %s is %s" % (review["path"], review["decision"]))

    for review in load_matrix_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Load profile matrix %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Load profile matrix %s is %s" % (review["path"], review["decision"]))

    for review in operations_bundle_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Operations release bundle %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Operations release bundle %s is %s" % (review["path"], review["decision"]))

    for review in release_retention_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Release retention evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Release retention evidence %s is %s" % (review["path"], review["decision"]))

    for review in secret_manager_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Secret manager evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Secret manager evidence %s is %s" % (review["path"], review["decision"]))

    for review in secret_runtime_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Secret runtime evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Secret runtime evidence %s is %s" % (review["path"], review["decision"]))

    for review in deployment_environment_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Deployment environment evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Deployment environment evidence %s is %s" % (review["path"], review["decision"]))

    for review in tenant_ops_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Tenant operations evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Tenant operations evidence %s is %s" % (review["path"], review["decision"]))
        for tenant in review.get("tenants") or []:
            tenant_decision = str(tenant.get("decision") or "").lower()
            tenant_label = tenant.get("tenant_db") or "unknown"
            if tenant_decision in {"failed", "blocked"}:
                blockers.append(
                    "Tenant %s in %s is %s"
                    % (tenant_label, review["path"], tenant.get("decision"))
                )
            elif tenant_decision in {"warning", "warn"}:
                warnings.append(
                    "Tenant %s in %s is %s"
                    % (tenant_label, review["path"], tenant.get("decision"))
                )

    for review in tenant_smoke_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Tenant smoke evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Tenant smoke evidence %s is %s" % (review["path"], review["decision"]))
        for tenant in review.get("tenants") or []:
            tenant_decision = str(tenant.get("decision") or "").lower()
            tenant_label = tenant.get("tenant_db") or "unknown"
            if tenant_decision in {"failed", "blocked"}:
                blockers.append(
                    "Tenant smoke %s in %s is %s"
                    % (tenant_label, review["path"], tenant.get("decision"))
                )
            elif tenant_decision in {"warning", "warn"}:
                warnings.append(
                    "Tenant smoke %s in %s is %s"
                    % (tenant_label, review["path"], tenant.get("decision"))
                )

    for review in tenant_rollout_reviews:
        decision = str(review.get("decision") or "").lower()
        if decision in {"failed", "blocked"}:
            blockers.append("Tenant rollout evidence %s is %s" % (review["path"], review["decision"]))
        elif decision in {"warning", "warn"}:
            warnings.append("Tenant rollout evidence %s is %s" % (review["path"], review["decision"]))
        for tenant in review.get("tenants") or []:
            tenant_decision = str(tenant.get("decision") or "").lower()
            tenant_label = tenant.get("tenant_db") or "unknown"
            if tenant_decision in {"failed", "blocked"}:
                blockers.append(
                    "Tenant rollout %s in %s is %s"
                    % (tenant_label, review["path"], tenant.get("decision"))
                )
            elif tenant_decision in {"warning", "warn"}:
                warnings.append(
                    "Tenant rollout %s in %s is %s"
                    % (tenant_label, review["path"], tenant.get("decision"))
                )

    if blockers:
        decision = "blocked"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "ready"
        ci_status = "pass"

    return {
        "package_id": context["run_id"],
        "generated_at": context["generated_at"],
        "target_environment": context["target_environment"],
        "git_branch": context["git_branch"],
        "git_head": context["git_head"],
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "evidence_group_counts": group_counts,
        "required_evidence_groups": context.get("required_evidence_groups") or [],
        "missing_evidence_groups": missing_groups,
        "strict_required_evidence": bool(context.get("strict_required_evidence")),
        "summary_reviews": summary_reviews,
        "check_rows": check_rows,
        "psp_readiness_reviews": psp_readiness_reviews,
        "fbr_readiness_reviews": fbr_readiness_reviews,
        "fbr_fixture_reviews": fbr_fixture_reviews,
        "monitoring_reviews": monitoring_reviews,
        "incident_runbook_reviews": incident_runbook_reviews,
        "load_reviews": load_reviews,
        "load_matrix_reviews": load_matrix_reviews,
        "operations_bundle_reviews": operations_bundle_reviews,
        "release_retention_reviews": release_retention_reviews,
        "secret_manager_reviews": secret_manager_reviews,
        "secret_runtime_reviews": secret_runtime_reviews,
        "deployment_environment_reviews": deployment_environment_reviews,
        "tenant_ops_reviews": tenant_ops_reviews,
        "tenant_smoke_reviews": tenant_smoke_reviews,
        "tenant_rollout_reviews": tenant_rollout_reviews,
    }


def _index(context, files, evidence_entries):
    evidence_lines = "\n".join(
        "- `%s` (%s bytes) `%s`" % (
            entry["relative_path"],
            entry["size_bytes"],
            entry["sha256"],
        )
        for entry in evidence_entries
    )
    if not evidence_lines:
        evidence_lines = "- No evidence files were attached by this generator run."
    template_lines = "\n".join("- [%s](%s)" % (title, path.name) for title, path in files)
    required_groups = context.get("required_evidence_groups") or []
    missing_groups = context.get("missing_evidence_groups") or []
    if required_groups:
        required_lines = "\n".join(
            [
                "- Mode: %s" % ("strict" if context.get("strict_required_evidence") else "warn"),
                "- Required groups: %s" % ", ".join(required_groups),
                "- Missing groups: %s" % (", ".join(missing_groups) if missing_groups else "none"),
            ]
        )
    else:
        required_lines = "- No required evidence groups configured for this run."
    return f"""
# Tijara Release Sign-Off Package

- Package ID: {context["run_id"]}
- Generated: {context["generated_at"]}
- Git branch: {context["git_branch"]}
- Git head: {context["git_head"]}
- Target environment: {context["target_environment"]}

## Templates

{template_lines}

## Evidence Manifest

{evidence_lines}

## Evidence Summary

- [Evidence Summary](evidence-summary.md)
- [Release Readiness JSON](release-readiness.json)

## Required Evidence Guardrails

{required_lines}

## Usage

1. Attach or copy release, E2E, operations, PSP/FBR, hardware, finance, and
   security evidence into this package or pass evidence paths to the generator.
2. Complete each checklist with named owners.
3. Record approvals, exceptions, due dates, and rollback references.
4. Keep this package with the release-candidate build artifacts and database
   backup reference.
"""


def main():
    parser = argparse.ArgumentParser(description="Generate Tijara release sign-off package templates.")
    parser.add_argument(
        "--output",
        default=os.environ.get("TIJARA_SIGNOFF_OUTPUT", ""),
        help="Output directory. Defaults to deploy/runtime/signoff-packages/<run-id>.",
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_SIGNOFF_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_SIGNOFF_ENVIRONMENT", "staging"),
    )
    parser.add_argument(
        "--evidence-path",
        action="append",
        default=[],
        help="Evidence file or directory to include in manifest. Can be repeated.",
    )
    parser.add_argument(
        "--required-evidence-group",
        action="append",
        default=[],
        help=(
            "Required evidence group for approval readiness. Examples: release, e2e, "
            "ops, security, hardware, fbr, psp. Can be repeated."
        ),
    )
    parser.add_argument(
        "--strict-required-evidence",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE")),
        help="Exit non-zero after writing the package when required evidence groups are missing.",
    )
    args = parser.parse_args()

    evidence_paths = list(args.evidence_path)
    env_paths = os.environ.get("TIJARA_SIGNOFF_EVIDENCE_PATHS", "")
    if env_paths:
        evidence_paths.extend(path.strip() for path in env_paths.split(","))

    required_groups = list(args.required_evidence_group)
    required_groups.extend(_csv_items(os.environ.get("TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS")))
    required_groups = [
        group
        for group in dict.fromkeys(_normalize_group_name(group) for group in required_groups)
        if group
    ]

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/signoff-packages" / args.run_id
    output.mkdir(parents=True, exist_ok=True)

    context = {
        "run_id": args.run_id,
        "generated_at": _utc_now(),
        "git_branch": _git_value(["git", "branch", "--show-current"]),
        "git_head": _git_value(["git", "rev-parse", "--short", "HEAD"]),
        "target_environment": args.target_environment,
    }

    template_specs = [
        ("Release Go/No-Go", "release-go-no-go.md", _release_go_no_go(context)),
        ("PSP Certification", "psp-certification.md", _psp_certification(context)),
        ("FBR Certification", "fbr-certification.md", _fbr_certification(context)),
        ("Hardware Certification", "hardware-certification.md", _hardware_certification(context)),
        ("Finance and Tax Sign-Off", "finance-tax-signoff.md", _finance_tax(context)),
        ("Security Review Sign-Off", "security-review-signoff.md", _security_review(context)),
    ]

    written_templates = []
    for title, filename, content in template_specs:
        path = output / filename
        _write(path, content)
        written_templates.append((title, path))

    evidence_entries = []
    for evidence_file in _iter_evidence_files(evidence_paths):
        try:
            relative = evidence_file.relative_to(ROOT_DIR)
        except ValueError:
            relative = evidence_file
        evidence_entries.append(
            {
                "path": str(evidence_file),
                "relative_path": str(relative),
                "size_bytes": evidence_file.stat().st_size,
                "sha256": _hash_file(evidence_file),
            }
        )
    group_counts = _group_counts(evidence_entries)
    missing_required_groups = [group for group in required_groups if group_counts.get(group, 0) < 1]
    context.update(
        {
            "required_evidence_groups": required_groups,
            "missing_evidence_groups": missing_required_groups,
            "strict_required_evidence": bool(args.strict_required_evidence),
        }
    )

    manifest = {
        "context": context,
        "generated_templates": [path.name for _, path in written_templates],
        "evidence_summary": "evidence-summary.md",
        "release_readiness": "release-readiness.json",
        "evidence_group_counts": group_counts,
        "required_evidence_groups": required_groups,
        "missing_evidence_groups": missing_required_groups,
        "strict_required_evidence": bool(args.strict_required_evidence),
        "evidence": evidence_entries,
    }
    readiness = _release_readiness(context, evidence_entries, group_counts)
    _write(output / "evidence-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "evidence-summary.md", _evidence_summary(context, evidence_entries))
    _write(output / "release-readiness.json", json.dumps(readiness, indent=2, sort_keys=True))
    _write(output / "README.md", _index(context, written_templates, evidence_entries))

    print("Sign-off package written to %s" % output)
    if missing_required_groups:
        message = "Missing required sign-off evidence groups: %s" % ", ".join(missing_required_groups)
        if args.strict_required_evidence:
            print(message, file=sys.stderr)
            return 2
        print("Warning: %s" % message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
