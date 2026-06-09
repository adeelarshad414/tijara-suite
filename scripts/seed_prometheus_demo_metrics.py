#!/usr/bin/env python3
"""Seed dummy Tijara business metrics into Pushgateway for Grafana demos."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT_DIR / "deploy/monitoring/tijara-delivery-metrics.example.prom"
REQUIRED_METRICS = [
    "up",
    "probe_success",
    "probe_duration_seconds",
    "tijara_ecommerce_orders_total",
    "tijara_ecommerce_order_amount_pkr",
    "tijara_ecommerce_delivery_orders_total",
    "tijara_delivery_open_exceptions",
    "tijara_delivery_retry_pending",
    "tijara_delivery_retry_oldest_seconds",
    "tijara_delivery_sla_breach_rate_percent",
    "tijara_delivery_webhook_failures_total",
    "tijara_delivery_cod_variance_amount",
    "tijara_payment_events_total",
    "tijara_payment_settlement_variance_pkr",
    "tijara_fbr_queue_total",
    "tijara_hardware_devices_total",
    "tijara_hardware_certifications_total",
    "tijara_external_assumption_mode",
]
METRIC_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+(.+)$")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("prom-demo-%Y%m%dT%H%M%SZ")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _resolve(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _metric_names(payload: str) -> set[str]:
    names: set[str] = set()
    for line in payload.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = METRIC_RE.match(stripped)
        if match:
            names.add(match.group(1))
    return names


def _split_labels(labels: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    escaped = False
    for char in labels:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            current.append(char)
            continue
        if char == "," and not in_quote:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _remove_job_label(labels: str) -> tuple[str, str]:
    job = ""
    kept: list[str] = []
    for part in _split_labels(labels):
        key, _, value = part.partition("=")
        if key.strip() == "job":
            job = value.strip().strip('"')
            continue
        kept.append(part)
    return ",".join(kept), job


def _group_payloads(payload: str, default_job: str) -> dict[str, str]:
    groups: dict[str, list[str]] = {}
    comments: list[str] = [
        "# Seeded by scripts/seed_prometheus_demo_metrics.py.",
        "# Dummy/assumed metrics for dashboard demonstration only.",
    ]
    for line in payload.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            comments.append(stripped)
            continue
        match = METRIC_RE.match(stripped)
        if not match:
            groups.setdefault(default_job, []).append(stripped)
            continue
        name, labels, value = match.groups()
        job = default_job
        rendered_labels = labels or ""
        if labels:
            rendered_labels, parsed_job = _remove_job_label(labels)
            if parsed_job:
                job = parsed_job
        sample = name
        if rendered_labels:
            sample += "{%s}" % rendered_labels
        sample += " " + value.strip()
        groups.setdefault(job, []).append(sample)
    return {
        job: "\n".join(comments + sorted(lines)) + "\n"
        for job, lines in sorted(groups.items())
        if lines
    }


def _push_group(base_url: str, job: str, payload: str, timeout: float) -> dict:
    encoded_job = urllib.parse.quote(job, safe="")
    url = "%s/metrics/job/%s" % (base_url.rstrip("/"), encoded_job)
    request = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {
            "job": job,
            "url": url,
            "status_code": response.getcode(),
            "bytes": len(payload.encode("utf-8")),
        }


def _status_tsv(rows: list[dict]) -> str:
    lines = ["check\tstatus\tmessage\tsource"]
    lines.extend(
        "%s\t%s\t%s\t%s" % (row["name"], row["status"], row["message"], row.get("source", ""))
        for row in rows
    )
    return "\n".join(lines)


def _summary(context: dict, rows: list[dict], blockers: list[str], warnings: list[str], groups: dict[str, str]) -> str:
    row_lines = "\n".join("- %s: %s - %s" % (row["name"], row["status"], row["message"]) for row in rows)
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    warning_lines = "\n".join("- %s" % item for item in warnings) or "- None"
    group_lines = "\n".join("- %s: %s sample line(s)" % (job, len(payload.splitlines())) for job, payload in groups.items())
    return f"""
# Prometheus Demo Metrics Seed

- Decision: {context["decision"]}
- CI status: {context["ci_status"]}
- Run ID: {context["run_id"]}
- Target environment: {context["target_environment"]}
- Pushgateway URL: {context["pushgateway_url"]}
- Dry run: {context["dry_run"]}
- Generated: {context["generated_at"]}
- Output: {context["output"]}

## Groups

{group_lines or "- No groups generated."}

## Checks

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Evidence Files

