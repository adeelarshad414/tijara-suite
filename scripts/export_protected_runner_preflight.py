#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "client_secret",
    "integrity_salt",
    "encryption_key",
}
PLACEHOLDER_MARKERS = ("replace-with", "change-me", "example", "dummy")

CORE_REQUIRED_VARIABLES = [
    ("TIJARA_TARGET_ENVIRONMENT", "Target environment"),
    ("TIJARA_PROTECTED_RUN_ID", "Protected evidence run ID"),
    ("TIJARA_PROTECTED_RELEASE_CHECKS", "Protected release check scope"),
    ("TIJARA_PROTECTED_REQUIRED_EVIDENCE_GROUPS", "Required sign-off evidence groups"),
    ("TIJARA_ARTIFACT_STORE_REFERENCE", "Release artifact store reference"),
    ("TIJARA_ARTIFACT_RETENTION_POLICY_REF", "Artifact retention policy reference"),
    ("TIJARA_CERTIFICATION_RETENTION_POLICY_REF", "Certification retention policy reference"),
    ("TIJARA_SECRET_MANAGER_PROVIDER", "Secret manager provider"),
    ("TIJARA_SECRET_MANAGER_REFERENCE", "Secret manager reference"),
    ("TIJARA_SECRET_ROTATION_POLICY_REF", "Secret rotation policy reference"),
    ("TIJARA_SECRET_ACCESS_REVIEW_REF", "Secret access review reference"),
    ("TIJARA_RESTORE_DRILL_BACKUP", "Restore drill backup path"),
    ("TIJARA_BACKUP_ARTIFACT_REF", "Backup artifact reference"),
]

OBSERVED_VARIABLES = [
    "TIJARA_BASE_URL",
    "ODOO_BASE_URL",
    "TIJARA_HARDWARE_BRIDGE_URL",
    "TIJARA_PROMETHEUS_URL",
    "TIJARA_ALERTMANAGER_URL",
    "TIJARA_GRAFANA_URL",
    "ODOO_IMAGE",
    "POSTGRES_IMAGE",
    "TIJARA_E2E_SCOPE",
    "TIJARA_RUN_POS_UI_E2E",
    "TIJARA_RUN_DIRECT_POS_CLICKTHROUGH",
    "TIJARA_RUN_DIRECT_POS_VALIDATE_E2E",
    "TIJARA_RUN_DIRECT_REFUND_FORM_E2E",
    "TIJARA_RUN_MOBILE_OFFLINE_E2E",
    "TIJARA_LOAD_VUS",
    "TIJARA_LOAD_DURATION",
    "TIJARA_LOAD_MAX_P95_MS",
    "TIJARA_LOAD_MAX_FAIL_RATE",
    "TIJARA_LOAD_MIN_CHECKS_RATE",
]

CERTIFICATION_REQUIREMENTS = {
    "psp": [
        ("TIJARA_CERT_PSP_PROVIDER", "PSP provider"),
        ("TIJARA_CERT_PSP_REFERENCE", "PSP certification reference"),
        ("TIJARA_CERT_PSP_OWNER", "PSP evidence owner"),
        ("TIJARA_CERT_PSP_ARTIFACT_MANIFEST", "PSP artifact manifest"),
        ("TIJARA_CERT_PSP_APPROVED_BY", "PSP approval owner"),
        ("TIJARA_CERT_PSP_APPROVAL_REFERENCE", "PSP approval reference"),
        ("TIJARA_CERT_PSP_VALID_UNTIL", "PSP evidence validity date"),
    ],
    "fbr": [
        ("TIJARA_CERT_FBR_PROVIDER", "FBR certified provider"),
        ("TIJARA_CERT_FBR_REFERENCE", "FBR certification reference"),
        ("TIJARA_CERT_FBR_OWNER", "FBR evidence owner"),
        ("TIJARA_CERT_FBR_ARTIFACT_MANIFEST", "FBR artifact manifest"),
        ("TIJARA_CERT_FBR_APPROVED_BY", "FBR approval owner"),
        ("TIJARA_CERT_FBR_APPROVAL_REFERENCE", "FBR approval reference"),
        ("TIJARA_CERT_FBR_VALID_UNTIL", "FBR evidence validity date"),
    ],
    "hardware": [
        ("TIJARA_CERT_HARDWARE_OWNER", "Hardware evidence owner"),
        ("TIJARA_CERT_HARDWARE_STORE", "Hardware store or branch"),
        ("TIJARA_CERT_HARDWARE_DEVICE_MODEL", "Hardware device model"),
        ("TIJARA_CERT_HARDWARE_DEVICE_SERIAL", "Hardware device serial"),
        ("TIJARA_CERT_HARDWARE_ARTIFACT_MANIFEST", "Hardware artifact manifest"),
        ("TIJARA_CERT_HARDWARE_APPROVED_BY", "Hardware approval owner"),
        ("TIJARA_CERT_HARDWARE_APPROVAL_REFERENCE", "Hardware approval reference"),
        ("TIJARA_CERT_HARDWARE_VALID_UNTIL", "Hardware evidence validity date"),
    ],
}

