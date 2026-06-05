#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _resolve(path):
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else ROOT_DIR / target


def _repo_relative(path):
    if not path:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def _read_json(path):
    target = _resolve(path)
    if not target:
        return {}, ""
    if not target.is_file():
        return {"_missing": True}, str(target)
    try:
        return json.loads(target.read_text(encoding="utf-8")), str(target)
    except (OSError, json.JSONDecodeError) as error:
        return {"_read_error": str(error)}, str(target)


def _decision(payload):
    if payload.get("_missing"):
        return "missing"
    if payload.get("_read_error"):
        return "error"
    return str(payload.get("decision") or payload.get("status") or payload.get("ci_status") or "unknown")


def _ci_status(payload):
    if payload.get("_missing"):
        return "missing"
    if payload.get("_read_error"):
        return "error"
    return str(payload.get("ci_status") or "unknown")


def _markdown_escape(value):
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _limit(items, limit):
    clean = [str(item or "").strip() for item in items or [] if str(item or "").strip()]
    return clean[:limit], max(len(clean) - limit, 0)


def _verdict_row(label, payload, source):
    return "| %s | %s | %s | `%s` |" % (
        _markdown_escape(label),
        _markdown_escape(_decision(payload)),
        _markdown_escape(_ci_status(payload)),
        _markdown_escape(_repo_relative(Path(source)) if source else ""),
    )


def _ops_component_rows(payload, limit):
    rows = []
    for component in (payload.get("components") or [])[:limit]:
        rows.append(
            "| %s | %s | %s |" % (
                _markdown_escape(component.get("name")),
                _markdown_escape(component.get("status")),
                _markdown_escape(component.get("message")),
            )
        )
    return rows


def _summary_lines(args):
    production_ops, production_ops_source = _read_json(args.production_ops_readiness)
    release_readiness, release_readiness_source = _read_json(args.release_readiness)
    artifact_summary, artifact_summary_source = _read_json(args.artifact_summary)
    post_run, post_run_source = _read_json(args.post_run_verification)

    lines = [
        "# Tijara Protected Release Summary",
        "",
        "- Run ID: `%s`" % args.run_id,
        "- Target environment: `%s`" % args.target_environment,
        "- Generated: `%s`" % _utc_now(),
        "",
        "## Verdicts",
        "",
        "| Evidence | Decision | CI status | Source |",
        "| --- | --- | --- | --- |",
        _verdict_row("Release readiness", release_readiness, release_readiness_source),
        _verdict_row("Production operations readiness", production_ops, production_ops_source),
        _verdict_row("Protected post-run verification", post_run, post_run_source),
        _verdict_row("Protected artifact summary", artifact_summary, artifact_summary_source),
        "",
    ]

    blockers = []
    warnings = []
    for label, payload in [
        ("release-readiness", release_readiness),
        ("production-ops", production_ops),
        ("post-run", post_run),
        ("artifact-summary", artifact_summary),
    ]:
        blockers.extend("%s: %s" % (label, item) for item in payload.get("blockers") or [])
        warnings.extend("%s: %s" % (label, item) for item in payload.get("warnings") or [])
        if payload.get("_missing"):
            warnings.append("%s: evidence JSON is missing" % label)
        if payload.get("_read_error"):
            blockers.append("%s: could not read evidence JSON: %s" % (label, payload["_read_error"]))

    blocker_items, blocker_extra = _limit(blockers, args.max_items)
    warning_items, warning_extra = _limit(warnings, args.max_items)
    lines.extend(["## Blockers", ""])
    lines.extend("- %s" % _markdown_escape(item) for item in blocker_items or ["None"])
    if blocker_extra:
        lines.append("- ... %s more blocker(s)" % blocker_extra)
    lines.extend(["", "## Warnings", ""])
    lines.extend("- %s" % _markdown_escape(item) for item in warning_items or ["None"])
    if warning_extra:
        lines.append("- ... %s more warning(s)" % warning_extra)

    component_rows = _ops_component_rows(production_ops, args.max_components)
    if component_rows:
        lines.extend(
            [
                "",
                "## Production Ops Components",
                "",
                "| Component | Status | Message |",
                "| --- | --- | --- |",
            ]
        )
        lines.extend(component_rows)
        extra = max(len(production_ops.get("components") or []) - args.max_components, 0)
        if extra:
            lines.append("")
            lines.append("... %s more component(s) in production-ops readiness." % extra)

    if args.artifact_name or args.artifact_url:
        lines.extend(["", "## Artifact", ""])
        if args.artifact_name:
            lines.append("- Name: `%s`" % _markdown_escape(args.artifact_name))
        if args.artifact_url:
            lines.append("- URL: %s" % _markdown_escape(args.artifact_url))

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Render a GitHub Actions step summary from Tijara evidence JSON.")
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_PROTECTED_RUN_ID", _default_run_id()))
    parser.add_argument("--target-environment", default=os.environ.get("TIJARA_TARGET_ENVIRONMENT", "staging"))
    parser.add_argument("--production-ops-readiness", default=os.environ.get("TIJARA_SUMMARY_PROD_OPS", ""))
    parser.add_argument("--release-readiness", default=os.environ.get("TIJARA_SUMMARY_RELEASE_READINESS", ""))
    parser.add_argument("--artifact-summary", default=os.environ.get("TIJARA_SUMMARY_ARTIFACT_SUMMARY", ""))
    parser.add_argument("--post-run-verification", default=os.environ.get("TIJARA_SUMMARY_POST_RUN", ""))
    parser.add_argument("--artifact-name", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_NAME", ""))
    parser.add_argument("--artifact-url", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_URL", ""))
    parser.add_argument("--output", default=os.environ.get("TIJARA_GITHUB_STEP_SUMMARY_OUTPUT", ""))
    parser.add_argument("--max-items", type=int, default=int(os.environ.get("TIJARA_GITHUB_STEP_SUMMARY_MAX_ITEMS", "8")))
    parser.add_argument(
        "--max-components",
        type=int,
        default=int(os.environ.get("TIJARA_GITHUB_STEP_SUMMARY_MAX_COMPONENTS", "16")),
    )
    args = parser.parse_args()

    if not args.production_ops_readiness:
        args.production_ops_readiness = "deploy/runtime/production-ops-readiness/%s/production-ops-readiness.json" % args.run_id
    if not args.release_readiness:
        args.release_readiness = "deploy/runtime/signoff-packages/%s/release-readiness.json" % args.run_id
    if not args.artifact_summary:
        args.artifact_summary = "deploy/runtime/protected-artifact-summary/%s/protected-artifact-summary.json" % args.run_id
    if not args.post_run_verification:
        args.post_run_verification = "deploy/runtime/protected-post-run-verification/%s/protected-post-run-verification.json" % args.run_id

    summary = _summary_lines(args)
    if args.output:
        target = _resolve(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
