#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { chromium } = require("@playwright/test");

const root = path.resolve(__dirname, "..");
const specPath = path.join(root, "docs", "SPEC_MAP.json");
const clipDir = path.join(root, "docs", "video-clips");

function slug(value) {
  return String(value || "demo")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "demo";
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function visit(page, baseUrl, route) {
  const target = route.startsWith("http") ? route : `${baseUrl}${route}`;
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.keyboard.press("Escape").catch(() => {});
  await sleep(1200);
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })).catch(() => {});
  await sleep(1200);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })).catch(() => {});
  await sleep(800);
}

(async () => {
  if (!fs.existsSync(specPath)) {
    throw new Error("docs/SPEC_MAP.json is required before demo recording.");
  }
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  const baseUrl = process.env.TIJARA_DEMO_BASE_URL || spec.base_urls.web || "http://localhost:8069";
  const publicScreens = (spec.screen_inventory || []).filter((screen) => screen.auth === "public");
  const personas = (spec.personas || []).slice(0, Number(process.env.TIJARA_DEMO_PERSONA_LIMIT || 5));

  fs.mkdirSync(clipDir, { recursive: true });
  const browser = await chromium.launch({ headless: process.env.TIJARA_DEMO_HEADED !== "1" });
  const recorded = [];

  try {
    const targets = personas.length ? personas : [{ role: "public_display", key_workflows: ["Public displays"] }];
    for (const persona of targets) {
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        recordVideo: { dir: clipDir, size: { width: 1440, height: 900 } },
      });
      const page = await context.newPage();
      const routes = publicScreens.length
        ? publicScreens.map((screen) => screen.route_path)
        : ["/web/login"];
      for (const route of routes.slice(0, 5)) {
        await visit(page, baseUrl, route).catch(async (error) => {
          await page.setContent(`<pre>${String(error.message || error)}</pre>`);
          await sleep(1000);
        });
      }
      await context.close();
      recorded.push(`${slug(persona.role)} demo clip recorded by Playwright context.`);
    }
  } finally {
    await browser.close();
  }

  fs.writeFileSync(path.join(clipDir, "README.md"), [
    "# Demo Video Clips",
    "",
    "Playwright writes browser video files into this directory at runtime.",
    "Run `bash scripts/assemble-video.sh` after recording to assemble clips with ffmpeg when available.",
    "",
    ...recorded.map((line) => `- ${line}`),
    "",
  ].join("\n"));
  console.log(`Video clip notes written to ${path.join(clipDir, "README.md")}`);
})().catch((error) => {
  fs.mkdirSync(clipDir, { recursive: true });
  fs.writeFileSync(path.join(clipDir, "RECORDING_ERROR.txt"), `${error.stack || error}\n`);
  console.error(error);
  process.exitCode = 1;
});
