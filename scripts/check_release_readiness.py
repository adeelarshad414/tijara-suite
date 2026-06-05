#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _print_items(title, items):
    if not items:
        return
    print(title)
    for item in items:
        print("- %s" % item)


def main():
    parser = argparse.ArgumentParser(
        description="Check Tijara release-readiness.json for CI/CD gating."
    )
    parser.add_argument(
        "readiness_file",
        nargs="?",
        default=os.environ.get("TIJARA_RELEASE_READINESS_FILE", ""),
        help="Path to release-readiness.json.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        default=_truthy(os.environ.get("TIJARA_RELEASE_FAIL_ON_WARNING")),
        help="Treat decision=warning as a failing CI condition.",
    )
    args = parser.parse_args()

    if not args.readiness_file:
        print(
            "Usage: python3 scripts/check_release_readiness.py "
            "deploy/runtime/signoff-packages/<run-id>/release-readiness.json",
            file=sys.stderr,
        )
        return 2

    path = Path(args.readiness_file)
    if not path.is_file():
        print("Release readiness file not found: %s" % path, file=sys.stderr)
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print("Could not read release readiness JSON: %s" % error, file=sys.stderr)
        return 2

    decision = str(data.get("decision") or "").strip().lower()
    ci_status = str(data.get("ci_status") or "").strip().lower()
    package_id = data.get("package_id") or ""
    target_environment = data.get("target_environment") or ""
    git_head = data.get("git_head") or ""

    print("Tijara release readiness")
    print("package_id=%s" % package_id)
    print("target_environment=%s" % target_environment)
    print("git_head=%s" % git_head)
    print("decision=%s" % (decision or "unknown"))
    print("ci_status=%s" % (ci_status or "unknown"))
    _print_items("Blockers:", data.get("blockers") or [])
    _print_items("Warnings:", data.get("warnings") or [])

    if decision == "blocked" or ci_status == "fail":
        return 1
    if decision == "warning" and args.fail_on_warning:
        print("Warnings are configured as failures.")
        return 1
    if decision not in {"ready", "warning"}:
        print("Unknown readiness decision: %s" % (decision or "empty"), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