- Demo metrics seed manifest: demo-metrics-seed.json
- Status table: status.tsv
- Metrics payload copy: metrics.prom
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Push dummy Tijara metrics to Pushgateway for Grafana demos.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_DEMO_METRICS_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_DEMO_METRICS_ENVIRONMENT", "staging-demo"))
    parser.add_argument("--metrics-file", default=os.environ.get("TIJARA_DEMO_METRICS_FILE", str(DEFAULT_METRICS)))
    parser.add_argument("--pushgateway-url", default=os.environ.get("TIJARA_PUSHGATEWAY_URL", "http://localhost:9091"))
    parser.add_argument("--output", default=os.environ.get("TIJARA_DEMO_METRICS_OUTPUT", ""))
    parser.add_argument("--job", default=os.environ.get("TIJARA_DEMO_METRICS_JOB", "tijara-demo-business"))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIJARA_DEMO_METRICS_TIMEOUT", "8")))
    parser.add_argument("--dry-run", action="store_true", default=os.environ.get("TIJARA_DEMO_METRICS_DRY_RUN", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--non-strict", action="store_true", default=os.environ.get("TIJARA_DEMO_METRICS_NON_STRICT", "").lower() in {"1", "true", "yes"})
    args = parser.parse_args()

    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/prometheus-demo-metrics" / args.run_id
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    metrics_file = _resolve(args.metrics_file)
    rows: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []
    pushes: list[dict] = []

    if not metrics_file.is_file():
        message = "Metrics file does not exist: %s" % metrics_file
        blockers.append(message)
        rows.append({"name": "metrics-file", "status": "failed", "message": message, "source": str(metrics_file)})
        payload = ""
    else:
        payload = metrics_file.read_text(encoding="utf-8")
        rows.append({"name": "metrics-file", "status": "passed", "message": "Metrics file loaded.", "source": _repo_relative(metrics_file)})
        shutil.copyfile(metrics_file, output / "metrics.prom")

    names = _metric_names(payload)
    missing = [name for name in REQUIRED_METRICS if name not in names]
    if missing:
        message = "Required demo metric(s) missing: %s" % ", ".join(missing)
        blockers.append(message)
        rows.append({"name": "required-metrics", "status": "failed", "message": message, "source": _repo_relative(metrics_file)})
    else:
        rows.append({"name": "required-metrics", "status": "passed", "message": "%s required metric family/families found." % len(REQUIRED_METRICS), "source": _repo_relative(metrics_file)})

    groups = _group_payloads(payload, args.job) if payload else {}
    if groups:
        rows.append({"name": "pushgateway-groups", "status": "passed", "message": "%s Pushgateway group(s) generated." % len(groups), "source": args.pushgateway_url})
    else:
        message = "No pushable metric groups were generated."
        blockers.append(message)
        rows.append({"name": "pushgateway-groups", "status": "failed", "message": message, "source": args.pushgateway_url})

    if not blockers and not args.dry_run:
        for job, group_payload in groups.items():
            try:
                result = _push_group(args.pushgateway_url, job, group_payload, args.timeout)
            except Exception as error:  # noqa: BLE001 - operator evidence needs exact external failure text.
                message = "Pushgateway PUT failed for job %s: %s" % (job, error)
                if args.non_strict:
                    warnings.append(message)
                    rows.append({"name": "pushgateway-%s" % job, "status": "warning", "message": message, "source": args.pushgateway_url})
                else:
                    blockers.append(message)
                    rows.append({"name": "pushgateway-%s" % job, "status": "failed", "message": message, "source": args.pushgateway_url})
            else:
                pushes.append(result)
                rows.append({"name": "pushgateway-%s" % job, "status": "passed", "message": "PUT returned HTTP %s." % result["status_code"], "source": result["url"]})
    elif args.dry_run:
        rows.append({"name": "pushgateway-publish", "status": "skipped", "message": "Dry run requested; metrics were not pushed.", "source": args.pushgateway_url})

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
        "output": _repo_relative(output),
        "metrics_file": _repo_relative(metrics_file),
        "pushgateway_url": args.pushgateway_url,
        "dry_run": bool(args.dry_run),
        "decision": decision,
        "ci_status": ci_status,
    }
    manifest = {
        "context": context,
        "decision": decision,
        "ci_status": ci_status,
        "checks": rows,
        "blockers": blockers,
        "warnings": warnings,
        "required_metrics": REQUIRED_METRICS,
        "present_metrics": sorted(names),
        "groups": [
            {"job": job, "sample_lines": len(group_payload.splitlines()), "bytes": len(group_payload.encode("utf-8"))}
            for job, group_payload in groups.items()
        ],
        "pushes": pushes,
    }
    _write(output / "demo-metrics-seed.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "summary.md", _summary(context, rows, blockers, warnings, groups))
    print("Prometheus demo metrics evidence written to %s" % output)
    print("decision=%s" % decision)
    print("ci_status=%s" % ci_status)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
