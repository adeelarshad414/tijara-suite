#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${TIJARA_PROTECTED_RUN_ID:-${TIJARA_CERT_RUN_ID:-}}"
if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
fi

TARGET_ENVIRONMENT="${TIJARA_TARGET_ENVIRONMENT:-${TIJARA_CERT_ENVIRONMENT:-staging}}"
EVIDENCE_ROOT="${TIJARA_CERTIFICATION_EVIDENCE_ROOT:-deploy/runtime/certification-evidence/$RUN_ID}"
REQUIRED_GROUPS="${TIJARA_CERTIFICATION_REQUIRED_GROUPS:-${TIJARA_PROTECTED_CERTIFICATION_GROUPS:-}}"
STATUS_FILE="$EVIDENCE_ROOT/status.tsv"
ENV_FILE="$EVIDENCE_ROOT/env-summary.txt"
mkdir -p "$EVIDENCE_ROOT"
: > "$STATUS_FILE"
printf 'category\tstatus\tmessage\toutput\n' > "$STATUS_FILE"

csv_args() {
  local raw="$1"
  local flag="$2"
  local item
  local old_ifs="$IFS"
  IFS=","
  for item in $raw; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    if [[ -n "$item" ]]; then
      CERT_ARGS+=("$flag" "$item")
    fi
  done
  IFS="$old_ifs"
}

value_for() {
  local name="$1"
  printf "%s" "${!name:-}"
}

record_status() {
  local category="$1"
  local status="$2"
  local message="$3"
  local output="$4"
  printf '%s\t%s\t%s\t%s\n' "$category" "$status" "$message" "$output" >> "$STATUS_FILE"
}

group_required() {
  local category="$1"
  local item
  local old_ifs="$IFS"
  IFS=","
  for item in $REQUIRED_GROUPS; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    item="$(printf "%s" "$item" | tr '[:upper:]' '[:lower:]')"
    if [[ "$item" == "$category" ]]; then
      IFS="$old_ifs"
      return 0
    fi
  done
  IFS="$old_ifs"
  return 1
}

run_certification_category() {
  local category="$1"
  local prefix="$2"
  local output="$EVIDENCE_ROOT/$category"
  local configured
  local minimum_evidence_files

  configured="$(
    printf "%s%s%s%s%s%s%s%s" \
      "$(value_for "${prefix}_EVIDENCE_FILES")" \
      "$(value_for "${prefix}_ARTIFACT_MANIFEST")" \
      "$(value_for "${prefix}_EXPECTED_SHA256")" \
      "$(value_for "${prefix}_PROVIDER")" \
      "$(value_for "${prefix}_REFERENCE")" \
      "$(value_for "${prefix}_OWNER")" \
      "$(value_for "${prefix}_DEVICE_MODEL")" \
      "$(value_for "${prefix}_DEVICE_SERIAL")"
  )"

  if [[ -z "$configured" ]]; then
    if group_required "$category"; then
      echo "Certification evidence for required group $category is not configured." >&2
      record_status "$category" "failed" "required certification group is not configured" "$output"
      return 1
    fi
    echo "Certification evidence for $category is not configured; skipping."
    record_status "$category" "skipped" "certification group is not configured" "$output"
    return 0
  fi

  CERT_ARGS=(
    python3 scripts/collect_certification_evidence.py
    --run-id "$RUN_ID"
    --category "$category"
    --target-environment "$TARGET_ENVIRONMENT"
    --output "$output"
    --provider "$(value_for "${prefix}_PROVIDER")"
    --reference "$(value_for "${prefix}_REFERENCE")"
    --owner "$(value_for "${prefix}_OWNER")"
    --device-model "$(value_for "${prefix}_DEVICE_MODEL")"
    --device-serial "$(value_for "${prefix}_DEVICE_SERIAL")"
    --store "$(value_for "${prefix}_STORE")"
    --artifact-manifest "$(value_for "${prefix}_ARTIFACT_MANIFEST")"
    --approved-by "$(value_for "${prefix}_APPROVED_BY")"
    --approval-reference "$(value_for "${prefix}_APPROVAL_REFERENCE")"
    --valid-until "$(value_for "${prefix}_VALID_UNTIL")"
    --require-artifact-manifest
    --require-approval
    --require-validity
    --strict
  )

  minimum_evidence_files="$(value_for "${prefix}_MINIMUM_EVIDENCE_FILES")"
  if [[ -n "$minimum_evidence_files" ]]; then
    CERT_ARGS+=(--minimum-evidence-files "$minimum_evidence_files")
  fi

  csv_args "$(value_for "${prefix}_EVIDENCE_FILES")" "--evidence-file"
  csv_args "$(value_for "${prefix}_EXPECTED_SHA256")" "--expected-sha256"
  csv_args "$(value_for "${prefix}_METADATA")" "--metadata"

  echo "Collecting strict $category certification evidence into $output"
  if "${CERT_ARGS[@]}"; then
    record_status "$category" "passed" "strict certification evidence collected" "$output"
    return 0
  fi
  record_status "$category" "failed" "strict certification evidence collection failed" "$output"
  return 1
}

