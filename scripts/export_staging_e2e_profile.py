#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

PUBLIC_REQUIRED = [
    "ODOO_BASE_URL",
    "TIJARA_DISPLAY_SLUG",
    "TIJARA_KIOSK_SLUG",
    "TIJARA_CUSTOMER_DISPLAY_SLUG",
]

AUTHENTICATED_REQUIRED = [
    "ODOO_BASE_URL",
    "ODOO_USERNAME",
    "ODOO_PASSWORD",
    "ODOO_DATABASE",
    "TIJARA_POS_CONFIG_ID",
    "TIJARA_E2E_PRODUCT_ID",
    "TIJARA_E2E_PAYMENT_METHOD_ID",
    "TIJARA_E2E_REFUND_REASON_ID",
    "TIJARA_E2E_REFUND_BARCODE",
    "TIJARA_REFUND_ACTION_URL",
    "TIJARA_REPORT_ORDER_URL",
    "TIJARA_OFFLINE_QUEUE_ACTION_URL",
]

OPTIONAL_FLAG_REQUIREMENTS = {
    "TIJARA_RUN_DIRECT_POS_CLICKTHROUGH": [
        "TIJARA_POS_CONFIG_ID",
        "TIJARA_E2E_PRODUCT_NAME",
    ],
    "TIJARA_RUN_DIRECT_POS_VALIDATE_E2E": [
        "TIJARA_POS_CONFIG_ID",
        "TIJARA_E2E_PRODUCT_NAME",
        "TIJARA_E2E_PAYMENT_METHOD_ID",
    ],
    "TIJARA_RUN_DIRECT_REFUND_FORM_E2E": [
        "TIJARA_REFUND_ACTION_URL",
        "TIJARA_E2E_REFUND_BARCODE",
    ],
    "TIJARA_RUN_MOBILE_OFFLINE_E2E": [
        "TIJARA_OFFLINE_QUEUE_ACTION_URL",
    ],
}

SELECTED_SPECS = {
    "public": ["tests/e2e/display-kiosk.spec.mjs"],
    "authenticated": [
        "tests/e2e/pos-checkout-print.spec.mjs",
        "tests/e2e/pos-enterprise-journey.spec.mjs",
        "tests/e2e/pos-direct-ui-clickthrough.spec.mjs",
        "tests/e2e/refunds-reports.spec.mjs",
    ],
    "full": [
        "tests/e2e/display-kiosk.spec.mjs",
        "tests/e2e/pos-checkout-print.spec.mjs",
        "tests/e2e/pos-enterprise-journey.spec.mjs",
        "tests/e2e/pos-direct-ui-clickthrough.spec.mjs",
        "tests/e2e/refunds-reports.spec.mjs",
    ],
}

OPERATOR_REFERENCES = [
    "TIJARA_E2E_OWNER",
    "TIJARA_E2E_RUNBOOK_REF",
    "TIJARA_E2E_CHANGE_REF",
]

SECRET_KEY_PARTS = {"password", "secret", "token", "api_key", "apikey", "client_secret"}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _secret_like(name):
    normalized = str(name or "").lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _safe_value(name, value):
    if not value:
        return "<missing>"
    if _secret_like(name):
        return "<set>"
    return str(value)


def _row(name, status, message, source=""):
    return {"name": name, "status": status, "message": message, "source": source}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _unquote_shell_value(value):
    text = str(value or "").strip()
    try:
        parts = shlex.split("x=%s" % text, posix=True)
    except ValueError:
        return text
    if len(parts) == 1 and parts[0].startswith("x="):
        return parts[0][2:]
    return text


def _parse_env_exports(path):
    exports = {}
    if not path or not path.is_file():
        return exports
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith("export "):
            continue
        assignment = stripped[len("export ") :].strip()
        if "=" not in assignment:
            continue
        name, value = assignment.split("=", 1)
        name = name.strip()
        if name and name.replace("_", "").isalnum():
            exports[name] = _unquote_shell_value(value)
    return exports


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _selected_required(scope):
    if scope == "public":
        return list(PUBLIC_REQUIRED)
    if scope == "authenticated":
        return list(AUTHENTICATED_REQUIRED)
    return list(dict.fromkeys(PUBLIC_REQUIRED + AUTHENTICATED_REQUIRED))


