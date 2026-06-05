#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
    cat <<'USAGE'
Usage:
  scripts/bootstrap_protected_runner.sh [--dry-run|--apply] [options]

Options:
  --config FILE       Source a secret-free bootstrap config file first.
  --run-id ID         Evidence run id. Defaults to UTC timestamp.
  --output DIR        Evidence output directory.
  --target-os OS      auto, ubuntu, debian, macos, or unknown.
  --dry-run           Write install/preflight plans only. Default.
  --apply             Execute the generated install plan, then rescan tools.
  -h, --help          Show this help.

Environment:
  TIJARA_BOOTSTRAP_MODE              dry-run or apply.
  TIJARA_BOOTSTRAP_TARGET_OS         auto, ubuntu, debian, macos, or unknown.
  TIJARA_BOOTSTRAP_REQUIRED_TOOLS    Required preflight tools.
  TIJARA_BOOTSTRAP_OPTIONAL_TOOLS    Optional preflight tools.
  TIJARA_BOOTSTRAP_DOCKER_GROUP_USER User to add to docker group on Linux.

The script writes a bootstrap evidence folder with:
  install-plan.sh       OS-specific open-source installation commands.
  preflight-command.sh  Exact protected-runner preflight command.
  tool-status.tsv       Current local command/version scan.
  env-summary.txt       Redacted bootstrap settings.
  summary.md            Operator summary and next actions.

Dry-run mode never installs packages and is safe for CI/local validation.
USAGE
}

default_run_id() {
    date -u +%Y%m%d-%H%M%S
}

utc_now() {
    date -u +%Y-%m-%dT%H:%M:%SZ
}

trim() {
    local value="$*"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

detect_target_os() {
    local uname_value
    uname_value="$(uname -s 2>/dev/null || true)"
    case "$uname_value" in
        Darwin)
            printf 'macos'
            return
            ;;
        Linux)
            if [[ -r /etc/os-release ]]; then
                # shellcheck disable=SC1091
                . /etc/os-release
                case "${ID:-}" in
                    ubuntu)
                        printf 'ubuntu'
                        return
                        ;;
                    debian)
                        printf 'debian'
                        return
                        ;;
                esac
            fi
            printf 'unknown'
            return
            ;;
    esac
    printf 'unknown'
}

CONFIG_FILE="${TIJARA_BOOTSTRAP_CONFIG:-}"
ARGS=("$@")
index=0
while [[ "$index" -lt "${#ARGS[@]}" ]]; do
    case "${ARGS[$index]}" in
        --config)
            index=$((index + 1))
            CONFIG_FILE="${ARGS[$index]:-}"
            ;;
    esac
    index=$((index + 1))
done

if [[ -n "$CONFIG_FILE" ]]; then
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "Bootstrap config not found: $CONFIG_FILE" >&2
        exit 2
    fi
    # shellcheck disable=SC1090
    . "$CONFIG_FILE"
fi

RUN_ID="${TIJARA_BOOTSTRAP_RUN_ID:-$(default_run_id)}"
MODE="${TIJARA_BOOTSTRAP_MODE:-dry-run}"
TARGET_OS="${TIJARA_BOOTSTRAP_TARGET_OS:-auto}"
OUTPUT_DIR="${TIJARA_BOOTSTRAP_OUTPUT:-deploy/runtime/protected-runner-bootstrap/$RUN_ID}"
REQUIRED_TOOLS="${TIJARA_BOOTSTRAP_REQUIRED_TOOLS:-python3,node,npm,docker,docker-compose,trivy,k6,psql,pg_dump,pg_restore}"
OPTIONAL_TOOLS="${TIJARA_BOOTSTRAP_OPTIONAL_TOOLS:-pip-audit,gh}"
DOCKER_GROUP_USER="${TIJARA_BOOTSTRAP_DOCKER_GROUP_USER:-${USER:-}}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            shift 2
            ;;
        --run-id)
            RUN_ID="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --target-os)
            TARGET_OS="$2"
            shift 2
            ;;
        --dry-run)
            MODE="dry-run"
            shift
            ;;
        --apply)
            MODE="apply"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$MODE" in
    dry-run|apply)
        ;;
    *)
        echo "TIJARA_BOOTSTRAP_MODE must be dry-run or apply." >&2
        exit 2
        ;;
esac

if [[ "$TARGET_OS" == "auto" ]]; then
    TARGET_OS="$(detect_target_os)"
