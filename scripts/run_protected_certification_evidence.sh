#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${TIJARA_PROTECTED_RUN_ID:-${TIJARA_CERT_RUN_ID:-}}"
if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
fi

TARGET_ENVIRONMENT="${TIJARA_TARGET_ENVIRONMENT:-${TIJARA_CERT_ENVIRONMENT:-staging}}"
EVIDENCE_ROOT="${TIJARA_CERTIFICATION_EVIDENCE_ROOT:-deploy/runtime/certification-evidence/$RUN_ID}"
mkdir -p "$EVIDENCE_ROOT"

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
    echo "Certification evidence for $category is not configured; skipping."
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
  "${CERT_ARGS[@]}"
}

status=0
run_certification_category "psp" "TIJARA_CERT_PSP" || status=1
run_certification_category "fbr" "TIJARA_CERT_FBR" || status=1
run_certification_category "hardware" "TIJARA_CERT_HARDWARE" || status=1

{
  echo "TIJARA_CERTIFICATION_EVIDENCE_ROOT=$EVIDENCE_ROOT"
  echo "TIJARA_CERTIFICATION_EVIDENCE_PATHS=$EVIDENCE_ROOT/psp,$EVIDENCE_ROOT/fbr,$EVIDENCE_ROOT/hardware"
} > "$EVIDENCE_ROOT/certification-evidence-paths.env"

exit "$status"