def _is_local_url(parsed):
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")


def _base_url_checks(base_url, strict):
    rows = []
    blockers = []
    warnings = []
    if not base_url:
        message = "ODOO_BASE_URL is required for staging browser E2E."
        rows.append(_row("base-url", "failed", message))
        blockers.append(message)
        return rows, blockers, warnings

    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        message = "ODOO_BASE_URL must be an absolute http(s) URL."
        rows.append(_row("base-url", "failed", message))
        blockers.append(message)
        return rows, blockers, warnings

    rows.append(_row("base-url", "passed", "Base URL is absolute."))
    if parsed.scheme == "https":
        rows.append(_row("base-url-scheme", "passed", "Base URL uses HTTPS."))
    elif _is_local_url(parsed):
        rows.append(_row("base-url-scheme", "passed", "HTTP is allowed for localhost staging drills."))
    else:
        message = "Non-local staging E2E should use HTTPS."
        rows.append(_row("base-url-scheme", "failed" if strict else "warning", message))
        if strict:
            blockers.append(message)
        else:
            warnings.append(message)
    return rows, blockers, warnings


def _probe_login(base_url, timeout):
    target = base_url.rstrip("/") + "/web/login"
    request = urllib.request.Request(target, headers={"User-Agent": "tijara-e2e-profile/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.geturl()


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage\tsource"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s"
            % (row["name"], row["status"], row["message"], row.get("source") or "")
        )
    return "\n".join(lines)


def _env_summary(context, variables, operator_refs):
    lines = [
        "run_id=%s" % context["run_id"],
        "scope=%s" % context["scope"],
        "base_url=%s" % context["base_url"],
        "target_environment=%s" % context["target_environment"],
        "output=%s" % context["output"],
        "strict=%s" % context["strict"],
        "probe_base_url=%s" % context["probe_base_url"],
        "seed_env=%s" % (context["seed_env"] or "<unset>"),
        "seed_evidence=%s" % (context["seed_evidence"] or "<unset>"),
    ]
    for item in variables:
        lines.append("%s=%s" % (item["name"], item["safe_value"]))
    for item in operator_refs:
        lines.append("%s=%s" % (item["name"], item["safe_value"]))
    return "\n".join(lines)


def _summary(context, rows, blockers, warnings):
    status = "blocked" if blockers else "warning" if warnings else "ready"
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Staging E2E Profile Evidence

- Status: {status}
- Run ID: {context["run_id"]}
- Scope: {context["scope"]}
- Target environment: {context["target_environment"]}
- Base URL: {context["base_url"]}
- Strict: {context["strict"]}
- Probe base URL: {context["probe_base_url"]}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Profile manifest: staging-e2e-profile.json
- Environment summary: env-summary.txt
- Status table: status.tsv
"""


def main():
    parser = argparse.ArgumentParser(
        description="Export Tijara live staging browser E2E profile evidence."
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_E2E_PROFILE_RUN_ID", ""))
    parser.add_argument("--scope", default=os.environ.get("TIJARA_E2E_SCOPE", "full"))
    parser.add_argument("--base-url", default=os.environ.get("ODOO_BASE_URL", ""))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_E2E_PROFILE_ENVIRONMENT", "staging"),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("TIJARA_E2E_PROFILE_OUTPUT", ""),
        help="Directory for profile evidence.",
    )
    parser.add_argument("--seed-env", default=os.environ.get("TIJARA_E2E_SEED_ENV", ""))
    parser.add_argument(
        "--seed-evidence",
        default=os.environ.get("TIJARA_E2E_SEED_EVIDENCE", ""),
    )
    parser.add_argument(
        "--require-seed",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_E2E_PROFILE_REQUIRE_SEED")),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_E2E_PROFILE_STRICT")),
        help="Block on missing operator references and non-local HTTP URLs.",
    )
    parser.add_argument(
        "--probe-base-url",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_E2E_PROFILE_PROBE_BASE_URL")),
        help="Probe Odoo /web/login and block if unreachable.",
    )
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=float(os.environ.get("TIJARA_E2E_PROFILE_PROBE_TIMEOUT", "8")),
    )
    args = parser.parse_args()

    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/e2e-profile" / run_id
    output.mkdir(parents=True, exist_ok=True)

    seed_env_path = Path(args.seed_env) if args.seed_env else None
    seed_evidence_path = Path(args.seed_evidence) if args.seed_evidence else None
    seed_exports = _parse_env_exports(seed_env_path) if seed_env_path else {}
    values = dict(seed_exports)
    for name, value in os.environ.items():
        if value:
            values[name] = value
    if args.base_url:
        values["ODOO_BASE_URL"] = args.base_url
    base_url = values.get("ODOO_BASE_URL", "")

    rows = []
    blockers = []
    warnings = []

    if args.scope not in SELECTED_SPECS:
        message = "Unsupported E2E profile scope: %s." % args.scope
        rows.append(_row("scope", "failed", message))
        blockers.append(message)
    else:
        rows.append(_row("scope", "passed", "Scope %s is supported." % args.scope))

    base_rows, base_blockers, base_warnings = _base_url_checks(base_url, args.strict)
    rows.extend(base_rows)
    blockers.extend(base_blockers)
    warnings.extend(base_warnings)

    if seed_env_path:
        if seed_env_path.is_file():
            rows.append(_row("seed-env", "passed", "Seed env file exists.", str(seed_env_path)))
        else:
            message = "Seed env file was configured but not found."
            rows.append(_row("seed-env", "failed" if args.require_seed else "warning", message, str(seed_env_path)))
            if args.require_seed:
                blockers.append(message)
            else:
                warnings.append(message)
    elif args.require_seed:
        message = "Seed env file is required for this E2E profile."
        rows.append(_row("seed-env", "failed", message))
        blockers.append(message)
    else:
        rows.append(_row("seed-env", "passed", "No seed env file configured; using direct environment values."))

    seed_evidence = {}
    if seed_evidence_path:
        if seed_evidence_path.is_file():
            seed_evidence = _read_json(seed_evidence_path)
            decision = str(seed_evidence.get("decision") or "").lower()
            if decision in {"ready", "warning"}:
                rows.append(_row("seed-evidence", "passed", "Seed evidence decision is %s." % decision, str(seed_evidence_path)))
            elif decision:
                message = "Seed evidence decision is %s." % decision
                rows.append(_row("seed-evidence", "failed", message, str(seed_evidence_path)))
                blockers.append(message)
            else:
                message = "Seed evidence JSON has no decision."
                rows.append(_row("seed-evidence", "warning", message, str(seed_evidence_path)))
                warnings.append(message)
        else:
            message = "Seed evidence file was configured but not found."
            rows.append(_row("seed-evidence", "failed" if args.require_seed else "warning", message, str(seed_evidence_path)))
            if args.require_seed:
                blockers.append(message)
            else:
                warnings.append(message)
    elif args.require_seed:
        message = "Seed evidence JSON is required for this E2E profile."
        rows.append(_row("seed-evidence", "failed", message))
        blockers.append(message)
    else:
        rows.append(_row("seed-evidence", "passed", "No seed evidence JSON configured; using direct environment values."))

    required = _selected_required(args.scope if args.scope in SELECTED_SPECS else "full")
    variable_reviews = []
    for name in required:
        value = values.get(name, "")
        present = bool(str(value).strip())
        review = {
            "name": name,
            "present": present,
            "safe_value": _safe_value(name, value),
            "secret_like": _secret_like(name),
            "source": "environment" if os.environ.get(name) else "seed-env" if seed_exports.get(name) else "",
        }
        variable_reviews.append(review)
        if present:
            rows.append(_row("env:%s" % name, "passed", "%s is present." % name, review["source"]))
        else:
            message = "%s is required for %s staging E2E." % (name, args.scope)
            rows.append(_row("env:%s" % name, "failed", message))
            blockers.append(message)

    operator_reviews = []
    for name in OPERATOR_REFERENCES:
        value = values.get(name, "")
        present = bool(str(value).strip())
        operator_reviews.append(
            {
                "name": name,
                "present": present,
                "safe_value": _safe_value(name, value),
            }
        )
        if present:
            rows.append(_row("operator:%s" % name, "passed", "%s is set." % name))
        else:
            message = "%s should be set for live staging E2E ownership." % name
            rows.append(_row("operator:%s" % name, "failed" if args.strict else "warning", message))
            if args.strict:
                blockers.append(message)
            else:
                warnings.append(message)

    specs = SELECTED_SPECS.get(args.scope) or SELECTED_SPECS["full"]
    spec_reviews = []
    for spec in specs:
        path = ROOT_DIR / spec
        exists = path.is_file()
        spec_reviews.append({"path": spec, "exists": exists})
        if exists:
            rows.append(_row("spec:%s" % spec, "passed", "Playwright spec exists.", spec))
        else:
            message = "Playwright spec is missing: %s." % spec
            rows.append(_row("spec:%s" % spec, "failed", message, spec))
            blockers.append(message)

    playwright_config = ROOT_DIR / "playwright.config.mjs"
    package_json = ROOT_DIR / "package.json"
    if playwright_config.is_file():
        rows.append(_row("playwright-config", "passed", "playwright.config.mjs exists."))
    else:
        message = "playwright.config.mjs is missing."
        rows.append(_row("playwright-config", "failed", message))
        blockers.append(message)
    if package_json.is_file():
        package = _read_json(package_json)
        scripts = package.get("scripts") or {}
        if "test:e2e:staging" in scripts:
            rows.append(_row("package-e2e-script", "passed", "npm staging E2E script is configured."))
        else:
            message = "package.json has no test:e2e:staging script."
            rows.append(_row("package-e2e-script", "warning", message))
            warnings.append(message)
    else:
        message = "package.json is missing."
        rows.append(_row("package-json", "failed", message))
        blockers.append(message)

    optional_flags = []
    for flag, requirements in OPTIONAL_FLAG_REQUIREMENTS.items():
        enabled = _truthy(values.get(flag, ""))
        missing = [name for name in requirements if not str(values.get(name, "")).strip()]
        optional_flags.append({"name": flag, "enabled": enabled, "missing_variables": missing})
        if not enabled:
            rows.append(_row("flag:%s" % flag, "passed", "%s is not enabled; optional prerequisites not required." % flag))
        elif missing:
            message = "%s is enabled but missing %s." % (flag, ", ".join(missing))
            rows.append(_row("flag:%s" % flag, "failed", message))
            blockers.append(message)
        else:
            rows.append(_row("flag:%s" % flag, "passed", "%s prerequisites are present." % flag))

    probe_result = {"enabled": bool(args.probe_base_url), "status": "skipped"}
    if args.probe_base_url:
        try:
            status_code, final_url = _probe_login(base_url, args.probe_timeout)
            probe_result.update({"status": "passed", "status_code": status_code, "final_url": final_url})
            rows.append(_row("probe-web-login", "passed", "Odoo login responded with HTTP %s." % status_code))
        except (OSError, urllib.error.URLError, ValueError) as error:
            message = "Odoo login probe failed: %s" % error
            probe_result.update({"status": "failed", "error": str(error)})
            rows.append(_row("probe-web-login", "failed", message))
            blockers.append(message)
    else:
        rows.append(_row("probe-web-login", "passed", "Base URL probe not requested for this profile run."))

    if blockers:
        decision = "blocked"
        ci_status = "fail"
    elif warnings:
        decision = "warning"
        ci_status = "pass_with_warnings"
    else:
        decision = "ready"
        ci_status = "pass"

    context = {
        "run_id": run_id,
        "scope": args.scope,
        "target_environment": args.target_environment,
        "base_url": base_url,
        "strict": bool(args.strict),
        "probe_base_url": bool(args.probe_base_url),
        "generated_at": _utc_now(),
        "output": str(output),
        "seed_env": str(seed_env_path) if seed_env_path else "",
        "seed_evidence": str(seed_evidence_path) if seed_evidence_path else "",
    }
    payload = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "required_variables": variable_reviews,
        "operator_references": operator_reviews,
        "specs": spec_reviews,
        "optional_flags": optional_flags,
        "seed_evidence_decision": seed_evidence.get("decision", "") if seed_evidence else "",
        "probe_result": probe_result,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
    }

    _write(output / "staging-e2e-profile.json", json.dumps(payload, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", _env_summary(context, variable_reviews, operator_reviews))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings))

    print("Staging E2E profile evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("blockers=%s" % len(blockers))
    if warnings:
        print("warnings=%s" % len(warnings))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