CERTIFICATION_OPTIONAL_VARIABLES = {
    "psp": [
        "TIJARA_CERT_PSP_EVIDENCE_FILES",
        "TIJARA_CERT_PSP_EXPECTED_SHA256",
        "TIJARA_CERT_PSP_MINIMUM_EVIDENCE_FILES",
        "TIJARA_CERT_PSP_METADATA",
    ],
    "fbr": [
        "TIJARA_CERT_FBR_EVIDENCE_FILES",
        "TIJARA_CERT_FBR_EXPECTED_SHA256",
        "TIJARA_CERT_FBR_MINIMUM_EVIDENCE_FILES",
        "TIJARA_CERT_FBR_METADATA",
    ],
    "hardware": [
        "TIJARA_CERT_HARDWARE_EVIDENCE_FILES",
        "TIJARA_CERT_HARDWARE_EXPECTED_SHA256",
        "TIJARA_CERT_HARDWARE_MINIMUM_EVIDENCE_FILES",
        "TIJARA_CERT_HARDWARE_METADATA",
    ],
}

URL_PROBE_SPECS = [
    {
        "name": "odoo-login",
        "env": "ODOO_BASE_URL",
        "fallback_env": "TIJARA_BASE_URL",
        "path": "/web/login",
        "label": "Odoo login",
    },
    {
        "name": "hardware-bridge-health",
        "env": "TIJARA_HARDWARE_BRIDGE_URL",
        "path": "/health",
        "label": "Hardware bridge health",
    },
    {
        "name": "prometheus-ready",
        "env": "TIJARA_PROMETHEUS_URL",
        "path": "/-/ready",
        "label": "Prometheus readiness",
    },
    {
        "name": "alertmanager-ready",
        "env": "TIJARA_ALERTMANAGER_URL",
        "path": "/-/ready",
        "label": "Alertmanager readiness",
    },
    {
        "name": "grafana-health",
        "env": "TIJARA_GRAFANA_URL",
        "path": "/api/health",
        "label": "Grafana health",
    },
]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_items(value):
    return [item.strip().lower() for item in str(value or "").split(",") if item.strip()]


def _present(value):
    return bool(str(value or "").strip())


def _is_secret_key(key):
    normalized = str(key or "").lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _is_placeholder(value):
    text = str(value or "").strip().lower()
    return bool(text) and any(marker in text for marker in PLACEHOLDER_MARKERS)


def _value_preview(key, value, include_values):
    if not _present(value):
        return "<unset>"
    if _is_secret_key(key):
        return "<redacted>"
    if not include_values:
        return "<present>"
    text = str(value).strip()
    return text if len(text) <= 96 else text[:93] + "..."


def _redact_url(value):
    if not _present(value):
        return "<unset>"
    try:
        parsed = urlsplit(str(value).strip())
    except ValueError:
        return "<invalid-url>"
    if not parsed.scheme or not parsed.netloc:
        return "<invalid-url>"
    hostname = parsed.hostname or ""
    netloc = hostname
    if parsed.port:
        netloc = "%s:%s" % (hostname, parsed.port)
    return urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))


