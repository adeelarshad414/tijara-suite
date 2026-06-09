#!/usr/bin/env python3
"""Shared Tijara Suite deployment/service helpers."""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_TEMPLATE = ".env.example"
ENV_FILE = ".env"
SECRET_TEMPLATE = "secrets/.env.secrets.example"
SECRET_FILE = "secrets/.env.secrets"
KNOWN_PROFILES = ("hardware", "monitoring")


def repo_path(root: Optional[Path] = None, *parts: str) -> Path:
    base = root or ROOT_DIR
    return base.joinpath(*parts)


def command_text(command: list[str]) -> str:
    return " ".join(command)


def run(
    command: list[str],
    *,
    cwd: Optional[Path] = None,
    dry_run: bool = False,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("+ %s" % command_text(command))
    if dry_run:
        return subprocess.CompletedProcess(command, 0, "", "")
    return subprocess.run(
        command,
        cwd=str(cwd or ROOT_DIR),
        check=check,
        text=True,
        capture_output=capture,
    )


def has_command(name: str) -> bool:
    return shutil.which(name) is not None


def check_docker_compose(root: Path, dry_run: bool = False) -> bool:
    if not has_command("docker"):
        print("Missing required command: docker", file=sys.stderr)
        return False
    result = run(["docker", "compose", "version"], cwd=root, dry_run=dry_run, check=False, capture=True)
    if result.returncode != 0:
        print("Docker Compose v2 is required.", file=sys.stderr)
        return False
    return True


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_runtime_env(root: Path) -> dict[str, str]:
    values = parse_env_file(repo_path(root, ENV_TEMPLATE))
    values.update(parse_env_file(repo_path(root, ENV_FILE)))
    values.update(parse_env_file(repo_path(root, SECRET_TEMPLATE)))
    values.update(parse_env_file(repo_path(root, SECRET_FILE)))
    values.update(os.environ)
    return values


def ensure_env_files(root: Path, *, dry_run: bool = False) -> list[str]:
    created: list[str] = []
    env_path = repo_path(root, ENV_FILE)
    env_template = repo_path(root, ENV_TEMPLATE)
    if not env_path.exists() and env_template.is_file():
        print("Create %s from %s" % (ENV_FILE, ENV_TEMPLATE))
        if not dry_run:
            env_path.write_text(env_template.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(ENV_FILE)

    secret_path = repo_path(root, SECRET_FILE)
    secret_template = repo_path(root, SECRET_TEMPLATE)
    if not secret_path.exists() and secret_template.is_file():
        print("Create %s from %s" % (SECRET_FILE, SECRET_TEMPLATE))
        if not dry_run:
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            secret_path.write_text(secret_template.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(SECRET_FILE)
    return created


def compose_command(root: Path, args: list[str], profiles: Sequence[str] = ()) -> list[str]:
    command = ["docker", "compose"]
    if repo_path(root, ENV_FILE).is_file():
        command.extend(["--env-file", str(repo_path(root, ENV_FILE))])
    if repo_path(root, SECRET_FILE).is_file():
        command.extend(["--env-file", str(repo_path(root, SECRET_FILE))])
    for profile in profiles:
        command.extend(["--profile", profile])
    command.extend(args)
    return command


def selected_profiles(with_hardware: bool = False, with_monitoring: bool = False, all_profiles: bool = False) -> list[str]:
    if all_profiles:
        return list(KNOWN_PROFILES)
    profiles: list[str] = []
    if with_hardware:
        profiles.append("hardware")
    if with_monitoring:
        profiles.append("monitoring")
    return profiles


def env_value(values: dict[str, str], key: str, fallback: str) -> str:
    return str(values.get(key) or fallback)


def known_ports(values: dict[str, str]) -> dict[str, int]:
    pairs = {
        "odoo": env_value(values, "HTTP_PORT", "8069"),
        "longpolling": env_value(values, "LONGPOLLING_PORT", "8072"),
        "postgres": "5432",
        "hardware_bridge": env_value(values, "TIJARA_BRIDGE_PORT", "9109"),
        "prometheus": env_value(values, "PROMETHEUS_PORT", "9090"),
        "blackbox": env_value(values, "BLACKBOX_PORT", "9115"),
        "alertmanager": env_value(values, "ALERTMANAGER_PORT", "9093"),
        "pushgateway": env_value(values, "PUSHGATEWAY_PORT", "9091"),
        "loki": env_value(values, "LOKI_PORT", "3100"),
        "grafana": env_value(values, "GRAFANA_PORT", "3000"),
    }
    ports: dict[str, int] = {}
    for name, value in pairs.items():
        try:
            ports[name] = int(value)
        except (TypeError, ValueError):
            continue
    return ports


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_http(url: str, timeout_seconds: int = 90) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(2)
    return False


def kill_port(port: int, *, dry_run: bool = False) -> None:
    system = platform.system().lower()
    if system == "windows":
        result = run(["netstat", "-ano"], dry_run=dry_run, check=False, capture=True)
        pids = set()
        for line in result.stdout.splitlines():
            if ":%s" % port in line:
                parts = line.split()
                if parts and parts[-1].isdigit():
                    pids.add(parts[-1])
        for pid in sorted(pids):
            run(["taskkill", "/PID", pid, "/F"], dry_run=dry_run, check=False)
        return

    if has_command("lsof"):
        result = run(["lsof", "-ti", ":%s" % port], dry_run=dry_run, check=False, capture=True)
        for pid in sorted(set(result.stdout.split())):
            if pid.isdigit():
                run(["kill", "-9", pid], dry_run=dry_run, check=False)
        return

    if has_command("fuser"):
        run(["fuser", "-k", "%s/tcp" % port], dry_run=dry_run, check=False)


def service_urls(values: dict[str, str], host: str = "localhost") -> dict[str, str]:
    ports = known_ports(values)
    urls = {
        "Odoo web": "http://%s:%s" % (host, ports.get("odoo", 8069)),
        "Odoo longpolling": "http://%s:%s" % (host, ports.get("longpolling", 8072)),
        "PostgreSQL": "%s:%s" % (host, ports.get("postgres", 5432)),
    }
    if "hardware_bridge" in ports:
        urls["Hardware bridge"] = "http://%s:%s" % (host, ports["hardware_bridge"])
    if "prometheus" in ports:
        urls["Prometheus"] = "http://%s:%s" % (host, ports["prometheus"])
    if "pushgateway" in ports:
        urls["Pushgateway"] = "http://%s:%s" % (host, ports["pushgateway"])
    if "grafana" in ports:
        urls["Grafana"] = "http://%s:%s" % (host, ports["grafana"])
    return urls