fi

mkdir -p "$OUTPUT_DIR"
INSTALL_PLAN="$OUTPUT_DIR/install-plan.sh"
PREFLIGHT_COMMAND="$OUTPUT_DIR/preflight-command.sh"
STATUS_FILE="$OUTPUT_DIR/status.tsv"
TOOL_STATUS_FILE="$OUTPUT_DIR/tool-status.tsv"
ENV_FILE="$OUTPUT_DIR/env-summary.txt"
SUMMARY_FILE="$OUTPUT_DIR/summary.md"
NOTES_FILE="$OUTPUT_DIR/github-environment-notes.md"
APPLY_LOG="$OUTPUT_DIR/apply.log"
STARTED_AT="$(utc_now)"

: > "$STATUS_FILE"
: > "$TOOL_STATUS_FILE"

record_status() {
    local name="$1"
    local status="$2"
    local message="$3"
    printf '%s\t%s\t%s\n' "$name" "$status" "$message" >> "$STATUS_FILE"
}

write_ubuntu_plan() {
    cat > "$INSTALL_PLAN" <<'PLAN'
#!/usr/bin/env bash
set -euo pipefail

: "${TIJARA_BOOTSTRAP_DOCKER_GROUP_USER:=${USER:-}}"

sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  python3 \
  python3-pip \
  python3-venv \
  pipx \
  nodejs \
  npm \
  postgresql-client \
  docker.io \
  docker-compose-plugin \
  git

export PATH="$HOME/.local/bin:$PATH"
if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "$HOME/.local/bin" >> "$GITHUB_PATH"
fi
python3 -m pipx ensurepath || true
python3 -m pipx install pip-audit || python3 -m pipx upgrade pip-audit || true

if ! command -v trivy >/dev/null 2>&1; then
  sudo install -m 0755 -d /usr/share/keyrings
  curl -fsSL https://aquasecurity.github.io/trivy-repo/deb/public.key \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/trivy.gpg
  echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" \
    | sudo tee /etc/apt/sources.list.d/trivy.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y trivy
fi

if ! command -v k6 >/dev/null 2>&1; then
  sudo install -m 0755 -d /usr/share/keyrings
  curl -fsSL https://dl.k6.io/key.gpg \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/k6-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
    | sudo tee /etc/apt/sources.list.d/k6.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y k6
fi

if ! command -v gh >/dev/null 2>&1; then
  sudo apt-get install -y gh || true
fi

if [[ -n "$TIJARA_BOOTSTRAP_DOCKER_GROUP_USER" ]]; then
  sudo usermod -aG docker "$TIJARA_BOOTSTRAP_DOCKER_GROUP_USER" || true
fi

echo "Protected runner tools installed. Re-login the runner user if Docker group membership changed."
PLAN
}

write_macos_plan() {
    cat > "$INSTALL_PLAN" <<'PLAN'
#!/usr/bin/env bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required for the macOS protected runner bootstrap." >&2
  exit 2
fi

brew update
brew install python node docker docker-compose trivy k6 postgresql@16 gh pipx

export PATH="$HOME/.local/bin:/opt/homebrew/opt/postgresql@16/bin:/usr/local/opt/postgresql@16/bin:$PATH"
if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "$HOME/.local/bin" >> "$GITHUB_PATH"
  echo "/opt/homebrew/opt/postgresql@16/bin" >> "$GITHUB_PATH"
  echo "/usr/local/opt/postgresql@16/bin" >> "$GITHUB_PATH"
fi

python3 -m pipx ensurepath || true
python3 -m pipx install pip-audit || python3 -m pipx upgrade pip-audit || true

echo "Protected runner tools installed. Start Docker Desktop or a compatible Docker daemon before release runs."
PLAN
}

write_unknown_plan() {
    cat > "$INSTALL_PLAN" <<'PLAN'
#!/usr/bin/env bash
set -euo pipefail

cat <<'MESSAGE'
No automatic package-manager plan is available for this OS.
Install these tools with your platform package manager, then run preflight:

Required:
  python3 node npm docker docker-compose trivy k6 psql pg_dump pg_restore

Optional:
  pip-audit gh

For Linux runners, ensure the GitHub runner user can talk to the Docker daemon.
For macOS runners, ensure Docker Desktop or an equivalent daemon is already running.
MESSAGE
PLAN
}

