#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}
PLACEHOLDER_PREFIXES = ("replace-", "change-me", "example-", "dummy-", "test-")
SUPPORTED_SOURCES = {"env", "file", "command"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _present(value):
    return bool(str(value or "").strip())


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _csv_items(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _secret_like_keys(metadata):
    flagged = []
    for key in metadata:
        normalized = str(key).lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


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


def _is_placeholder(value):
    text = str(value or "").strip()
    lowered = text.lower()
    if not text:
        return False
    return lowered.startswith(PLACEHOLDER_PREFIXES)


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _add_required(rows, blockers, warnings, strict, name, value, label):
    if _present(value):
        rows.append(_row(name, "passed", "%s is recorded." % label))
        return
    message = "%s is required for runtime secret connectivity evidence." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


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
# Secret Runtime Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Provider: {context["provider"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Secret runtime manifest: secret-runtime-evidence.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def _parse_probe(raw):
    if "=" not in raw:
        raise ValueError("Probe must use NAME=source:reference format: %s" % raw)
    name, spec = raw.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError("Probe name cannot be blank.")
    if ":" not in spec:
        raise ValueError("Probe source must use source:reference format for %s." % name)
    source, reference = spec.split(":", 1)
    source = source.strip().lower()
    reference = reference.strip()
    if source not in SUPPORTED_SOURCES:
        raise ValueError("Unsupported secret source %s for %s." % (source or "<empty>", name))
    if not reference:
        raise ValueError("Probe reference cannot be blank for %s." % name)
    return {"name": name, "source": source, "reference": reference}


def _safe_reference(probe):
    if probe["source"] == "command":
        return "<command-redacted>"
    return probe["reference"]


def _read_file_secret(path):
    target = Path(path)
    if not target.is_absolute():
        target = ROOT_DIR / target
    if not target.is_file():
        return None, "file does not exist"
    try:
        return target.read_text(encoding="utf-8", errors="replace").strip(), ""
    except OSError as error:
        return None, str(error)


def _run_command_secret(command, timeout):
    try:
        result = subprocess.run(
            shlex.split(command),
            cwd=str(ROOT_DIR),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except ValueError as error:
        return None, "could not parse command: %s" % error
    except subprocess.TimeoutExpired:
        return None, "command timed out after %ss" % timeout
    if result.returncode != 0:
        return None, "command exited %s" % result.returncode
    return result.stdout.strip(), ""


def _resolve_probe(probe, timeout, reject_placeholders):
    value = None
    error = ""
    if probe["source"] == "env":
        value = os.environ.get(probe["reference"])
        if value is None:
            error = "environment variable is not set"
    elif probe["source"] == "file":
        value, error = _read_file_secret(probe["reference"])
    elif probe["source"] == "command":
        value, error = _run_command_secret(probe["reference"], timeout)
    if error:
        return False, error, 0
    if not _present(value):
        return False, "resolved value is empty", 0
    if reject_placeholders and _is_placeholder(value):
        return False, "resolved value looks like a placeholder", len(value)
    return True, "resolved without exposing value", len(value)


def main():
    parser = argparse.ArgumentParser(
        description="Export Tijara runtime secret connectivity evidence without exposing values."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_SECRET_RUNTIME_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_SECRET_RUNTIME_ENVIRONMENT", "production"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_SECRET_RUNTIME_OUTPUT", ""))
    parser.add_argument(
        "--secret-manager-provider",
        default=os.environ.get("TIJARA_SECRET_MANAGER_PROVIDER", ""),
    )
    parser.add_argument(
        "--secret-manager-reference",
        default=os.environ.get("TIJARA_SECRET_MANAGER_REFERENCE", ""),
    )
    parser.add_argument(
        "--secret-access-review-ref",
        default=os.environ.get("TIJARA_SECRET_ACCESS_REVIEW_REF", ""),
    )
    parser.add_argument("--probe", action="append", default=[])
    parser.add_argument("--expected-secret", action="append", default=[])
    parser.add_argument(
        "--minimum-probes",
        type=int,
        default=int(os.environ.get("TIJARA_SECRET_RUNTIME_MINIMUM_PROBES", "1")),
    )
    parser.add_argument("--metadata", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_SECRET_RUNTIME_TIMEOUT", "8")))
    parser.add_argument(
        "--allow-placeholder",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_SECRET_RUNTIME_ALLOW_PLACEHOLDER")),
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_SECRET_RUNTIME_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when runtime secret evidence is missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    probes_raw = list(args.probe)
    probes_raw.extend(_csv_items(os.environ.get("TIJARA_SECRET_RUNTIME_PROBES")))
    expected_secrets = list(dict.fromkeys(args.expected_secret + _csv_items(os.environ.get("TIJARA_SECRET_RUNTIME_EXPECTED_SECRETS"))))

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/secret-runtime-evidence" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    blockers = []
    warnings = []

    _add_required(rows, blockers, warnings, strict, "secret-manager-provider", args.secret_manager_provider, "Secret manager provider")
    _add_required(rows, blockers, warnings, strict, "secret-manager-reference", args.secret_manager_reference, "Secret manager reference")
    _add_required(rows, blockers, warnings, strict, "secret-access-review", args.secret_access_review_ref, "Secret access review")

    try:
        metadata = _metadata_items(args.metadata)
    except ValueError as error:
        metadata = {}
        blockers.append(str(error))
        rows.append(_row("metadata-format", "failed", str(error)))
    else:
        rows.append(_row("metadata-format", "passed", "%s metadata item(s) parsed." % len(metadata)))

    flagged = _secret_like_keys(metadata)
    if flagged:
        message = "Secret-like metadata keys are not allowed: %s" % ", ".join(flagged)
        blockers.append(message)
        rows.append(_row("metadata-secret-safety", "failed", message))
    else:
        rows.append(_row("metadata-secret-safety", "passed", "No secret-like metadata keys found."))

    probes = []
    parse_errors = []
    for raw_probe in probes_raw:
        try:
            probes.append(_parse_probe(raw_probe))
        except ValueError as error:
            parse_errors.append(str(error))
    if parse_errors:
        blockers.extend(parse_errors)
        rows.append(_row("probe-format", "failed", "; ".join(parse_errors)))
    else:
        rows.append(_row("probe-format", "passed", "%s probe(s) parsed." % len(probes)))

    probe_names = {probe["name"] for probe in probes}
    missing_expected = [name for name in expected_secrets if name not in probe_names]
    if missing_expected:
        message = "Expected runtime secret probe(s) missing: %s" % ", ".join(missing_expected)
        if strict:
            blockers.append(message)
            rows.append(_row("expected-secret-probes", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("expected-secret-probes", "warning", message))
    else:
        rows.append(_row("expected-secret-probes", "passed", "%s expected probe(s) are present." % len(expected_secrets)))

    resolved = []
    unresolved = []
    probe_results = []
    for probe in probes:
        ok, message, value_length = _resolve_probe(probe, args.timeout, not args.allow_placeholder)
        probe_result = {
            "name": probe["name"],
            "source": probe["source"],
            "reference": _safe_reference(probe),
            "resolved": ok,
            "value_length": value_length if ok else 0,
            "message": message,
        }
        probe_results.append(probe_result)
        if ok:
            resolved.append(probe_result)
            rows.append(_row("probe-%s" % probe["name"], "passed", "%s resolved from %s." % (probe["name"], probe["source"])))
        else:
            unresolved.append(probe_result)
            rows.append(_row("probe-%s" % probe["name"], "failed", "%s did not resolve: %s" % (probe["name"], message)))

    minimum = max(args.minimum_probes, 0)
    if len(resolved) < minimum:
        message = "Resolved %s runtime secret probe(s); minimum required is %s." % (len(resolved), minimum)
        if strict:
            blockers.append(message)
            rows.append(_row("minimum-probes", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("minimum-probes", "warning", message))
    else:
        rows.append(_row("minimum-probes", "passed", "%s runtime secret probe(s) resolved." % len(resolved)))

    for result in unresolved:
        if strict:
            blockers.append("%s: %s" % (result["name"], result["message"]))
        else:
            warnings.append("%s: %s" % (result["name"], result["message"]))

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
        "provider": args.secret_manager_provider.strip() or "unset",
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "secret_manager": {
            "provider_present": _present(args.secret_manager_provider),
            "provider": args.secret_manager_provider.strip(),
            "reference_present": _present(args.secret_manager_reference),
            "access_review_reference_present": _present(args.secret_access_review_ref),
        },
        "minimum_probes": minimum,
        "probe_count": len(probes),
        "resolved_probe_count": len(resolved),
        "unresolved_probe_count": len(unresolved),
        "expected_secrets": expected_secrets,
        "probes": probe_results,
        "metadata": metadata,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "secret_manager_provider=%s" % (args.secret_manager_provider.strip() or "<unset>"),
            "secret_manager_reference_present=%s" % int(_present(args.secret_manager_reference)),
            "secret_access_review_present=%s" % int(_present(args.secret_access_review_ref)),
            "probe_count=%s" % len(probes),
            "resolved_probe_count=%s" % len(resolved),
            "unresolved_probe_count=%s" % len(unresolved),
            "minimum_probes=%s" % minimum,
            "expected_secret_count=%s" % len(expected_secrets),
            "allow_placeholder=%s" % int(args.allow_placeholder),
            "non_strict=%s" % int(args.non_strict),
        ]
    )

    _write(output / "secret-runtime-evidence.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Secret runtime evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
