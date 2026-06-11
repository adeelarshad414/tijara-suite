#!/usr/bin/env python3
"""Bootstrap and host Tijara Suite on a server using central config files."""

from __future__ import annotations

import argparse
import secrets as secretlib
import string
from pathlib import Path

from tijara_ops_common import (
    ROOT_DIR,
    ENV_FILE,
    SECRET_FILE,
    check_docker_compose,
    compose_command,
    ensure_env_files,
    has_command,
    load_runtime_env,
    run,
    selected_profiles,
    service_urls,
)


SECRET_KEYS_TO_GENERATE = {
    "POSTGRES_PASSWORD",
    "ODOO_DB_PASSWORD",
    "ODOO_MASTER_PASSWORD",
    "BACKUP_ENCRYPTION_KEY",
    "ODOO_SESSION_SECRET",
    "GRAFANA_ADMIN_PASSWORD",
    "TIJARA_METRICS_TOKEN",
    "TIJARA_BRIDGE_SHARED_SECRET",
}
PLACEHOLDER_PREFIXES = ("replace-", "dummy-", "change-me", "example-", "test-")


def _secret_value(length: int = 48) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secretlib.choice(alphabet) for _ in range(length))


def _read_env_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _upsert_env(path: Path, updates: dict[str, str], *, dry_run: bool = False) -> None:
    lines = _read_env_lines(path)
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                output.append("%s=%s" % (key, updates[key]))
                seen.add(key)
                continue
        output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append("%s=%s" % (key, value))
    print("Update %s: %s" % (path, ", ".join(sorted(updates))))
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _looks_placeholder(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    return text.startswith(PLACEHOLDER_PREFIXES)


def _generate_secret_updates(values: dict[str, str]) -> dict[str, str]:
    generated = {key: _secret_value() for key in SECRET_KEYS_TO_GENERATE if _looks_placeholder(values.get(key, ""))}
    if "POSTGRES_PASSWORD" in generated:
        generated["ODOO_DB_PASSWORD"] = generated["POSTGRES_PASSWORD"]
    elif "ODOO_DB_PASSWORD" in generated and not _looks_placeholder(values.get("POSTGRES_PASSWORD", "")):
        generated["ODOO_DB_PASSWORD"] = values["POSTGRES_PASSWORD"]
    return generated


def _production_secret_blockers(values: dict[str, str]) -> list[str]:
    blockers = []
    for key in sorted(SECRET_KEYS_TO_GENERATE):
        if _looks_placeholder(values.get(key, "")):
            blockers.append("%s is missing or placeholder" % key)
    return blockers


def cmd_preflight(args: argparse.Namespace) -> int:
    root = args.root
    ok = True
    print("Tijara host preflight")
    print("Project root: %s" % root)
    for command in ("python3", "docker", "git"):
        present = has_command(command)
        print("%-16s %s" % (command, "ok" if present else "missing"))
        if command in {"python3", "docker"} and not present:
            ok = False
    if not check_docker_compose(root, args.dry_run):
        ok = False
    ensure_env_files(root, dry_run=args.dry_run)
    profiles = selected_profiles(
        with_hardware=getattr(args, "with_hardware", False),
        with_monitoring=getattr(args, "with_monitoring", False),
        all_profiles=args.all_profiles,
    )
    run(compose_command(root, ["config", "--quiet"], profiles), cwd=root, dry_run=args.dry_run, check=False)
    return 0 if ok else 2


def cmd_init_config(args: argparse.Namespace) -> int:
    root = args.root
    ensure_env_files(root, dry_run=args.dry_run)
    env_updates: dict[str, str] = {}
    if args.environment:
        env_updates["TIJARA_ENV"] = args.environment
    if args.public_url:
        env_updates["TIJARA_PUBLIC_URL"] = args.public_url
    if args.domain:
        env_updates["TIJARA_DOMAIN"] = args.domain
        env_updates["ODOO_DB_FILTER"] = "^%d$|^%h$"
        env_updates["ODOO_PROXY_MODE"] = "True"
        env_updates["TIJARA_PUBLIC_URL"] = "https://%s" % args.domain
    if args.production:
        env_updates.setdefault("TIJARA_ENV", "production")
        env_updates.setdefault("ODOO_WORKERS", "2")
        env_updates.setdefault("ODOO_LIST_DB", "False")
    if env_updates:
        _upsert_env(root / ENV_FILE, env_updates, dry_run=args.dry_run)

    if args.generate_secrets:
        values = load_runtime_env(root)
        secret_updates = _generate_secret_updates(values)
        if secret_updates:
            _upsert_env(root / SECRET_FILE, secret_updates, dry_run=args.dry_run)
        else:
            print("No placeholder central secrets found to generate.")

    values = load_runtime_env(root)
    if args.production and not args.allow_placeholders:
        blockers = _production_secret_blockers(values)
        if blockers:
            print("Production secret blockers:")
            for blocker in blockers:
                print("- %s" % blocker)
            print("Use --generate-secrets for local generated values or inject a real secret manager.")
            return 2
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    root = args.root
    if cmd_init_config(args) != 0:
        return 2
    if cmd_preflight(args) != 0:
        return 2
    profiles = selected_profiles(
        with_hardware=args.with_hardware,
        with_monitoring=args.with_monitoring,
        all_profiles=args.all_profiles,
    )
    if args.pull:
        run(compose_command(root, ["pull"], profiles), cwd=root, dry_run=args.dry_run, check=False)
    if args.build:
        run(compose_command(root, ["build"], profiles), cwd=root, dry_run=args.dry_run)
    run(compose_command(root, ["up", "-d"], profiles), cwd=root, dry_run=args.dry_run)
    if args.install_suite:
        run(["make", "install-suite", "DB=%s" % args.db], cwd=root, dry_run=args.dry_run)
    if args.seed_demo:
        run(["make", "seed-pos-demo", "DB=%s" % args.db], cwd=root, dry_run=args.dry_run)
    values = load_runtime_env(root)
    print()
    print("Hosted Tijara Suite endpoints:")
    for name, url in service_urls(values, host=args.host_label).items():
        print("- %s: %s" % (name, url))
    print()
    print("Next: configure reverse proxy/TLS, monitoring alerts, backups, and production secret-manager evidence.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap and host Tijara Suite on a server.")
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help="Project root. Defaults to this repo.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files or services.")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight", help="Check required tooling and Compose config.")
    preflight.add_argument("--dry-run", action="store_true", help="Print actions without changing files or services.")
    preflight.add_argument("--all-profiles", action="store_true", help="Validate with all Compose profiles.")
    preflight.set_defaults(func=cmd_preflight)

    init_config = sub.add_parser("init-config", help="Create and update central config/secret files.")
    init_config.add_argument("--dry-run", action="store_true", help="Print actions without changing files or services.")
    add_config_flags(init_config)
    init_config.set_defaults(func=cmd_init_config)

    deploy = sub.add_parser("deploy", help="Initialize config and start the hosted stack.")
    deploy.add_argument("--dry-run", action="store_true", help="Print actions without changing files or services.")
    add_config_flags(deploy)
    deploy.add_argument("--with-hardware", action="store_true", help="Start hardware bridge profile.")
    deploy.add_argument("--with-monitoring", action="store_true", help="Start monitoring profile.")
    deploy.add_argument("--all-profiles", action="store_true", help="Start every optional profile.")
    deploy.add_argument("--pull", action=argparse.BooleanOptionalAction, default=True, help="Pull images before startup.")
    deploy.add_argument("--build", action="store_true", help="Build local services before startup.")
    deploy.add_argument("--install-suite", action="store_true", help="Install Tijara Odoo modules after startup.")
    deploy.add_argument("--seed-demo", action="store_true", help="Seed local demo POS data after startup.")
    deploy.add_argument("--db", default="tijara_dev", help="Odoo database for install/seed.")
    deploy.add_argument("--host-label", default="localhost", help="Host label printed in endpoint summary.")
    deploy.set_defaults(func=cmd_deploy)
    return parser


def add_config_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--environment", choices=("development", "staging", "production"), help="Set TIJARA_ENV.")
    parser.add_argument("--public-url", help="Set TIJARA_PUBLIC_URL.")
    parser.add_argument("--domain", help="Set production public URL to https://DOMAIN and enable proxy defaults.")
    parser.add_argument("--production", action="store_true", help="Apply production-safe defaults and block placeholders.")
    parser.add_argument("--generate-secrets", action="store_true", help="Generate local random values for placeholder secrets.")
    parser.add_argument("--allow-placeholders", action="store_true", help="Allow placeholders even with --production.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.root = args.root.resolve()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
