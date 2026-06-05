#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


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


def _evidence_group(entry):
    relative = entry["relative_path"].replace("\\", "/")
    if "release-evidence/" in relative:
        return "Release Candidate"
    if "e2e-evidence/" in relative:
        return "Browser E2E"
    if "ops-evidence/" in relative:
        return "Operations"
    if "hardware" in relative.lower():
        return "Hardware"
    if "fbr" in relative.lower():
        return "FBR"
    if "psp" in relative.lower() or "settlement" in relative.lower():
        return "PSP"
    if "security" in relative.lower():
        return "Security"
    return "General"


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
        message = parts[4] if len(parts) >= 5 else ""
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


def _evidence_summary(context, evidence_entries):
    by_group = {}
    summary_blocks = []
    status_blocks = []
    environment_blocks = []

    for entry in evidence_entries:
        group = _evidence_group(entry)
        by_group[group] = by_group.get(group, 0) + 1
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

    return f"""
# Evidence Summary

- Package ID: {context["run_id"]}
- Generated: {context["generated_at"]}
- Target environment: {context["target_environment"]}

## Evidence Groups

{group_lines}

## Run Summaries

{chr(10).join(summary_lines)}
## Check Status Tables

{chr(10).join(status_lines)}
## Environment Snapshots

{chr(10).join(env_lines)}
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
    args = parser.parse_args()

    evidence_paths = list(args.evidence_path)
    env_paths = os.environ.get("TIJARA_SIGNOFF_EVIDENCE_PATHS", "")
    if env_paths:
        evidence_paths.extend(path.strip() for path in env_paths.split(","))

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

    manifest = {
        "context": context,
        "generated_templates": [path.name for _, path in written_templates],
        "evidence_summary": "evidence-summary.md",
        "evidence": evidence_entries,
    }
    _write(output / "evidence-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "evidence-summary.md", _evidence_summary(context, evidence_entries))
    _write(output / "README.md", _index(context, written_templates, evidence_entries))

    print("Sign-off package written to %s" % output)


if __name__ == "__main__":
    main()
