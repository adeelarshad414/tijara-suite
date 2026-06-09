#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const dashboardsDir = path.join(root, "deploy", "monitoring", "grafana", "dashboards");

function utcNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function defaultRunId() {
  return utcNow().replace(/[-:]/g, "").replace("T", "-").replace("Z", "");
}

function slug(value) {
  return (
    String(value || "dashboard")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "dashboard"
  );
}

function parseEnvFile(file) {
  if (!fs.existsSync(file)) return {};
  const values = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim().replace(/^['"]|['"]$/g, "");
    if (key) values[key] = value;
  }
  return values;
}

function centralEnv() {
  return {
    ...parseEnvFile(path.join(root, ".env")),
    ...parseEnvFile(path.join(root, "secrets", ".env.secrets")),
    ...process.env,
  };
}

function parseArgs(argv) {
  const args = {
    dashboards: [],
    metadataOnly: false,
    skipApi: false,
    skipBrowser: false,
    headed: false,
    nonStrict: false,
    timeout: 15000,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`${arg} requires a value.`);
      return argv[index];
    };
    if (arg === "--run-id") args.runId = next();
    else if (arg === "--output") args.output = next();
    else if (arg === "--grafana-url") args.grafanaUrl = next();
    else if (arg === "--username") args.username = next();
    else if (arg === "--password") args.password = next();
    else if (arg === "--dashboard") args.dashboards.push(next());
    else if (arg === "--timeout") args.timeout = Number(next());
    else if (arg === "--metadata-only") args.metadataOnly = true;
    else if (arg === "--skip-api") args.skipApi = true;
    else if (arg === "--skip-browser") args.skipBrowser = true;
    else if (arg === "--headed") args.headed = true;
    else if (arg === "--non-strict") args.nonStrict = true;
    else if (arg === "-h" || arg === "--help") {
      printUsage();
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }
  return args;
}

function printUsage() {
  console.log(`Usage: node scripts/capture-grafana-evidence.js [options]

Captures Grafana dashboard API and screenshot evidence for Tijara Suite.

Options:
  --run-id VALUE          Evidence run id
  --output PATH           Output directory
  --grafana-url URL       Grafana URL (default: TIJARA_GRAFANA_URL or http://localhost:3000)
  --username USER         Grafana admin user (default: GRAFANA_ADMIN_USER or admin)
  --password VALUE        Grafana admin password (default: GRAFANA_ADMIN_PASSWORD)
  --dashboard UID         Limit to one dashboard UID/title/slug, repeatable
  --metadata-only         Validate committed dashboard JSON only
  --skip-api              Skip Grafana API checks
  --skip-browser          Skip Playwright screenshots
  --headed                Run browser headed
  --non-strict            Convert live API/browser failures into warnings
  --timeout MS            API/browser timeout in milliseconds
  -h, --help              Show this help`);
}

function loadDashboards(filterValues) {
  const filter = new Set(filterValues.map((value) => slug(value)));
  const files = fs
    .readdirSync(dashboardsDir)
    .filter((name) => name.endsWith(".json"))
    .sort();
  const dashboards = files.map((filename) => {
    const file = path.join(dashboardsDir, filename);
    const payload = JSON.parse(fs.readFileSync(file, "utf8"));
    return {
      uid: payload.uid,
      title: payload.title,
      description: payload.description || "",
      filename,
      file,
      slug: slug(payload.title),
      panelCount: Array.isArray(payload.panels) ? payload.panels.length : 0,
    };
  });
  if (!filter.size) return dashboards;
  return dashboards.filter((dashboard) =>
    [dashboard.uid, dashboard.title, dashboard.filename, dashboard.slug].some((value) => filter.has(slug(value))),
  );
}

function row(name, status, message, source = "") {
  return { name, status, message, source };
}

function statusTsv(rows) {
  return [
    "check\tstatus\tmessage\tsource",
    ...rows.map((item) => `${item.name}\t${item.status}\t${item.message}\t${item.source || ""}`),
  ].join("\n");
}

function authHeaders(username, password) {
  if (!username || !password) return {};
  return {
    Authorization: `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`,
  };
}

async function fetchJson(url, headers, timeout) {
  if (typeof fetch !== "function") {
    throw new Error("Node.js fetch is not available. Use Node 18+ or pass --metadata-only.");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      headers: { "User-Agent": "TijaraGrafanaEvidence/1.0", ...headers },
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = { raw: text.slice(0, 400) };
    }
    return { ok: response.ok, statusCode: response.status, payload };
  } finally {
    clearTimeout(timer);
  }
}