write_install_plan() {
    case "$TARGET_OS" in
        ubuntu|debian)
            write_ubuntu_plan
            ;;
        macos)
            write_macos_plan
            ;;
        *)
            write_unknown_plan
            ;;
    esac
    chmod +x "$INSTALL_PLAN"
    record_status "install-plan" "generated" "$INSTALL_PLAN"
}

write_preflight_command() {
    cat > "$PREFLIGHT_COMMAND" <<'PLAN'
#!/usr/bin/env bash
set -euo pipefail

export TIJARA_PREFLIGHT_CHECK_TOOLS=1
export TIJARA_PREFLIGHT_REQUIRED_TOOLS="${TIJARA_PREFLIGHT_REQUIRED_TOOLS:-python3,node,npm,docker,docker-compose,trivy,k6,psql,pg_dump,pg_restore}"
export TIJARA_PREFLIGHT_OPTIONAL_TOOLS="${TIJARA_PREFLIGHT_OPTIONAL_TOOLS:-pip-audit,gh}"
export TIJARA_PREFLIGHT_TOOL_TIMEOUT="${TIJARA_PREFLIGHT_TOOL_TIMEOUT:-8}"
RUN_ID="${TIJARA_PROTECTED_RUN_ID:-protected-runner-bootstrap-preflight}"

python3 scripts/export_protected_runner_preflight.py \
  --run-id "$RUN_ID" \
  --target-environment "${TIJARA_TARGET_ENVIRONMENT:-staging}" \
  --output "deploy/runtime/protected-runner-preflight/$RUN_ID" \
  --check-tools \
  --strict
PLAN
    chmod +x "$PREFLIGHT_COMMAND"
    record_status "preflight-command" "generated" "$PREFLIGHT_COMMAND"
}

write_notes() {
    cat > "$NOTES_FILE" <<'NOTES'
# Protected Runner Environment Notes

- Runner labels: `self-hosted`, `tijara-protected`.
- Non-secret variables: start from `deploy/config/github-protected-vars.example`.
- Secrets: start from `secrets/github-protected-secrets.example`.
- Bootstrap config: start from `deploy/config/protected-runner-bootstrap.env.example`.
- Keep package installation outside the protected release workflow; run it as
  runner maintenance, then prove readiness with `preflight-command.sh`.
- Re-run bootstrap dry-run and protected preflight after runner image upgrades,
  Docker daemon changes, k6/Trivy upgrades, or PostgreSQL client upgrades.
NOTES
    record_status "environment-notes" "generated" "$NOTES_FILE"
}

tool_version_command() {
    local tool="$1"
    case "$tool" in
        python3) printf 'python3\0--version\0' ;;
        node) printf 'node\0--version\0' ;;
        npm) printf 'npm\0--version\0' ;;
        docker) printf 'docker\0--version\0' ;;
        docker-compose) printf 'docker\0compose\0version\0' ;;
        trivy) printf 'trivy\0--version\0' ;;
        k6) printf 'k6\0version\0' ;;
        psql) printf 'psql\0--version\0' ;;
        pg_dump) printf 'pg_dump\0--version\0' ;;
        pg_restore) printf 'pg_restore\0--version\0' ;;
        pip-audit) printf 'pip-audit\0--version\0' ;;
        gh) printf 'gh\0--version\0' ;;
        *) printf '%s\0--version\0' "$tool" ;;
    esac
}

scan_tool() {
    local tool="$1"
    local scope="$2"
    local safe_tool="${tool//[^a-zA-Z0-9_.-]/_}"
    local log_file="$OUTPUT_DIR/tool-$safe_tool.log"
    local status="missing"
    local exit_code=127
    local version=""
    local -a command=()

    while IFS= read -r -d '' item; do
        command+=("$item")
    done < <(tool_version_command "$tool")

    if [[ "${#command[@]}" -eq 0 ]]; then
        printf '%s: command not found\n' "$tool" > "$log_file"
    elif ! command -v "${command[0]}" >/dev/null 2>&1; then
        printf '%s: command not found\n' "${command[0]:-$tool}" > "$log_file"
    else
        set +e
        "${command[@]}" > "$log_file" 2>&1
        exit_code=$?
        set -e
    fi

    if [[ "$exit_code" -eq 0 ]]; then
        status="present"
    fi
    version="$(head -n 1 "$log_file" 2>/dev/null | tr '\t' ' ' || true)"
    printf '%s\t%s\t%s\t%s\t%s\n' "$tool" "$scope" "$status" "$exit_code" "$version" >> "$TOOL_STATUS_FILE"
}

