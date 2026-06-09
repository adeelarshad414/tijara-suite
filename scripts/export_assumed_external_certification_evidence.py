#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("assumed-cert-%Y%m%dT%H%M%SZ")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _run(name: str, command: list[str], output: Path) -> dict:
    started_at = _utc_now()
    process = subprocess.run(
        command,
        cwd=ROOT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    finished_at = _utc_now()
    log_path = output / ("%s.log" % name)
    _write(
        log_path,
        "\n".join(
            [
                "$ %s" % " ".join(command),
                "",
                "## stdout",
                process.stdout or "",
                "",
                "## stderr",
                process.stderr or "",
            ]
        ),
    )
    return {
        "name": name,
        "command": command,
        "exit_code": process.returncode,
        "status": "passed" if process.returncode == 0 else "failed",
        "started_at": started_at,
        "finished_at": finished_at,
        "log": _repo_relative(log_path),
    }


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _status_tsv(runs: list[dict]) -> str:
    lines = ["check\tstatus\texit_code\tartifact\tmessage"]
    for run in runs:
        lines.append(
            "%s\t%s\t%s\t%s\t%s"
            % (
                run["name"],
                run["status"],
                run["exit_code"],
                run.get("artifact", ""),
                run.get("message", ""),
            )
        )
    return "\n".join(lines)


def _summary(context: dict, runs: list[dict], assumptions: list[str], warnings: list[str]) -> str:
    run_lines = "\n".join(
        "- %s: %s (exit %s) `%s`"
        % (run["name"], run["status"], run["exit_code"], run.get("artifact") or run["log"])
        for run in runs
    )
    assumption_lines = "\n".join("- %s" % item for item in assumptions)
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Assumed External Certification Evidence

- Decision: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Generated: {context["generated_at"]}
- Output: {context["output"]}

## Runs

{run_lines}

## Assumptions

{assumption_lines}

## Go-Live Warnings

{warning_lines}

## Evidence Files

- Manifest: `assumed-certification-evidence.json`
- Status table: `status.tsv`
- Environment summary: `env-summary.txt`
- Command logs: `*.log`
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate dummy/assumption-mode evidence for external hardware, FBR, PSP, and courier certification."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_ASSUMED_CERT_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_ASSUMED_CERT_ENVIRONMENT", "staging-assumed"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_ASSUMED_CERT_OUTPUT", ""))
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/assumed-certification" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    payload_hash = hashlib.sha256(args.run_id.encode("utf-8")).hexdigest()
    runs: list[dict] = []

    psp_output = output / "psp-readiness"
    runs.append(
        _run(
            "psp-readiness-assumed",
            [
                sys.executable,
                "scripts/export_psp_readiness.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(psp_output),
                "--provider",
                "jazzcash",
                "--provider",
                "easypaisa",
                "--provider",
                "stripe",
                "--secret-present",
                "jazzcash=true",
                "--secret-present",
                "easypaisa=true",
                "--secret-present",
                "stripe=true",
                "--certification-reference",
                "jazzcash=ASSUMED-JAZZCASH-UAT-001",
                "--certification-reference",
                "easypaisa=ASSUMED-EASYPAISA-UAT-001",
                "--certification-reference",
                "stripe=ASSUMED-STRIPE-UAT-001",
                "--certification-status",
                "jazzcash=approved",
                "--certification-status",
                "easypaisa=approved",
                "--certification-status",
                "stripe=approved",
                "--require-native-signatures",
                "--non-strict",
            ],
            output,
        )
    )
    runs[-1]["artifact"] = _repo_relative(psp_output / "psp-readiness.json")

    psp_fixture_output = output / "psp-fixture-smoke"
    runs.append(
        _run(
            "psp-fixture-smoke",
            [
                sys.executable,
                "scripts/psp_settlement_fixture_smoke.py",
                "--run-id",
                args.run_id,
                "--output",
                str(psp_fixture_output),
            ],
            output,
        )
    )
    runs[-1]["artifact"] = _repo_relative(psp_fixture_output / "psp-fixture-smoke.json")

    fbr_output = output / "fbr-readiness"
    runs.append(
        _run(
            "fbr-readiness-assumed",
            [
                sys.executable,
                "scripts/export_fbr_readiness.py",
                "--run-id",
                args.run_id,
                "--target-environment",
                args.target_environment,
                "--output",
                str(fbr_output),
                "--adapter-mode",
                "live",
                "--certification-environment",
                "sandbox",
                "--provider-name",
                "Assumed Certified FBR Provider",
                "--endpoint",
                "https://fbr-sandbox.assumed.tijara-suite.local/invoice",
                "--client-id",
                "assumed-fbr-client-id",
                "--credential-reference",
                "secret-manager://tijara/assumed/fbr",
                "--sandbox-reference",
                "ASSUMED-FBR-SBX-001",
                "--fbr-pos-id",
                "ASSUMED-POS-001",
                "--branch-code",
                "ASSUMED-BR-001",
                "--payload-hash",
                payload_hash,
                "--client-secret-present",
                "--non-strict",
            ],
            output,
        )
    )
    runs[-1]["artifact"] = _repo_relative(fbr_output / "fbr-readiness.json")

    fbr_fixture_output = output / "fbr-fixture-smoke"
    runs.append(
        _run(
            "fbr-fixture-smoke",
            [
                sys.executable,
                "scripts/fbr_provider_fixture_smoke.py",
                "--run-id",
                args.run_id,
                "--output",
                str(fbr_fixture_output),
            ],
            output,
        )
    )
    runs[-1]["artifact"] = _repo_relative(fbr_fixture_output / "fbr-fixture-smoke.json")

    hardware_log_run = _run(
        "hardware-dry-run-smoke",
        [
            sys.executable,
            "scripts/hardware_certification_smoke.py",
            "hardware-bridge/config/certification_profiles.example.json",
        ],
        output,
    )
    hardware_log_run["artifact"] = hardware_log_run["log"]
    runs.append(hardware_log_run)

    courier_evidence_file = output / "courier-assumed-evidence.md"
    _write(
        courier_evidence_file,
        """
# Assumed Courier Certification Evidence

- Provider: TCS-ASSUMED
- Scope: create shipment, cancel shipment, track shipment, label/manifest, COD reconciliation.
- Mode: dummy public-repo assumption for staging evidence only.
- Production replacement: attach signed courier UAT/live certification letter, API payload logs,
  webhook proof, and COD settlement sample.
""",
    )
    courier_output = output / "courier-certification"
    runs.append(
        _run(
            "courier-certification-assumed",
            [
                sys.executable,
                "scripts/collect_certification_evidence.py",
                "--run-id",
                args.run_id,
                "--category",
                "courier",
                "--target-environment",
                args.target_environment,
                "--output",
                str(courier_output),
                "--provider",
                "TCS-ASSUMED",
                "--reference",
                "ASSUMED-COURIER-UAT-001",
                "--owner",
                "Delivery Ops",
                "--evidence-file",
                str(courier_evidence_file),
                "--minimum-evidence-files",
                "1",
                "--metadata",
                "provider_type=pakistan_courier",
                "--metadata",
                "api_scope=create_cancel_track_label_manifest_cod",
                "--non-strict",
            ],
            output,
        )
    )
    runs[-1]["artifact"] = _repo_relative(courier_output / "certification-evidence.json")

    failures = [run for run in runs if run["exit_code"] != 0]
    warnings = [
        "Assumption-mode evidence is not a legal or provider certification substitute.",
        "Physical printer, drawer, scanner, scale, and display certification still needs target devices.",
        "FBR sandbox/live sign-off still needs certified-provider credentials and official compliance evidence.",
        "JazzCash, Easypaisa, and Stripe still need merchant UAT/live references before production launch.",
        "Courier create/cancel/track/label/manifest/COD flows still need provider UAT/live certification.",
    ]
    assumptions = [
        "PSP secrets and certification references are dummy redacted values for staging evidence.",
        "FBR provider, POS id, branch code, endpoint, and payload hash are dummy assumed values.",
        "Hardware operations run through dry-run bridge drivers using the open-source certification profile.",
        "Committed FBR and PSP fixtures stand in for provider payloads until signed samples are attached.",
        "Courier certification uses a dummy Pakistan courier reference until signed provider evidence is attached.",
    ]
    decision = "failed" if failures else "passed_with_assumptions"
    ci_status = "fail" if failures else "pass_with_warnings"
    context = {
        "run_id": args.run_id,
        "target_environment": args.target_environment,
        "generated_at": _utc_now(),
        "output": _repo_relative(output),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "runs": runs,
        "assumptions": assumptions,
        "warnings": warnings,
        "psp_readiness": _read_json(psp_output / "psp-readiness.json"),
        "psp_fixture_smoke": _read_json(psp_fixture_output / "psp-fixture-smoke.json"),
        "fbr_readiness": _read_json(fbr_output / "fbr-readiness.json"),
        "fbr_fixture_smoke": _read_json(fbr_fixture_output / "fbr-fixture-smoke.json"),
        "courier_certification": _read_json(courier_output / "certification-evidence.json"),
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
            "output=%s" % _repo_relative(output),
            "dummy_mode=1",
            "hardware_mode=dry_run",
            "fbr_mode=assumed_sandbox_live_adapter",
            "psp_mode=assumed_uat_certification",
            "courier_mode=assumed_uat_certification",
        ]
    )
    for run in runs:
        run["message"] = "Completed with dummy/assumption inputs." if run["status"] == "passed" else "Command failed."
    _write(output / "assumed-certification-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(runs))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, runs, assumptions, warnings))

    print("Assumed certification evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