async function apiEvidence(args, dashboards, headers) {
  const checks = [];
  const details = {};
  const base = args.grafanaUrl.replace(/\/$/, "");

  try {
    const health = await fetchJson(`${base}/api/health`, headers, args.timeout);
    checks.push(
      row(
        "grafana-api-health",
        health.ok ? "passed" : "failed",
        `Grafana health returned HTTP ${health.statusCode}.`,
        `${base}/api/health`,
      ),
    );
    details.health = health.payload;
  } catch (error) {
    checks.push(row("grafana-api-health", "failed", error.message, `${base}/api/health`));
  }

  let searchPayload = [];
  try {
    const search = await fetchJson(`${base}/api/search?query=Tijara`, headers, args.timeout);
    searchPayload = Array.isArray(search.payload) ? search.payload : [];
    checks.push(
      row(
        "grafana-dashboard-search",
        search.ok ? "passed" : "failed",
        `Grafana search returned HTTP ${search.statusCode} with ${searchPayload.length} dashboard item(s).`,
        `${base}/api/search?query=Tijara`,
      ),
    );
  } catch (error) {
    checks.push(row("grafana-dashboard-search", "failed", error.message, `${base}/api/search?query=Tijara`));
  }
  details.search = searchPayload.map((item) => ({
    uid: item.uid || "",
    title: item.title || "",
    type: item.type || "",
    folderTitle: item.folderTitle || "",
    url: item.url || "",
  }));

  const foundUids = new Set(details.search.map((item) => item.uid).filter(Boolean));
  for (const dashboard of dashboards) {
    const apiUrl = `${base}/api/dashboards/uid/${encodeURIComponent(dashboard.uid)}`;
    try {
      const result = await fetchJson(apiUrl, headers, args.timeout);
      const remoteTitle = result.payload && result.payload.dashboard ? result.payload.dashboard.title : "";
      const status = result.ok && remoteTitle === dashboard.title ? "passed" : "failed";
      checks.push(
        row(
          `grafana-dashboard-${dashboard.uid}`,
          status,
          result.ok
            ? `Dashboard UID ${dashboard.uid} resolved as "${remoteTitle || "untitled"}".`
            : `Dashboard UID ${dashboard.uid} returned HTTP ${result.statusCode}.`,
          apiUrl,
        ),
      );
    } catch (error) {
      checks.push(row(`grafana-dashboard-${dashboard.uid}`, "failed", error.message, apiUrl));
    }
    if (!foundUids.has(dashboard.uid)) {
      checks.push(
        row(
          `grafana-search-contains-${dashboard.uid}`,
          "warning",
          `Dashboard UID ${dashboard.uid} was not present in the Tijara search response.`,
          `${base}/api/search?query=Tijara`,
        ),
      );
    }
  }
  return { checks, details };
}

async function browserEvidence(args, dashboards, output) {
  const screenshotsDir = path.join(output, "screenshots");
  fs.mkdirSync(screenshotsDir, { recursive: true });
  const checks = [];
  const screenshots = [];
  let chromium;
  try {
    chromium = require("@playwright/test").chromium;
  } catch (error) {
    return {
      checks: [row("grafana-browser-playwright", "failed", `Playwright is not available: ${error.message}`)],
      screenshots,
    };
  }

  const base = args.grafanaUrl.replace(/\/$/, "");
  const browser = await chromium.launch({ headless: !args.headed });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, ignoreHTTPSErrors: true });
    const page = await context.newPage();
    await page.goto(`${base}/login`, { waitUntil: "domcontentloaded", timeout: args.timeout });
    const loginInput = page.locator('input[name="user"], input[name="login"]').first();
    if (await loginInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await loginInput.fill(args.username);
      await page.locator('input[name="password"]').first().fill(args.password || "");
      await Promise.all([
        page.waitForLoadState("networkidle", { timeout: args.timeout }).catch(() => {}),
        page.locator('button[type="submit"]').first().click(),
      ]);
      await page.waitForTimeout(1200);
    }

    for (const dashboard of dashboards) {
      const file = path.join(screenshotsDir, `${dashboard.uid}.png`);
      const url = `${base}/d/${encodeURIComponent(dashboard.uid)}/${dashboard.slug}?orgId=1&from=now-6h&to=now&kiosk=tv`;
      try {
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: args.timeout });
        await page.locator("body").waitFor({ timeout: args.timeout }).catch(() => {});
        await page.getByText(dashboard.title, { exact: false }).first().waitFor({ timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(2500);
        await page.screenshot({ path: file, fullPage: true });
        screenshots.push({ uid: dashboard.uid, title: dashboard.title, path: file, url });
        checks.push(row(`grafana-screenshot-${dashboard.uid}`, "passed", "Dashboard screenshot captured.", file));
      } catch (error) {
        const errorFile = path.join(screenshotsDir, `${dashboard.uid}-error.png`);
        await page.screenshot({ path: errorFile, fullPage: true }).catch(() => {});
        screenshots.push({ uid: dashboard.uid, title: dashboard.title, path: errorFile, url, error: error.message });
        checks.push(row(`grafana-screenshot-${dashboard.uid}`, "failed", error.message, errorFile));
      }
    }
    await context.close();
  } finally {
    await browser.close();
  }
  return { checks, screenshots };
}

