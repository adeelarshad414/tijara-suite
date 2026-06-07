#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { chromium } = require("@playwright/test");

const root = path.resolve(__dirname, "..");
const specPath = path.join(root, "docs", "SPEC_MAP.json");
const credentialsPath = path.join(root, "docs", "TEST_CREDENTIALS.csv");
const outputRoot = path.join(root, "docs", "screenshots");

function slug(value) {
  return String(value || "screen")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "screen";
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = (lines.shift() || "").split(",");
  return lines.map((line) => {
    const values = line.split(",");
    return Object.fromEntries(header.map((key, index) => [key, values[index] || ""]));
  });
}

function publicScreens(spec) {
  return (spec.screen_inventory || []).filter((screen) => screen.auth === "public");
}

function personaScreens(spec, persona) {
  return (spec.screen_inventory || []).filter((screen) => {
    if (screen.auth === "public") return true;
    return (screen.personas || []).includes(persona.persona);
  });
}

async function login(page, baseUrl, credential) {
  await page.goto(`${baseUrl}/web/login`, { waitUntil: "domcontentloaded", timeout: 15000 });
  await page.locator('input[name="login"]').fill(credential.email, { timeout: 5000 });
  await page.locator('input[name="password"]').fill(credential.password, { timeout: 5000 });
  await Promise.all([
    page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {}),
    page.locator('button[type="submit"], input[type="submit"]').first().click(),
  ]);
}

async function captureScreen(page, baseUrl, personaDir, screen) {
  const target = screen.route_path.startsWith("http") ? screen.route_path : `${baseUrl}${screen.route_path}`;
  const file = path.join(personaDir, `${slug(screen.name || screen.route_path)}.png`);
  try {
    await page.goto(target, { waitUntil: "networkidle", timeout: 20000 });
    await page.keyboard.press("Escape").catch(() => {});
    await page.screenshot({ path: file, fullPage: true });
    return { screen: screen.name, path: file, status: "captured" };
  } catch (error) {
    const errorFile = path.join(personaDir, `${slug(screen.name || screen.route_path)}-error.png`);
    await page.screenshot({ path: errorFile, fullPage: true }).catch(() => {});
    return { screen: screen.name, path: errorFile, status: "error", message: error.message };
  }
}

function writeIndex(results) {
  const lines = ["# Screenshot Index", ""];
  for (const result of results) {
    lines.push(`## ${result.persona}`);
    for (const item of result.screens) {
      const rel = path.relative(outputRoot, item.path).replace(/\\/g, "/");
      lines.push(`- ${item.screen}: ${item.status}`);
      if (fs.existsSync(item.path)) {
        lines.push(`  ![${item.screen}](${rel})`);
      }
      if (item.message) lines.push(`  - ${item.message}`);
    }
    lines.push("");
  }
  fs.writeFileSync(path.join(outputRoot, "INDEX.md"), lines.join("\n"));
}

(async () => {
  if (!fs.existsSync(specPath)) {
    throw new Error("docs/SPEC_MAP.json is required before screenshot capture.");
  }
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  const credentials = fs.existsSync(credentialsPath)
    ? parseCsv(fs.readFileSync(credentialsPath, "utf8"))
    : [];
  const baseUrl = process.env.TIJARA_SCREENSHOT_BASE_URL || spec.base_urls.web || "http://localhost:8069";

  fs.mkdirSync(outputRoot, { recursive: true });
  const browser = await chromium.launch({ headless: process.env.TIJARA_SCREENSHOT_HEADED !== "1" });
  const results = [];

  try {
    const publicPersona = {
      persona: "public_display",
      email: "",
      password: "",
    };
    const personas = credentials.length ? credentials : [publicPersona];
    for (const credential of personas) {
      const personaDir = path.join(outputRoot, slug(credential.persona));
      fs.mkdirSync(personaDir, { recursive: true });
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      const isPublicPersona = !credential.email || credential.persona === "public_display";
      const screens = isPublicPersona ? publicScreens(spec) : personaScreens(spec, credential);
      const captured = [];
      try {
        if (!isPublicPersona) {
          await login(page, baseUrl, credential);
        }
      } catch (error) {
        captured.push({
          screen: "login",
          path: path.join(personaDir, "login-error.png"),
          status: "error",
          message: error.message,
        });
        await page.screenshot({ path: captured[0].path, fullPage: true }).catch(() => {});
      }
      for (const screen of screens) {
        captured.push(await captureScreen(page, baseUrl, personaDir, screen));
      }
      await context.close();
      results.push({ persona: credential.persona, screens: captured });
    }
  } finally {
    await browser.close();
  }

  writeIndex(results);
  console.log(`Screenshot index written to ${path.join(outputRoot, "INDEX.md")}`);
})().catch((error) => {
  fs.mkdirSync(outputRoot, { recursive: true });
  fs.writeFileSync(path.join(outputRoot, "CAPTURE_ERROR.txt"), `${error.stack || error}\n`);
  console.error(error);
  process.exitCode = 1;
});
