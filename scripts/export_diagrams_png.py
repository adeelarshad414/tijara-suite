#!/usr/bin/env python3
"""Export Mermaid diagrams from docs/DIAGRAMS.md to PNG files."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "DIAGRAMS.md"
OUTPUT_ROOT = ROOT / "docs" / "diagrams"
MMD_DIR = OUTPUT_ROOT / "mmd"
PNG_DIR = OUTPUT_ROOT / "png"
README = OUTPUT_ROOT / "README.md"
PUPPETEER_CONFIG = ROOT / "deploy" / "runtime" / "diagram-export" / "puppeteer-config.json"


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "diagram"


def extract_diagrams(markdown: str) -> list[dict[str, str]]:
    diagrams: list[dict[str, str]] = []
    current_heading = "diagram"
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("## "):
            current_heading = line[3:].strip()
        if line.strip() == "```mermaid":
            start_line = index + 1
            block: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "```":
                block.append(lines[index])
                index += 1
            diagram_number = len(diagrams) + 1
            title = current_heading
            slug = f"{diagram_number:02d}-{slugify(title)}"
            diagrams.append(
                {
                    "title": title,
                    "slug": slug,
                    "source_line": str(start_line),
                    "content": "\n".join(block).strip() + "\n",
                }
            )
        index += 1
    return diagrams


def browser_executable() -> str:
    env_path = shutil.os.environ.get("MERMAID_CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    try:
        result = subprocess.run(
            ["node", "-e", "const { chromium } = require('playwright'); console.log(chromium.executablePath())"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        candidate = result.stdout.strip()
        if candidate and Path(candidate).exists():
            return candidate
    except Exception:
        pass

    mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac_chrome.exists():
        return str(mac_chrome)

    for command in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        candidate = shutil.which(command)
        if candidate:
            return candidate
    return ""


def write_readme(diagrams: list[dict[str, str]]) -> None:
    rows = [
        "# Tijara Diagram PNG Exports",
        "",
        "These files are generated from the Mermaid blocks in `../DIAGRAMS.md`.",
        "",
        "Regenerate them from the repository root with:",
        "",
        "```bash",
        "npm run docs:diagrams:png",
        "```",
        "",
        "| Diagram | Mermaid source | PNG export |",
        "|---|---|---|",
    ]
    for diagram in diagrams:
        rows.append(
            "| {title} | [mmd/{slug}.mmd](mmd/{slug}.mmd) | [png/{slug}.png](png/{slug}.png) |".format(
                title=diagram["title"],
                slug=diagram["slug"],
            )
        )
    README.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    markdown = SOURCE.read_text(encoding="utf-8")
    diagrams = extract_diagrams(markdown)
    if not diagrams:
        print(f"No Mermaid diagrams found in {SOURCE}", file=sys.stderr)
        return 1

    MMD_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    PUPPETEER_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    executable_path = browser_executable()
    puppeteer_config = {
        "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    }
    if executable_path:
        puppeteer_config["executablePath"] = executable_path
    PUPPETEER_CONFIG.write_text(json.dumps(puppeteer_config, indent=2) + "\n", encoding="utf-8")

    mmdc = ROOT / "node_modules" / ".bin" / "mmdc"
    if not mmdc.exists():
        print("Mermaid CLI not found. Run `npm install` first.", file=sys.stderr)
        return 1

    for diagram in diagrams:
        mmd_path = MMD_DIR / f"{diagram['slug']}.mmd"
        png_path = PNG_DIR / f"{diagram['slug']}.png"
        mmd_path.write_text(diagram["content"], encoding="utf-8")
        command = [
            str(mmdc),
            "--input",
            str(mmd_path),
            "--output",
            str(png_path),
            "--backgroundColor",
            "white",
            "--scale",
            "2",
            "--puppeteerConfigFile",
            str(PUPPETEER_CONFIG),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        print(f"rendered {png_path.relative_to(ROOT)}")

    write_readme(diagrams)
    print(f"rendered {len(diagrams)} diagrams to {PNG_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
