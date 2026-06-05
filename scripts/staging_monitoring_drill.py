#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _env(name, default=""):
    return os.environ.get(name, default).strip()


def _check_http(name, url, expected_statuses):
    if not url:
        return {
            "name": name,
            "kind": "http",
            "status": "skipped",
            "message": "URL not configured",
        }
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"Accept": "application/json,text/html,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=float(_env("TIJARA_DRILL_TIMEOUT", "8"))) as response:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            ok = response.status in expected_statuses
            return {
                "name": name,
                "kind": "http",
                "url": url,
                "http_status": response.status,
                "duration_ms": elapsed_ms,
                "status": "passed" if ok else "failed",
            }
    except urllib.error.HTTPError as error:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        ok = error.code in expected_statuses
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "http_status": error.code,
            "duration_ms": elapsed_ms,
            "status": "passed" if ok else "failed",
            "message": str(error),
        }
    except (urllib.error.URLError, TimeoutError) as error:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "duration_ms": elapsed_ms,
            "status": "failed",
            "message": str(error),
        }


def _check_file(name, file_path):
    if not file_path:
        return {
            "name": name,
            "kind": "file",
            "status": "skipped",
            "message": "File path not configured",
        }
    path = Path(file_path)
    if not path.exists():
        return {
            "name": name,
            "kind": "file",
            "path": str(path),
            "status": "failed",
            "message": "Backup artifact does not exist",
        }
    return {
        "name": name,
        "kind": "file",
        "path": str(path),
        "status": "passed",
        "size_bytes": path.stat().st_size,
    }


def _join_url(base_url, path):
    if not base_url:
        return ""
    return "%s/%s" % (base_url.rstrip("/"), path.lstrip("/"))


def main():
    base_url = _env("TIJARA_STAGING_BASE_URL", "http://localhost:8069").rstrip("/")
    bridge_url = _env("TIJARA_HARDWARE_BRIDGE_URL", "http://localhost:9199").rstrip("/")
    prometheus_url = _env("TIJARA_PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
    alertmanager_url = _env("TIJARA_ALERTMANAGER_URL", "http://localhost:9093").rstrip("/")
    grafana_url = _env("TIJARA_GRAFANA_URL", "http://localhost:3000").rstrip("/")

    checks = [
        _check_http("odoo-web", _join_url(base_url, "/web"), {200, 303}),
        _check_http(
            "offline-pos-status",
            _env("TIJARA_OFFLINE_STATUS_URL", _join_url(base_url, "/tijara/offline-pos/status")),
            {200, 401, 403},
        ),
        _check_http("hardware-bridge-health", _join_url(bridge_url, "/health"), {200}),
        _check_http("prometheus-ready", _join_url(prometheus_url, "/-/ready"), {200}),
        _check_http("alertmanager-ready", _join_url(alertmanager_url, "/-/ready"), {200}),
        _check_http("grafana-health", _join_url(grafana_url, "/api/health"), {200}),
        _check_file("backup-artifact", _env("TIJARA_BACKUP_DRILL_FILE")),
    ]
    failed = [check for check in checks if check["status"] == "failed"]
    result = {
        "status": "failed" if failed else "passed",
        "failed_count": len(failed),
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
