#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _write(path, content):
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not read JSON file %s: %s" % (path, error)) from error


def _status_row(name, status, exit_code, command, message):
    return {
        "name": name,
        "status": status,
        "exit_code": exit_code,
        "command": command,
        "message": message,
    }


def _docker_compose_commands(args, rollback_ref):
    compose_file = args.compose_file or "docker-compose.yml"
    service = args.service or "odoo"
    project = args.compose_project
    image_env = args.compose_image_env or "ODOO_IMAGE"
    base = ["docker", "compose", "-f", compose_file]
    if project:
        base.extend(["-p", project])
    command_base = ["env", "%s=%s" % (image_env, rollback_ref)] + base
    commands = [
        {
            "name": "compose-pull",
            "command": command_base + ["pull", service],
            "message": "Pull service image with %s=%s." % (image_env, rollback_ref),
        },
        {
            "name": "compose-up",
            "command": command_base + ["up", "-d", "--no-deps", service],
            "message": "Restart service with rollback image environment override.",
        },
        {
            "name": "compose-ps",
            "command": command_base + ["ps", service],
            "message": "Capture service status after rollback.",
        },
    ]
    return commands


def _kubernetes_commands(args, rollback_ref):
    namespace = args.namespace or "default"
    deployment = args.deployment or "tijara-odoo"
    container = args.container or "odoo"
    commands = [
        {
            "name": "kubectl-set-image",
            "command": [
                "kubectl",
                "-n",
                namespace,
                "set",
                "image",
                "deployment/%s" % deployment,
                "%s=%s" % (container, rollback_ref),
            ],
            "message": "Set Kubernetes deployment image to rollback reference.",
        },
        {
            "name": "kubectl-rollout-status",
            "command": ["kubectl", "-n", namespace, "rollout", "status", "deployment/%s" % deployment],
            "message": "Wait for Kubernetes rollout status.",
        },
    ]
    return commands


def _manifest_commands(args, rollback_ref):
    manifest = args.manifest or "deployment-manifest.yaml"
    return [
        {
            "name": "manifest-review",
            "command": ["printf", "Review deployment manifest %s for rollback reference %s\n" % (manifest, rollback_ref)],
            "message": "Manual/provider-specific rollback manifest review command.",
        }
    ]


def _commands(args, rollback_ref):
    provider = args.provider.replace("_", "-").lower()
    if provider == "docker-compose":
        return _docker_compose_commands(args, rollback_ref)
    if provider == "kubernetes":
        return _kubernetes_commands(args, rollback_ref)
    if provider == "manifest":
        return _manifest_commands(args, rollback_ref)
    raise RuntimeError("Unsupported rollback provider: %s" % args.provider)


def _run_command(command, execute, log_file):
    command_text = " ".join(command)
    if not execute:
        _write(log_file, "DRY RUN: %s" % command_text)
        return 0, "dry-run"
    with log_file.open("w", encoding="utf-8") as handle:
        process = subprocess.run(command, cwd=ROOT_DIR, text=True, stdout=handle, stderr=subprocess.STDOUT)
    return process.returncode, "passed" if process.returncode == 0 else "failed"


def _status_tsv(rows):
    lines = ["step\tstatus\texit_code\tcommand\tmessage"]
    for row in rows:
        lines.append(
            "%s\t%s\t%s\t%s\t%s"
            % (row["name"], row["status"], row["exit_code"], row["command"], row["message"])
        )
    return "\n".join(lines)


def _summary(args, output, execute, decision, rows, blockers, rollback_ref):
    row_lines = "\n".join(
        "- %s: %s (exit %s) - %s" % (row["name"], row["status"], row["exit_code"], row["message"])
        for row in rows
    )
    blocker_lines = "\n".join("- %s" % item for item in blockers) or "- None"
    return f"""
# Production Rollback Execution

- Status: {decision}
- Run ID: {args.run_id}
- Provider: {args.provider}
- Execute: {int(execute)}
- Rollback reference: {rollback_ref}
- Deployment gate: {args.deployment_gate}
- Output directory: {output}
- Generated: {_utc_now()}

## Steps

{row_lines}

## Blockers

{blocker_lines}

## Evidence Files

- Rollback decision: rollback-decision.json
- Status table: status.tsv
- Environment summary: env-summary.txt
- Per-step logs: `*.log`
"""


