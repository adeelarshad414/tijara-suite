#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


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


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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


def _result_status(payload, exit_code, fail_on_warning):
    decision = str(payload.get("decision") or "").lower()
    ci_status = str(payload.get("ci_status") or "").lower()
    if exit_code != 0 or decision in {"failed", "blocked"} or ci_status == "fail":
        return "failed"
    if fail_on_warning and (decision in {"warning", "warn"} or ci_status == "pass_with_warnings"):
        return "failed"
    if decision in {"warning", "warn"} or ci_status == "pass_with_warnings":
        return "warning"
    return "passed"


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Provider Readiness

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

- Provider readiness manifest: protected-provider-readiness.json
- PSP readiness folder: psp-readiness/
- FBR readiness folder: fbr-readiness/
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export protected PSP/FBR provider readiness evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_PROVIDER_READINESS_OUTPUT", ""))
    parser.add_argument(
        "--psp-provider",
        action="append",
        default=[],
        help="PSP provider profile to verify. Can be repeated.",
    )
    parser.add_argument(
        "--psp-providers",
        default=os.environ.get("TIJARA_PROVIDER_READINESS_PSP_PROVIDERS", "jazzcash,easypaisa,stripe"),
    )
    parser.add_argument(
        "--require-psp",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROVIDER_READINESS_REQUIRE_PSP")),
    )
    parser.add_argument(
        "--require-fbr",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROVIDER_READINESS_REQUIRE_FBR")),
    )
    parser.add_argument(
        "--require-native-signatures",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES")),
    )
    parser.add_argument(
        "--require-live-fbr",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROVIDER_READINESS_REQUIRE_LIVE_FBR"))
        or _truthy(os.environ.get("TIJARA_PROVIDER_READINESS_REQUIRE_LIVE")),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PROVIDER_READINESS_FAIL_ON_WARNING")),
    )
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_PROVIDER_READINESS_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    certification_groups = set(_csv_items(os.environ.get("TIJARA_PROTECTED_CERTIFICATION_GROUPS", "")))
    require_psp = args.require_psp or "psp" in certification_groups
    require_fbr = args.require_fbr or "fbr" in certification_groups
    psp_providers = _dedupe(args.psp_provider + _csv_items(args.psp_providers))

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-provider-readiness" / args.run_id
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

    runs = []
    if psp_providers or require_psp:
        psp_output = output / "psp-readiness"
        command = [
            "python3",
            "scripts/export_psp_readiness.py",
            "--run-id",
            args.run_id,
            "--target-environment",
            args.target_environment,
            "--output",
            str(psp_output),
        ]
        for provider in psp_providers:
            command.extend(["--provider", provider])
        if args.require_native_signatures or require_psp:
            command.append("--require-native-signatures")
        if args.non_strict:
            command.append("--non-strict")
        run = _run_command(command)
        payload = _read_json(psp_output / "psp-readiness.json")
        status = _result_status(payload, run["exit_code"], args.fail_on_warning)
        runs.append({"name": "psp-readiness", "status": status, "output": str(psp_output), "payload": payload, **run})
        message = "PSP readiness decision is %s/%s." % (payload.get("decision") or "unknown", payload.get("ci_status") or "unknown")
        rows.append(_row("psp-readiness", status, message))
        if status == "failed" and (require_psp or strict):
            blockers.append(message)
        elif status != "passed":
            warnings.append(message)
    else:
        rows.append(_row("psp-readiness", "passed", "PSP readiness is not required for this protected run."))

    if require_fbr or os.environ.get("FBR_ADAPTER_MODE") or os.environ.get("FBR_PROVIDER_NAME"):
        fbr_output = output / "fbr-readiness"
        command = [
            "python3",
            "scripts/export_fbr_readiness.py",
            "--run-id",
            args.run_id,
            "--target-environment",
            args.target_environment,
            "--output",
            str(fbr_output),
        ]
        if args.require_live_fbr:
            command.append("--require-live")
        if args.non_strict:
            command.append("--non-strict")
        run = _run_command(command)
        payload = _read_json(fbr_output / "fbr-readiness.json")
        status = _result_status(payload, run["exit_code"], args.fail_on_warning)
        runs.append({"name": "fbr-readiness", "status": status, "output": str(fbr_output), "payload": payload, **run})
        message = "FBR readiness decision is %s/%s." % (payload.get("decision") or "unknown", payload.get("ci_status") or "unknown")
        rows.append(_row("fbr-readiness", status, message))
        if status == "failed" and (require_fbr or strict):
            blockers.append(message)
        elif status != "passed":
            warnings.append(message)
    else:
        rows.append(_row("fbr-readiness", "passed", "FBR readiness is not required for this protected run."))

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
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
        "require_psp": bool(require_psp),
        "require_fbr": bool(require_fbr),
        "require_live_fbr": bool(args.require_live_fbr),
        "require_native_signatures": bool(args.require_native_signatures or require_psp),
        "fail_on_warning": bool(args.fail_on_warning),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
        "runs": runs,
        "metadata": metadata,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "require_psp=%s" % int(require_psp),
            "require_fbr=%s" % int(require_fbr),
            "require_live_fbr=%s" % int(args.require_live_fbr),
            "psp_providers=%s" % (",".join(psp_providers) or "<none>"),
            "run_count=%s" % len(runs),
            "metadata_keys=%s" % (",".join(sorted(metadata)) or "<none>"),
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-provider-readiness.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Protected provider readiness written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
