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
    run_decision, run_decision_source = _read_json(args.run_decision)
    evidence_retention, evidence_retention_source = _read_json(args.evidence_retention) if args.evidence_retention else ({}, "")
    sidecar_verification, sidecar_verification_source = (
        _read_json(args.sidecar_verification) if args.sidecar_verification else ({}, "")
    )
    evidence_replay, evidence_replay_source = _read_json(args.evidence_replay) if args.evidence_replay else ({}, "")
    evidence_index, evidence_index_source = _read_json(args.evidence_index) if args.evidence_index else ({}, "")
    closure_gate, closure_gate_source = _read_json(args.closure_gate) if args.closure_gate else ({}, "")
    closure_result, closure_result_source = _read_json(args.closure_result) if args.closure_result else ({}, "")
    release_archive, release_archive_source = _read_json(args.release_archive) if args.release_archive else ({}, "")
    archive_upload, archive_upload_source = _read_json(args.archive_upload) if args.archive_upload else ({}, "")
    bundle_score, bundle_score_source = _read_json(args.bundle_score) if args.bundle_score else ({}, "")
    bundle_drift, bundle_drift_source = _read_json(args.bundle_drift) if args.bundle_drift else ({}, "")
    protected_chain, protected_chain_source = (
        _read_json(args.protected_release_chain) if args.protected_release_chain else ({}, "")
    )
    ci_artifact_bundle, ci_artifact_bundle_source = (
        _read_json(args.ci_artifact_bundle) if args.ci_artifact_bundle else ({}, "")
    )

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
        _verdict_row("Protected run decision", run_decision, run_decision_source),
    ]
    if args.protected_release_chain:
        lines.append(_verdict_row("Protected release chain", protected_chain, protected_chain_source))
    if args.ci_artifact_bundle:
        lines.append(_verdict_row("CI artifact bundle", ci_artifact_bundle, ci_artifact_bundle_source))
    if args.evidence_retention:
        lines.append(_verdict_row("Protected evidence retention", evidence_retention, evidence_retention_source))
    if args.sidecar_verification:
        lines.append(_verdict_row("Protected sidecar verification", sidecar_verification, sidecar_verification_source))
    if args.evidence_replay:
        lines.append(_verdict_row("Protected evidence replay", evidence_replay, evidence_replay_source))
    if args.evidence_index:
        lines.append(_verdict_row("Protected evidence index", evidence_index, evidence_index_source))
    if args.closure_gate:
        lines.append(_verdict_row("Protected closure gate", closure_gate, closure_gate_source))
    if args.closure_result:
        lines.append(_verdict_row("Protected closure result", closure_result, closure_result_source))
    if args.release_archive:
        lines.append(_verdict_row("Protected release archive", release_archive, release_archive_source))
    if args.archive_upload:
        lines.append(_verdict_row("Protected archive upload", archive_upload, archive_upload_source))
    if args.bundle_score:
        lines.append(_verdict_row("Protected bundle score", bundle_score, bundle_score_source))
    if args.bundle_drift:
        lines.append(_verdict_row("Protected bundle drift", bundle_drift, bundle_drift_source))
    lines.append("")

    blockers = []
    warnings = []
    for label, payload in [
        ("release-readiness", release_readiness),
        ("production-ops", production_ops),
        ("post-run", post_run),
        ("artifact-summary", artifact_summary),
        ("run-decision", run_decision),
    ]:
        blockers.extend("%s: %s" % (label, item) for item in payload.get("blockers") or [])
        warnings.extend("%s: %s" % (label, item) for item in payload.get("warnings") or [])
        if payload.get("_missing"):
            warnings.append("%s: evidence JSON is missing" % label)
        if payload.get("_read_error"):
            blockers.append("%s: could not read evidence JSON: %s" % (label, payload["_read_error"]))
    if args.evidence_retention:
        blockers.extend("evidence-retention: %s" % item for item in evidence_retention.get("blockers") or [])
        warnings.extend("evidence-retention: %s" % item for item in evidence_retention.get("warnings") or [])
        if evidence_retention.get("_missing"):
            warnings.append("evidence-retention: evidence JSON is missing")
        if evidence_retention.get("_read_error"):
            blockers.append("evidence-retention: could not read evidence JSON: %s" % evidence_retention["_read_error"])
    if args.sidecar_verification:
        blockers.extend("sidecar-verification: %s" % item for item in sidecar_verification.get("blockers") or [])
        warnings.extend("sidecar-verification: %s" % item for item in sidecar_verification.get("warnings") or [])
        if sidecar_verification.get("_missing"):
            warnings.append("sidecar-verification: evidence JSON is missing")
        if sidecar_verification.get("_read_error"):
            blockers.append("sidecar-verification: could not read evidence JSON: %s" % sidecar_verification["_read_error"])
    if args.evidence_replay:
        blockers.extend("evidence-replay: %s" % item for item in evidence_replay.get("blockers") or [])
        warnings.extend("evidence-replay: %s" % item for item in evidence_replay.get("warnings") or [])
        if evidence_replay.get("_missing"):
            warnings.append("evidence-replay: evidence JSON is missing")
        if evidence_replay.get("_read_error"):
            blockers.append("evidence-replay: could not read evidence JSON: %s" % evidence_replay["_read_error"])
    if args.evidence_index:
        blockers.extend("evidence-index: %s" % item for item in evidence_index.get("blockers") or [])
        warnings.extend("evidence-index: %s" % item for item in evidence_index.get("warnings") or [])
        if evidence_index.get("_missing"):
            warnings.append("evidence-index: evidence JSON is missing")
        if evidence_index.get("_read_error"):
            blockers.append("evidence-index: could not read evidence JSON: %s" % evidence_index["_read_error"])
    if args.closure_gate:
        blockers.extend("closure-gate: %s" % item for item in closure_gate.get("blockers") or [])
        warnings.extend("closure-gate: %s" % item for item in closure_gate.get("warnings") or [])
        if closure_gate.get("_missing"):
            warnings.append("closure-gate: evidence JSON is missing")
        if closure_gate.get("_read_error"):
            blockers.append("closure-gate: could not read evidence JSON: %s" % closure_gate["_read_error"])
    if args.closure_result:
        blockers.extend("closure-result: %s" % item for item in closure_result.get("blockers") or [])
        warnings.extend("closure-result: %s" % item for item in closure_result.get("warnings") or [])
        if closure_result.get("_missing"):
            warnings.append("closure-result: evidence JSON is missing")
        if closure_result.get("_read_error"):
            blockers.append("closure-result: could not read evidence JSON: %s" % closure_result["_read_error"])
    if args.release_archive:
        blockers.extend("release-archive: %s" % item for item in release_archive.get("blockers") or [])
        warnings.extend("release-archive: %s" % item for item in release_archive.get("warnings") or [])
        if release_archive.get("_missing"):
            warnings.append("release-archive: evidence JSON is missing")
        if release_archive.get("_read_error"):
            blockers.append("release-archive: could not read evidence JSON: %s" % release_archive["_read_error"])
    if args.archive_upload:
        blockers.extend("archive-upload: %s" % item for item in archive_upload.get("blockers") or [])
        warnings.extend("archive-upload: %s" % item for item in archive_upload.get("warnings") or [])
        if archive_upload.get("_missing"):
            warnings.append("archive-upload: evidence JSON is missing")
        if archive_upload.get("_read_error"):
            blockers.append("archive-upload: could not read evidence JSON: %s" % archive_upload["_read_error"])
    if args.bundle_score:
        blockers.extend("bundle-score: %s" % item for item in bundle_score.get("blockers") or [])
        warnings.extend("bundle-score: %s" % item for item in bundle_score.get("warnings") or [])
        if bundle_score.get("_missing"):
            warnings.append("bundle-score: evidence JSON is missing")
        if bundle_score.get("_read_error"):
            blockers.append("bundle-score: could not read evidence JSON: %s" % bundle_score["_read_error"])
    if args.bundle_drift:
        blockers.extend("bundle-drift: %s" % item for item in bundle_drift.get("blockers") or [])
        warnings.extend("bundle-drift: %s" % item for item in bundle_drift.get("warnings") or [])
        if bundle_drift.get("_missing"):
            warnings.append("bundle-drift: evidence JSON is missing")
        if bundle_drift.get("_read_error"):
            blockers.append("bundle-drift: could not read evidence JSON: %s" % bundle_drift["_read_error"])
    if args.protected_release_chain:
        blockers.extend("protected-release-chain: %s" % item for item in protected_chain.get("blockers") or [])
        warnings.extend("protected-release-chain: %s" % item for item in protected_chain.get("warnings") or [])
        if protected_chain.get("_missing"):
            warnings.append("protected-release-chain: evidence JSON is missing")
        if protected_chain.get("_read_error"):
            blockers.append("protected-release-chain: could not read evidence JSON: %s" % protected_chain["_read_error"])
    if args.ci_artifact_bundle:
        blockers.extend("ci-artifact-bundle: %s" % item for item in ci_artifact_bundle.get("blockers") or [])
        warnings.extend("ci-artifact-bundle: %s" % item for item in ci_artifact_bundle.get("warnings") or [])
        if ci_artifact_bundle.get("_missing"):
            warnings.append("ci-artifact-bundle: evidence JSON is missing")
        if ci_artifact_bundle.get("_read_error"):
            blockers.append("ci-artifact-bundle: could not read evidence JSON: %s" % ci_artifact_bundle["_read_error"])

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

    if args.artifact_name or args.artifact_url or args.artifact_id or args.artifact_digest:
        lines.extend(["", "## Artifact", ""])
        if args.artifact_name:
            lines.append("- Name: `%s`" % _markdown_escape(args.artifact_name))
        if args.artifact_id:
            lines.append("- ID: `%s`" % _markdown_escape(args.artifact_id))
        if args.artifact_url:
            lines.append("- URL: %s" % _markdown_escape(args.artifact_url))
        if args.artifact_digest:
            lines.append("- Digest: `%s`" % _markdown_escape(args.artifact_digest))
        if args.artifact_retention_days:
            lines.append("- Retention days: `%s`" % _markdown_escape(args.artifact_retention_days))

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
    parser.add_argument("--run-decision", default=os.environ.get("TIJARA_SUMMARY_RUN_DECISION", ""))
    parser.add_argument("--evidence-retention", default=os.environ.get("TIJARA_SUMMARY_EVIDENCE_RETENTION", ""))
    parser.add_argument("--sidecar-verification", default=os.environ.get("TIJARA_SUMMARY_SIDECAR_VERIFICATION", ""))
    parser.add_argument("--evidence-replay", default=os.environ.get("TIJARA_SUMMARY_EVIDENCE_REPLAY", ""))
    parser.add_argument("--evidence-index", default=os.environ.get("TIJARA_SUMMARY_EVIDENCE_INDEX", ""))
    parser.add_argument("--closure-gate", default=os.environ.get("TIJARA_SUMMARY_CLOSURE_GATE", ""))
    parser.add_argument("--closure-result", default=os.environ.get("TIJARA_SUMMARY_CLOSURE_RESULT", ""))
    parser.add_argument("--release-archive", default=os.environ.get("TIJARA_SUMMARY_RELEASE_ARCHIVE", ""))
    parser.add_argument("--archive-upload", default=os.environ.get("TIJARA_SUMMARY_ARCHIVE_UPLOAD", ""))
    parser.add_argument("--bundle-score", default=os.environ.get("TIJARA_SUMMARY_BUNDLE_SCORE", ""))
    parser.add_argument("--bundle-drift", default=os.environ.get("TIJARA_SUMMARY_BUNDLE_DRIFT", ""))
    parser.add_argument("--protected-release-chain", default=os.environ.get("TIJARA_SUMMARY_PROTECTED_RELEASE_CHAIN", ""))
    parser.add_argument("--ci-artifact-bundle", default=os.environ.get("TIJARA_SUMMARY_CI_ARTIFACT_BUNDLE", ""))
    parser.add_argument("--artifact-name", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_NAME", ""))
    parser.add_argument("--artifact-id", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_ID", ""))
    parser.add_argument("--artifact-url", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_URL", ""))
    parser.add_argument("--artifact-digest", default=os.environ.get("TIJARA_UPLOADED_ARTIFACT_DIGEST", ""))
    parser.add_argument("--artifact-retention-days", default=os.environ.get("TIJARA_GITHUB_ARTIFACT_RETENTION_DAYS", ""))
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
    if not args.run_decision:
        args.run_decision = "deploy/runtime/protected-run-decision/%s/protected-run-decision.json" % args.run_id
    if not args.evidence_retention:
        default_retention = "deploy/runtime/protected-evidence-retention/%s/protected-evidence-retention-manifest.json" % args.run_id
        if _resolve(default_retention).is_file():
            args.evidence_retention = default_retention
    if not args.sidecar_verification:
        default_sidecar = "deploy/runtime/protected-sidecar-verification/%s/protected-sidecar-verification.json" % args.run_id
        if _resolve(default_sidecar).is_file():
            args.sidecar_verification = default_sidecar
    if not args.evidence_replay:
        default_replay = "deploy/runtime/protected-evidence-replay/%s/protected-evidence-replay-report.json" % args.run_id
        if _resolve(default_replay).is_file():
            args.evidence_replay = default_replay
    if not args.evidence_index:
        default_index = "deploy/runtime/protected-release-evidence-index/%s/protected-release-evidence-index.json" % args.run_id
        if _resolve(default_index).is_file():
            args.evidence_index = default_index
    if not args.closure_gate:
        default_closure = "deploy/runtime/protected-release-closure/%s/protected-release-closure-decision.json" % args.run_id
        if _resolve(default_closure).is_file():
            args.closure_gate = default_closure
    if not args.closure_result:
        default_result = "deploy/runtime/protected-closure-result-verification/%s/protected-closure-result-verification.json" % args.run_id
        if _resolve(default_result).is_file():
            args.closure_result = default_result
    if not args.release_archive:
        default_archive = "deploy/runtime/protected-release-archive/%s/protected-release-archive-manifest.json" % args.run_id
        if _resolve(default_archive).is_file():
            args.release_archive = default_archive
    if not args.archive_upload:
        default_archive_upload = "deploy/runtime/protected-archive-upload-verification/%s/protected-archive-upload-verification.json" % args.run_id
        if _resolve(default_archive_upload).is_file():
            args.archive_upload = default_archive_upload
    if not args.bundle_score:
        default_bundle_score = "deploy/runtime/protected-evidence-bundle-score/%s/protected-evidence-bundle-score.json" % args.run_id
        if _resolve(default_bundle_score).is_file():
            args.bundle_score = default_bundle_score
    if not args.bundle_drift:
        default_bundle_drift = "deploy/runtime/protected-evidence-bundle-drift/%s/protected-evidence-bundle-drift.json" % args.run_id
        if _resolve(default_bundle_drift).is_file():
            args.bundle_drift = default_bundle_drift
    if not args.protected_release_chain:
        default_chain = "deploy/runtime/protected-release-chain/%s/protected-release-chain.json" % args.run_id
        if _resolve(default_chain).is_file():
            args.protected_release_chain = default_chain
    if not args.ci_artifact_bundle:
        default_bundle = "deploy/runtime/protected-release-chain/%s/ci-artifact-bundle.json" % args.run_id
        if _resolve(default_bundle).is_file():
            args.ci_artifact_bundle = default_bundle

    summary = _summary_lines(args)
    if args.output:
        target = _resolve(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