def main():
    parser = argparse.ArgumentParser(description="Run or dry-run Tijara production rollback commands.")
    parser.add_argument(
        "deployment_gate",
        nargs="?",
        default=os.environ.get("TIJARA_DEPLOYMENT_GATE_DECISION", ""),
        help="Path to deployment-decision.json from production deployment gate.",
    )
    parser.add_argument("--run-id", default=os.environ.get("TIJARA_ROLLBACK_RUN_ID", _default_run_id()))
    parser.add_argument("--output", default=os.environ.get("TIJARA_ROLLBACK_OUTPUT", ""))
    parser.add_argument("--provider", default=os.environ.get("TIJARA_ROLLBACK_PROVIDER", "manifest"))
    parser.add_argument("--rollback-ref", default=os.environ.get("TIJARA_ROLLBACK_REF", ""))
    parser.add_argument("--execute", action="store_true", default=_truthy(os.environ.get("TIJARA_ROLLBACK_EXECUTE")))
    parser.add_argument("--compose-file", default=os.environ.get("TIJARA_ROLLBACK_COMPOSE_FILE", ""))
    parser.add_argument("--compose-project", default=os.environ.get("TIJARA_ROLLBACK_COMPOSE_PROJECT", ""))
    parser.add_argument("--compose-image-env", default=os.environ.get("TIJARA_ROLLBACK_COMPOSE_IMAGE_ENV", ""))
    parser.add_argument("--service", default=os.environ.get("TIJARA_ROLLBACK_SERVICE", ""))
    parser.add_argument("--namespace", default=os.environ.get("TIJARA_ROLLBACK_NAMESPACE", ""))
    parser.add_argument("--deployment", default=os.environ.get("TIJARA_ROLLBACK_DEPLOYMENT", ""))
    parser.add_argument("--container", default=os.environ.get("TIJARA_ROLLBACK_CONTAINER", ""))
    parser.add_argument("--manifest", default=os.environ.get("TIJARA_ROLLBACK_MANIFEST", ""))
    args = parser.parse_args()

    if not args.deployment_gate:
        print("Missing deployment-decision.json path.", file=sys.stderr)
        return 2
    gate_path = Path(args.deployment_gate)
    if not gate_path.is_absolute():
        gate_path = ROOT_DIR / gate_path
    if not gate_path.is_file():
        print("Deployment gate decision file not found: %s" % gate_path, file=sys.stderr)
        return 2
    try:
        gate = _load_json(gate_path)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    rollback_ref = args.rollback_ref or gate.get("rollback_ref") or ""
    output = Path(args.output) if args.output else ROOT_DIR / "deploy/runtime/rollback-runs" / args.run_id
    output.mkdir(parents=True, exist_ok=True)

    blockers = []
    if gate.get("decision") == "blocked":
        blockers.append("Deployment gate is blocked; rollback still allowed only with explicit incident approval.")
    if not rollback_ref:
        blockers.append("Rollback reference is missing.")
    execute = bool(args.execute)
    if execute and os.environ.get("CONFIRM_PRODUCTION_ROLLBACK") != "YES":
        blockers.append("Set CONFIRM_PRODUCTION_ROLLBACK=YES to execute rollback commands.")

    rows = []
    if not blockers:
        try:
            commands = _commands(args, rollback_ref)
        except RuntimeError as error:
            blockers.append(str(error))
            commands = []
        for command_spec in commands:
            log_file = output / ("%s.log" % command_spec["name"])
            exit_code, status = _run_command(command_spec["command"], execute, log_file)
            rows.append(
                _status_row(
                    command_spec["name"],
                    status,
                    exit_code,
                    " ".join(command_spec["command"]),
                    command_spec["message"],
                )
            )
            if status == "failed":
                blockers.append("%s failed with exit code %s." % (command_spec["name"], exit_code))
    else:
        rows.append(_status_row("rollback-preflight", "failed", 1, "", "; ".join(blockers)))

    decision = "blocked" if blockers else ("executed" if execute else "dry-run")
    rollback_decision = {
        "run_id": args.run_id,
        "generated_at": _utc_now(),
        "decision": decision,
        "execute": execute,
        "provider": args.provider,
        "rollback_ref": rollback_ref,
        "deployment_gate": str(gate_path),
        "deployment_gate_decision": gate.get("decision"),
        "blockers": blockers,
        "steps": rows,
    }
    env_summary = "\n".join(
        [
            "run_id=%s" % args.run_id,
            "provider=%s" % args.provider,
            "execute=%s" % int(execute),
            "rollback_ref=%s" % (rollback_ref or "<missing>"),
            "deployment_gate=%s" % gate_path,
            "confirm_production_rollback=%s" % ("YES" if os.environ.get("CONFIRM_PRODUCTION_ROLLBACK") == "YES" else "<missing>"),
        ]
    )
    _write(output / "rollback-decision.json", json.dumps(rollback_decision, indent=2, sort_keys=True))
    _write(output / "status.tsv", _status_tsv(rows))
    _write(output / "env-summary.txt", env_summary)
    _write(output / "summary.md", _summary(args, output, execute, decision, rows, blockers, rollback_ref))

    print("Rollback evidence written to %s" % output)
    print("decision=%s" % decision)
    if blockers:
        print("Blockers:", file=sys.stderr)
        for blocker in blockers:
            print("- %s" % blocker, file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
