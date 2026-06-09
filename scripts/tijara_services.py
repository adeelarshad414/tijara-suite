#!/usr/bin/env python3
"""Start, stop, restart, and inspect Tijara Suite services."""

from __future__ import annotations

import argparse
from pathlib import Path

from tijara_ops_common import (
    ROOT_DIR,
    check_docker_compose,
    compose_command,
    ensure_env_files,
    is_port_open,
    known_ports,
    load_runtime_env,
    run,
    selected_profiles,
    service_urls,
    wait_for_http,
    kill_port,
)


def _profiles(args: argparse.Namespace) -> list[str]:
    return selected_profiles(
        with_hardware=args.with_hardware,
        with_monitoring=args.with_monitoring,
        all_profiles=getattr(args, "all_profiles", False),
    )


def cmd_start(args: argparse.Namespace) -> int:
    root = args.root
    if not check_docker_compose(root, args.dry_run):
        return 2
    ensure_env_files(root, dry_run=args.dry_run)
    run(compose_command(root, ["config", "--quiet"], _profiles(args)), cwd=root, dry_run=args.dry_run)
    run(compose_command(root, ["up", "-d"], _profiles(args)), cwd=root, dry_run=args.dry_run)

    values = load_runtime_env(root)
    if args.wait and not args.dry_run:
        port = int(values.get("HTTP_PORT") or 8069)
        url = "http://localhost:%s/web/login" % port
        print("Waiting for Odoo: %s" % url)
        if not wait_for_http(url, args.timeout):
            print("Odoo did not become healthy within %ss." % args.timeout)

    if args.install_suite:
        run(["make", "install-suite", "DB=%s" % args.db], cwd=root, dry_run=args.dry_run)
    if args.seed_demo:
        run(["make", "seed-pos-demo", "DB=%s" % args.db], cwd=root, dry_run=args.dry_run)

    print_status(root)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    root = args.root
    if check_docker_compose(root, args.dry_run):
        run(compose_command(root, ["down"], selected_profiles(all_profiles=True)), cwd=root, dry_run=args.dry_run, check=False)

    values = load_runtime_env(root)
    if args.force_kill_ports:
        for port in sorted(set(known_ports(values).values())):
            kill_port(port, dry_run=args.dry_run)
    print_status(root)
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    stop_args = argparse.Namespace(root=args.root, dry_run=args.dry_run, force_kill_ports=args.force_kill_ports)
    cmd_stop(stop_args)
    return cmd_start(args)


def print_status(root: Path) -> None:
    values = load_runtime_env(root)
    ports = known_ports(values)
    port_keys = {
        "Odoo web": "odoo",
        "Odoo longpolling": "longpolling",
        "PostgreSQL": "postgres",
        "Hardware bridge": "hardware_bridge",
        "Prometheus": "prometheus",
        "Grafana": "grafana",
    }
    print()
    print("%-22s %-34s %-12s" % ("Service", "URL/Port", "Port state"))
    for name, url in service_urls(values).items():
        port = ports.get(port_keys.get(name, ""))
        state = "open" if port and is_port_open("127.0.0.1", port, timeout=0.5) else "closed"
        print("%-22s %-34s %-12s" % (name, url, state))


def cmd_status(args: argparse.Namespace) -> int:
    root = args.root
    if check_docker_compose(root, args.dry_run):
        run(compose_command(root, ["ps"], selected_profiles(all_profiles=True)), cwd=root, dry_run=args.dry_run, check=False)
    print_status(root)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    root = args.root
    command = ["logs", "--tail", str(args.tail)]
    if args.follow:
        command.append("-f")
    if args.service:
        command.append(args.service)
    run(compose_command(root, command, selected_profiles(all_profiles=True)), cwd=root, dry_run=args.dry_run, check=False)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    root = args.root
    if not check_docker_compose(root, args.dry_run):
        return 2
    ensure_env_files(root, dry_run=args.dry_run)
    command = ["config"] if args.print else ["config", "--quiet"]
    run(compose_command(root, command, _profiles(args)), cwd=root, dry_run=args.dry_run)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Tijara Suite services on a PC or server.")
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help="Project root. Defaults to this repo.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing services.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_dry_run(p: argparse.ArgumentParser) -> None:
        p.add_argument("--dry-run", action="store_true", help="Print actions without changing services.")

    def add_runtime_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--with-hardware", action="store_true", help="Include the hardware bridge profile.")
        p.add_argument("--with-monitoring", action="store_true", help="Include Prometheus/Grafana monitoring.")
        p.add_argument("--all-profiles", action="store_true", help="Include all optional profiles.")

    start = sub.add_parser("start", help="Create missing env files and start services.")
    add_dry_run(start)
    add_runtime_flags(start)
    start.add_argument("--db", default="tijara_dev", help="Odoo database for optional install/seed.")
    start.add_argument("--install-suite", action="store_true", help="Install Tijara modules after startup.")
    start.add_argument("--seed-demo", action="store_true", help="Seed demo POS data after startup.")
    start.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True, help="Wait for Odoo login route.")
    start.add_argument("--timeout", type=int, default=90, help="Odoo health wait timeout in seconds.")
    start.set_defaults(func=cmd_start)

    stop = sub.add_parser("stop", help="Stop all Compose services.")
    add_dry_run(stop)
    stop.add_argument("--force-kill-ports", action="store_true", help="Kill any process still using known Tijara ports.")
    stop.set_defaults(func=cmd_stop)

    restart = sub.add_parser("restart", help="Stop and start services.")
    add_dry_run(restart)
    add_runtime_flags(restart)
    restart.add_argument("--db", default="tijara_dev")
    restart.add_argument("--install-suite", action="store_true")
    restart.add_argument("--seed-demo", action="store_true")
    restart.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    restart.add_argument("--timeout", type=int, default=90)
    restart.add_argument("--force-kill-ports", action="store_true")
    restart.set_defaults(func=cmd_restart)

    status = sub.add_parser("status", help="Show Compose and port status.")
    add_dry_run(status)
    status.set_defaults(func=cmd_status)

    logs = sub.add_parser("logs", help="Show Compose logs.")
    add_dry_run(logs)
    logs.add_argument("service", nargs="?", help="Optional Compose service name.")
    logs.add_argument("--tail", default="120", help="Number of lines to show.")
    logs.add_argument("--follow", action="store_true", help="Follow logs.")
    logs.set_defaults(func=cmd_logs)

    config = sub.add_parser("config", help="Render Docker Compose config.")
    add_dry_run(config)
    add_runtime_flags(config)
    config.add_argument("--print", action="store_true", help="Print full rendered config. May include resolved secrets.")
    config.set_defaults(func=cmd_config)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.root = args.root.resolve()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
