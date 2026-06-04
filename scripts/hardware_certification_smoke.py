#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "hardware-bridge"))

from tijara_bridge.drivers import build_driver_output  # noqa: E402


def load_profiles(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("profiles", [])


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT_DIR / "hardware-bridge" / "config" / "certification_profiles.example.json"
    profiles = load_profiles(path)
    if not profiles:
        print(f"No hardware certification profiles found in {path}", file=sys.stderr)
        return 1

    failures = []
    for profile in profiles:
        device = profile.get("device") or {}
        for test in profile.get("tests", []):
            operation = test["operation"]
            payload = dict(test.get("payload") or {})
            payload.setdefault("device_code", device.get("code") or profile.get("code"))
            payload.setdefault("printer_language", device.get("printer_language"))
            output = build_driver_output(operation, payload, device, dry_run=True)
            if not output:
                failures.append(f"{profile.get('code')}: {operation} produced no driver output")
                continue
            if operation != "read_scale" and output.get("byte_count", 0) <= 0:
                failures.append(f"{profile.get('code')}: {operation} produced empty bytes")
            print(
                "%s %-18s format=%s bytes=%s status=%s"
                % (
                    profile.get("code"),
                    operation,
                    output.get("format"),
                    output.get("byte_count"),
                    (output.get("delivery") or {}).get("status"),
                )
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