function summary(context, dashboards, rows, blockers, warnings, screenshots) {
  const dashboardLines = dashboards
    .map((dashboard) => `- ${dashboard.title} (${dashboard.uid}): ${dashboard.panelCount} panel(s)`)
    .join("\n");
  const checkLines = rows.map((item) => `- ${item.name}: ${item.status} - ${item.message}`).join("\n");
  const screenshotLines = screenshots.length
    ? screenshots.map((item) => `- ${item.title}: ${path.relative(context.output, item.path).replace(/\\/g, "/")}`).join("\n")
    : "- None captured";
  return `# Grafana Dashboard Evidence

- Decision: ${context.decision}
- Run ID: ${context.runId}
- Generated: ${context.generatedAt}
- Grafana URL: ${context.grafanaUrl}
- Output: ${context.output}

## Dashboards

${dashboardLines}

## Checks

${checkLines}

## Screenshots

${screenshotLines}

## Blockers

${blockers.length ? blockers.map((item) => `- ${item}`).join("\n") : "- None"}

## Warnings

${warnings.length ? warnings.map((item) => `- ${item}`).join("\n") : "- None"}
`;
}

(async () => {
  const env = centralEnv();
  const args = parseArgs(process.argv);
  args.runId = args.runId || env.TIJARA_GRAFANA_EVIDENCE_RUN_ID || defaultRunId();
  args.grafanaUrl = args.grafanaUrl || env.TIJARA_GRAFANA_URL || "http://localhost:3000";
  args.username = args.username || env.GRAFANA_ADMIN_USER || "admin";
  args.password = args.password || env.GRAFANA_ADMIN_PASSWORD || "";
  args.output = path.resolve(
    root,
    args.output || env.TIJARA_GRAFANA_EVIDENCE_OUTPUT || path.join("deploy", "runtime", "grafana-dashboard-evidence", args.runId),
  );
  if (env.TIJARA_GRAFANA_DASHBOARDS) {
    args.dashboards.push(...env.TIJARA_GRAFANA_DASHBOARDS.split(",").map((item) => item.trim()).filter(Boolean));
  }
  if (args.metadataOnly) {
    args.skipApi = true;
    args.skipBrowser = true;
  }

  fs.mkdirSync(args.output, { recursive: true });
  const dashboards = loadDashboards(args.dashboards);
  const rows = [];
  const dashboardDetails = dashboards.map((dashboard) => ({
    uid: dashboard.uid,
    title: dashboard.title,
    filename: dashboard.filename,
    panel_count: dashboard.panelCount,
    description: dashboard.description,
  }));

  if (!dashboards.length) {
    rows.push(row("grafana-dashboard-definitions", "failed", "No dashboard definitions matched the selected filter.", dashboardsDir));
  } else {
    rows.push(row("grafana-dashboard-definitions", "passed", `${dashboards.length} committed dashboard definition(s) found.`, dashboardsDir));
  }

  let apiDetails = {};
  if (args.skipApi) {
    rows.push(row("grafana-api-checks", "skipped", "Grafana API checks skipped by operator flag."));
  } else {
    const api = await apiEvidence(args, dashboards, authHeaders(args.username, args.password));
    rows.push(...api.checks);
    apiDetails = api.details;
  }

  let screenshots = [];
  if (args.skipBrowser) {
    rows.push(row("grafana-browser-screenshots", "skipped", "Browser screenshot capture skipped by operator flag."));
  } else {
    const browser = await browserEvidence(args, dashboards, args.output);
    rows.push(...browser.checks);
    screenshots = browser.screenshots;
  }

  const blockers = [];
  const warnings = [];
  for (const item of rows) {
    if (item.status === "failed") {
      if (args.nonStrict) warnings.push(`${item.name}: ${item.message}`);
      else blockers.push(`${item.name}: ${item.message}`);
    } else if (item.status === "warning" || (item.status === "skipped" && !args.metadataOnly)) {
      warnings.push(`${item.name}: ${item.message}`);
    }
  }
  const decision = blockers.length ? "failed" : warnings.length ? "warning" : "passed";
  const ciStatus = blockers.length ? "fail" : warnings.length ? "pass_with_warnings" : "pass";
  const context = {
    runId: args.runId,
    generatedAt: utcNow(),
    grafanaUrl: args.grafanaUrl,
    output: args.output,
    decision,
    ciStatus,
    metadataOnly: args.metadataOnly,
    skipApi: args.skipApi,
    skipBrowser: args.skipBrowser,
    nonStrict: args.nonStrict,
  };
  const manifest = {
    context,
    decision,
    ci_status: ciStatus,
    dashboards: dashboardDetails,
    api: apiDetails,
    screenshots: screenshots.map((item) => ({ ...item, path: path.relative(root, item.path).replace(/\\/g, "/") })),
    checks: rows,
    blockers,
    warnings,
  };
  fs.writeFileSync(path.join(args.output, "grafana-dashboard-evidence.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  fs.writeFileSync(path.join(args.output, "status.tsv"), `${statusTsv(rows)}\n`);
  fs.writeFileSync(path.join(args.output, "summary.md"), summary(context, dashboards, rows, blockers, warnings, screenshots));

  console.log(`Grafana dashboard evidence written to ${args.output}`);
  console.log(`decision=${decision}`);
  console.log(`ci_status=${ciStatus}`);
  if (blockers.length) {
    console.error("Blockers:");
    for (const blocker of blockers) console.error(`- ${blocker}`);
  }
  process.exitCode = blockers.length ? 1 : 0;
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
