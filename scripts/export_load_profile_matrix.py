#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = {
    "code",
    "tenant_size",
    "verticals",
    "profile_name",
    "vus",
    "duration",
    "max_p95_ms",
    "max_fail_rate",
    "min_checks_rate",
    "checkout_enabled",
}
SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _resolve(path):
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _load_matrix(path):
    target = _resolve(path)
    if not target.is_file():
        raise RuntimeError("Load profile matrix not found: %s" % target)
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not read load profile matrix %s: %s" % (target, error)) from error


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _duration_ok(value):
    return bool(re.match(r"^[1-9][0-9]*(ms|s|m|h)$", str(value or "").strip()))


def _float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _secret_like_keys(profile):
    flagged = []
    for key in profile:
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in SECRET_KEY_PARTS):
            flagged.append(key)
    return flagged


def _profile_review(profile):
    code = str(profile.get("code") or "<missing>")
    blockers = []
    warnings = []
    missing = sorted(REQUIRED_FIELDS - set(profile))
    if missing:
        blockers.append("Missing required fields: %s" % ", ".join(missing))
    if _secret_like_keys(profile):
        blockers.append("Secret-like keys are not allowed: %s" % ", ".join(_secret_like_keys(profile)))
    if not isinstance(profile.get("verticals"), list) or not profile.get("verticals"):
        blockers.append("Verticals must be a non-empty list.")
    if int(profile.get("vus") or 0) <= 0:
        blockers.append("VUs must be greater than zero.")
    if not _duration_ok(profile.get("duration")):
        blockers.append("Duration must use k6 duration syntax such as 30s, 5m, or 1h.")
    max_p95 = _float(profile.get("max_p95_ms"))
    max_fail = _float(profile.get("max_fail_rate"))
    min_checks = _float(profile.get("min_checks_rate"))
    if max_p95 is None or max_p95 <= 0:
        blockers.append("max_p95_ms must be greater than zero.")
    if max_fail is None or not 0 <= max_fail < 1:
        blockers.append("max_fail_rate must be between 0 and 1.")
    if min_checks is None or not 0 < min_checks <= 1:
        blockers.append("min_checks_rate must be between 0 and 1.")
    return {
        "code": code,
        "tenant_size": profile.get("tenant_size", ""),
        "verticals": profile.get("verticals") or [],
        "profile_name": profile.get("profile_name", ""),
        "vus": profile.get("vus"),
        "duration": profile.get("duration", ""),
        "max_p95_ms": max_p95,
        "max_fail_rate": max_fail,
        "min_checks_rate": min_checks,
        "checkout_enabled": bool(profile.get("checkout_enabled")),
        "notes": profile.get("notes", ""),
        "blockers": blockers,
        "warnings": warnings,
    }


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _summary(context, rows, profile_reviews, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    profile_lines = "\n".join(
        "- `%s`: verticals=%s, vus=%s, duration=%s, p95=%s, fail_rate=%s, checks_rate=%s, checkout=%s"
        % (
            review["code"],
            ",".join(review["verticals"]),
            review["vus"],
            review["duration"],
            review["max_p95_ms"],
            review["max_fail_rate"],
            review["min_checks_rate"],
            "yes" if review["checkout_enabled"] else "no",
        )
        for review in profile_reviews
    ) or "- No profiles were found."
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Load Profile Matrix Evidence

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Matrix: {context["matrix_path"]}
- Approved by: {context["approved_by"] or "<unset>"}
- Approval reference: {context["approval_reference"] or "<unset>"}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Profiles

{profile_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Load profile matrix manifest: load-profile-matrix.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara load-profile matrix evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_LOAD_MATRIX_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_LOAD_MATRIX_ENVIRONMENT", "staging"))
    parser.add_argument("--matrix", default=os.environ.get("TIJARA_LOAD_PROFILE_MATRIX", "deploy/config/load-profile-matrix.json"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_LOAD_MATRIX_OUTPUT", ""))
    parser.add_argument("--approved-by", default=os.environ.get("TIJARA_LOAD_MATRIX_APPROVED_BY", ""))
    parser.add_argument("--approval-reference", default=os.environ.get("TIJARA_LOAD_MATRIX_APPROVAL_REF", ""))
    parser.add_argument("--non-strict", action="store_true", default=_truthy(os.environ.get("TIJARA_LOAD_MATRIX_NON_STRICT", "1")))
    parser.add_argument("--strict", action="store_true", help="Fail when load matrix approval or profile validation is missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/load-profile-matrix" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    try:
        matrix, matrix_path = _load_matrix(args.matrix)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    rows = []
    blockers = []
    warnings = []
    profiles = matrix.get("profiles") or []
    if not profiles:
        blockers.append("Load profile matrix has no profiles.")
        rows.append(_row("profile-count", "failed", "No profiles are configured."))
    else:
        rows.append(_row("profile-count", "passed", "%s profile(s) configured." % len(profiles)))

    profile_reviews = [_profile_review(profile) for profile in profiles]
    codes = [review["code"] for review in profile_reviews]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        blockers.append("Duplicate profile codes: %s" % ", ".join(duplicates))
        rows.append(_row("profile-code-uniqueness", "failed", "Duplicate profile codes found."))
    else:
        rows.append(_row("profile-code-uniqueness", "passed", "Profile codes are unique."))

    for review in profile_reviews:
        for blocker in review["blockers"]:
            blockers.append("%s: %s" % (review["code"], blocker))
        for warning in review["warnings"]:
            warnings.append("%s: %s" % (review["code"], warning))
        if review["blockers"]:
            rows.append(_row("profile-%s" % review["code"], "failed", "; ".join(review["blockers"])))
        elif review["warnings"]:
            rows.append(_row("profile-%s" % review["code"], "warning", "; ".join(review["warnings"])))
        else:
            rows.append(_row("profile-%s" % review["code"], "passed", "Profile is valid."))

    if args.approved_by and args.approval_reference:
        rows.append(_row("release-approval", "passed", "Load matrix approval is recorded."))
    else:
        message = "Load matrix approval owner and reference are required for production release."
        if args.non_strict:
            warnings.append(message)
            rows.append(_row("release-approval", "warning", message))
        else:
            blockers.append(message)
            rows.append(_row("release-approval", "failed", message))

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
        "matrix_path": matrix_path,
        "approved_by": args.approved_by,
        "approval_reference": args.approval_reference,
        "generated_at": _utc_now(),
        "output": str(output),
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "matrix_version": matrix.get("version"),
        "description": matrix.get("description", ""),
        "profile_count": len(profile_reviews),
        "profiles": profile_reviews,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "matrix=%s" % matrix_path,
            "profile_count=%s" % len(profile_reviews),
            "approved_by_present=%s" % int(bool(args.approved_by)),
            "approval_reference_present=%s" % int(bool(args.approval_reference)),
            "non_strict=%s" % int(args.non_strict),
        ]
    )
    _write(output / "load-profile-matrix.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, profile_reviews, decision, blockers, warnings))

    print("Load profile matrix evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