def _probe_url(base_url, path, timeout):
    if not _present(base_url) or _is_placeholder(base_url):
        return None, "missing"
    try:
        parsed = urlsplit(str(base_url).strip())
    except ValueError:
        return None, "invalid"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "invalid"
    normalized_path = (parsed.path or "").rstrip("/")
    if path:
        normalized_path = normalized_path + "/" + path.lstrip("/")
    target = urlunsplit((parsed.scheme, parsed.netloc, normalized_path or "/", "", ""))
    request = urllib.request.Request(target, headers={"User-Agent": "tijara-preflight/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 0) or response.getcode() or 0)
            return {
                "url": _redact_url(target),
                "status_code": status_code,
                "reachable": 200 <= status_code < 400,
                "error": "",
            }, "ok"
    except urllib.error.HTTPError as error:
        return {
            "url": _redact_url(target),
            "status_code": int(error.code),
            "reachable": 200 <= int(error.code) < 400,
            "error": str(error.reason or ""),
        }, "http-error"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        return {
            "url": _redact_url(target),
            "status_code": 0,
            "reachable": False,
            "error": str(reason),
        }, "error"


def _row(name, status, message):
    return {"name": name, "status": status, "message": message}


def _status_tsv(rows):
    lines = ["check\tstatus\tmessage"]
    lines.extend("%s\t%s\t%s" % (row["name"], row["status"], row["message"]) for row in rows)
    return "\n".join(lines)


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _add_requirement(rows, blockers, warnings, strict, name, value, label):
    if _present(value) and not _is_placeholder(value):
        rows.append(_row(name, "passed", "%s is configured." % label))
        return
    if _present(value) and _is_placeholder(value):
        message = "%s still contains a placeholder value." % label
    else:
        message = "%s is required for protected release preflight." % label
    if strict:
        blockers.append(message)
        rows.append(_row(name, "failed", message))
    else:
        warnings.append(message)
        rows.append(_row(name, "warning", message))


def _variable_entry(env, key, label, include_values, required):
    value = env.get(key, "")
    return {
        "name": key,
        "label": label,
        "required": bool(required),
        "present": _present(value),
        "placeholder": _is_placeholder(value),
        "secret_like": _is_secret_key(key),
        "value_preview": _value_preview(key, value, include_values),
    }


def _summary(context, rows, decision, blockers, warnings):
    row_lines = "\n".join(
        "- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    return f"""
# Protected Runner Preflight

- Status: {decision}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Certification groups: {context["certification_groups"] or "none"}
- Generated: {context["generated_at"]}
- Output directory: {context["output"]}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Protected runner preflight manifest: protected-runner-preflight.json
- Status table: status.tsv
- Environment summary: env-summary.txt
"""


def main():
    parser = argparse.ArgumentParser(description="Export Tijara protected runner preflight evidence.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument(
        "--target-environment",
        default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"),
    )
    parser.add_argument("--output", default=os.environ.get("TIJARA_PREFLIGHT_OUTPUT", ""))
    parser.add_argument(
        "--certification-groups",
        default=os.environ.get("TIJARA_PROTECTED_CERTIFICATION_GROUPS", ""),
    )
    parser.add_argument("--include-values", action="store_true")
    parser.add_argument(
        "--probe-urls",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PREFLIGHT_PROBE_URLS")),
        help="Probe configured Odoo, bridge, and monitoring URLs without credentials.",
    )
    parser.add_argument(
        "--require-url-probes",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PREFLIGHT_REQUIRE_URLS")),
        help="Treat missing URL probe targets as blockers in strict mode.",
    )
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=float(os.environ.get("TIJARA_PREFLIGHT_PROBE_TIMEOUT", "5")),
        help="Per-URL probe timeout in seconds.",
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_PREFLIGHT_NON_STRICT", "1")),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when required preflight variables are missing.")
    args = parser.parse_args()
    if args.strict:
        args.non_strict = False
    strict = not args.non_strict

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/protected-runner-preflight" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    certification_groups = [
        group for group in dict.fromkeys(_csv_items(args.certification_groups)) if group
    ]
    effective_env = dict(os.environ)
    effective_env.setdefault("TIJARA_PROTECTED_RUN_ID", args.run_id)
    effective_env.setdefault("TIJARA_TARGET_ENVIRONMENT", args.target_environment)
    rows = []
    blockers = []
    warnings = []

    variables = []
    for key, label in CORE_REQUIRED_VARIABLES:
        value = effective_env.get(key, "")
        _add_requirement(rows, blockers, warnings, strict, key.lower(), value, label)
        variables.append(_variable_entry(effective_env, key, label, args.include_values, True))

    for key in OBSERVED_VARIABLES:
        variables.append(_variable_entry(effective_env, key, key, args.include_values, False))

    url_probes = []
    if args.probe_urls:
        rows.append(_row("url-probes-enabled", "passed", "Protected runner URL probes are enabled."))
        for spec in URL_PROBE_SPECS:
            value = effective_env.get(spec["env"], "")
            source_env = spec["env"]
            fallback_env = spec.get("fallback_env")
            if not _present(value) and fallback_env:
                value = effective_env.get(fallback_env, "")
                source_env = fallback_env
            probe, probe_state = _probe_url(value, spec["path"], max(args.probe_timeout, 0.1))
            entry = {
                "name": spec["name"],
                "label": spec["label"],
                "env": source_env,
                "configured": _present(value) and not _is_placeholder(value),
                "required": bool(args.require_url_probes),
                "path": spec["path"],
                "result": probe or {},
            }
            url_probes.append(entry)
            check_name = "url-probe-%s" % spec["name"]
            if probe and probe.get("reachable"):
                rows.append(
                    _row(
                        check_name,
                        "passed",
                        "%s is reachable at %s." % (spec["label"], probe.get("url")),
                    )
                )
            elif probe:
                message = "%s is not reachable at %s: %s" % (
                    spec["label"],
                    probe.get("url"),
                    probe.get("error") or "HTTP %s" % probe.get("status_code"),
                )
                if strict:
                    blockers.append(message)
                    rows.append(_row(check_name, "failed", message))
                else:
                    warnings.append(message)
                    rows.append(_row(check_name, "warning", message))
            else:
                message = "%s URL is not configured for probing." % spec["label"]
                if strict and args.require_url_probes:
                    blockers.append(message)
                    rows.append(_row(check_name, "failed", message))
                else:
                    warnings.append(message)
                    rows.append(_row(check_name, "warning", message))
    else:
        url_probes = []
        rows.append(_row("url-probes-enabled", "passed", "Protected runner URL probes are disabled."))

    certification = {}
    for group, requirements in CERTIFICATION_REQUIREMENTS.items():
        selected = group in certification_groups
        group_entries = []
        if selected:
            rows.append(_row("certification-%s-selected" % group, "passed", "%s certification is required." % group))
        else:
            rows.append(_row("certification-%s-selected" % group, "passed", "%s certification is optional for this run." % group))
        for key, label in requirements:
            value = effective_env.get(key, "")
            if selected:
                _add_requirement(rows, blockers, warnings, strict, key.lower(), value, label)
            group_entries.append(_variable_entry(effective_env, key, label, args.include_values, selected))
        for key in CERTIFICATION_OPTIONAL_VARIABLES[group]:
            group_entries.append(_variable_entry(effective_env, key, key, args.include_values, False))
        certification[group] = {"required": selected, "variables": group_entries}

    unknown_groups = sorted(set(certification_groups) - set(CERTIFICATION_REQUIREMENTS))
    if unknown_groups:
        message = "Unknown certification group(s): %s" % ", ".join(unknown_groups)
        if strict:
            blockers.append(message)
            rows.append(_row("certification-groups", "failed", message))
        else:
            warnings.append(message)
            rows.append(_row("certification-groups", "warning", message))
    else:
        rows.append(_row("certification-groups", "passed", "Certification group list is valid."))

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
        "certification_groups": ",".join(certification_groups),
        "generated_at": _utc_now(),
        "output": str(output),
        "strict": strict,
        "include_values": bool(args.include_values),
        "probe_urls": bool(args.probe_urls),
        "require_url_probes": bool(args.require_url_probes),
        "probe_timeout": args.probe_timeout,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "blockers": blockers,
        "warnings": warnings,
        "checks": rows,
        "variables": variables,
        "url_probes": url_probes,
        "certification": certification,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "target_environment=%s" % args.target_environment,
            "certification_groups=%s" % (",".join(certification_groups) or "<none>"),
            "strict=%s" % int(strict),
            "include_values=%s" % int(args.include_values),
            "probe_urls=%s" % int(args.probe_urls),
            "require_url_probes=%s" % int(args.require_url_probes),
            "probe_timeout=%s" % args.probe_timeout,
            "decision=%s" % decision,
            "ci_status=%s" % ci_status,
        ]
    )
    _write(output / "protected-runner-preflight.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(context, rows, decision, blockers, warnings))

    print("Protected runner preflight evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