status=0
run_certification_category "psp" "TIJARA_CERT_PSP" || status=1
run_certification_category "fbr" "TIJARA_CERT_FBR" || status=1
run_certification_category "hardware" "TIJARA_CERT_HARDWARE" || status=1

{
  echo "TIJARA_CERTIFICATION_EVIDENCE_ROOT=$EVIDENCE_ROOT"
  echo "TIJARA_CERTIFICATION_EVIDENCE_PATHS=$EVIDENCE_ROOT/psp,$EVIDENCE_ROOT/fbr,$EVIDENCE_ROOT/hardware"
} > "$EVIDENCE_ROOT/certification-evidence-paths.env"

{
  echo "run_id=$RUN_ID"
  echo "target_environment=$TARGET_ENVIRONMENT"
  echo "required_groups=${REQUIRED_GROUPS:-<none>}"
  echo "evidence_root=$EVIDENCE_ROOT"
  echo "status=$status"
} > "$ENV_FILE"

python3 - "$EVIDENCE_ROOT" "$RUN_ID" "$TARGET_ENVIRONMENT" "${REQUIRED_GROUPS:-}" "$status" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
run_id = sys.argv[2]
target_environment = sys.argv[3]
required_groups = [item.strip() for item in sys.argv[4].split(",") if item.strip()]
exit_status = int(sys.argv[5])
status_path = root / "status.tsv"
rows = []
if status_path.is_file():
    for line in status_path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = line.split("\t")
        while len(parts) < 4:
            parts.append("")
        rows.append(
            {
                "category": parts[0],
                "status": parts[1],
                "message": parts[2],
                "output": parts[3],
            }
        )

failed = [row for row in rows if row["status"] == "failed"]
skipped = [row for row in rows if row["status"] == "skipped"]
passed = [row for row in rows if row["status"] == "passed"]
if failed or exit_status:
    decision = "failed"
    ci_status = "fail"
else:
    decision = "passed"
    ci_status = "pass"

generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
manifest = {
    "context": {
        "run_id": run_id,
        "target_environment": target_environment,
        "required_groups": required_groups,
        "generated_at": generated_at,
        "output": str(root),
    },
    "decision": decision,
    "ci_status": ci_status,
    "categories": rows,
}
(root / "certification-execution.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

row_lines = "\n".join(
    "- %(category)s: %(status)s - %(message)s - %(output)s" % row for row in rows
) or "- No certification categories were evaluated."
blocker_lines = "\n".join(
    "- %(category)s: %(message)s" % row for row in failed
) or "- None"
warning_lines = "- None"
skipped_lines = "\n".join(
    "- %(category)s: %(message)s" % row for row in skipped
) or "- None"
summary = f"""
# Protected Certification Execution

- Status: {decision}
- Run ID: {run_id}
- Target environment: {target_environment}
- Required groups: {",".join(required_groups) or "<none>"}
- Generated: {generated_at}
- Output directory: {root}

## Categories

{row_lines}

## Blockers

{blocker_lines}

## Warnings

{warning_lines}

## Skipped Optional Groups

{skipped_lines}

## Evidence Files

- Execution manifest: certification-execution.json
- Status table: status.tsv
- Environment summary: env-summary.txt
- Evidence paths: certification-evidence-paths.env
"""
(root / "summary.md").write_text(summary.strip() + "\n", encoding="utf-8")
PY

exit "$status"