scan_tools() {
    local tool
    local raw
    local -a required=()
    local -a optional=()
    IFS=',' read -r -a required <<< "$REQUIRED_TOOLS"
    IFS=',' read -r -a optional <<< "$OPTIONAL_TOOLS"

    for raw in "${required[@]}"; do
        tool="$(trim "$raw")"
        [[ -n "$tool" ]] && scan_tool "$tool" "required"
    done
    for raw in "${optional[@]}"; do
        tool="$(trim "$raw")"
        [[ -n "$tool" ]] && scan_tool "$tool" "optional"
    done
    record_status "tool-scan" "completed" "$TOOL_STATUS_FILE"
}

write_env_summary() {
    {
        echo "run_id=$RUN_ID"
        echo "mode=$MODE"
        echo "target_os=$TARGET_OS"
        echo "output_dir=$OUTPUT_DIR"
        echo "required_tools=$REQUIRED_TOOLS"
        echo "optional_tools=$OPTIONAL_TOOLS"
        echo "docker_group_user=${DOCKER_GROUP_USER:-<unset>}"
        echo "started_at=$STARTED_AT"
        echo "finished_at=$(utc_now)"
    } > "$ENV_FILE"
    record_status "env-summary" "generated" "$ENV_FILE"
}

run_apply_if_requested() {
    if [[ "$MODE" != "apply" ]]; then
        record_status "apply" "skipped" "dry-run mode"
        return
    fi

    set +e
    TIJARA_BOOTSTRAP_DOCKER_GROUP_USER="$DOCKER_GROUP_USER" bash "$INSTALL_PLAN" > "$APPLY_LOG" 2>&1
    local exit_code=$?
    set -e

    if [[ "$exit_code" -eq 0 ]]; then
        record_status "apply" "passed" "$APPLY_LOG"
    else
        record_status "apply" "failed" "$APPLY_LOG"
        return "$exit_code"
    fi
}

write_summary() {
    local present_count
    local missing_count
    present_count="$(awk -F '\t' '$3 == "present" {count++} END {print count + 0}' "$TOOL_STATUS_FILE")"
    missing_count="$(awk -F '\t' '$3 == "missing" {count++} END {print count + 0}' "$TOOL_STATUS_FILE")"
    {
        echo "# Tijara Protected Runner Bootstrap"
        echo
        echo "- Run ID: $RUN_ID"
        echo "- Mode: $MODE"
        echo "- Target OS: $TARGET_OS"
        echo "- Output: $OUTPUT_DIR"
        echo "- Started: $STARTED_AT"
        echo "- Finished: $(utc_now)"
        echo "- Tools present: $present_count"
        echo "- Tools missing: $missing_count"
        echo
        echo "## Generated Files"
        echo
        echo "- Install plan: $INSTALL_PLAN"
        echo "- Preflight command: $PREFLIGHT_COMMAND"
        echo "- GitHub environment notes: $NOTES_FILE"
        echo "- Tool scan: $TOOL_STATUS_FILE"
        echo "- Status table: $STATUS_FILE"
        echo "- Environment summary: $ENV_FILE"
        if [[ -f "$APPLY_LOG" ]]; then
            echo "- Apply log: $APPLY_LOG"
        fi
        echo
        echo "## Tool Scan"
        echo
        while IFS=$'\t' read -r tool scope status exit_code version; do
            echo "- $tool ($scope): $status, exit $exit_code, ${version:-no version output}"
        done < "$TOOL_STATUS_FILE"
        echo
        echo "## Next Actions"
        echo
        if [[ "$MODE" == "dry-run" ]]; then
            echo "- Review $INSTALL_PLAN on the protected runner."
            echo "- Run this script with --apply during runner maintenance if the plan is approved."
        else
            echo "- Review $APPLY_LOG for package-manager output."
        fi
        echo "- Run $PREFLIGHT_COMMAND after installation and before protected release dispatch."
        echo "- Attach the generated preflight folder to the protected release evidence review."
    } > "$SUMMARY_FILE"
    record_status "summary" "generated" "$SUMMARY_FILE"
}

write_install_plan
write_preflight_command
write_notes
run_apply_if_requested
scan_tools
write_env_summary
write_summary

echo "Protected runner bootstrap evidence written to $OUTPUT_DIR"
echo "mode=$MODE"
echo "target_os=$TARGET_OS"
