import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.ODOO_BASE_URL || "http://127.0.0.1:8069";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60000,
  expect: {
    timeout: 10000
  },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] }
    },
    {
      name: "firefox-desktop",
      use: { ...devices["Desktop Firefox"] }
    },
    {
      name: "webkit-desktop",
      use: { ...devices["Desktop Safari"] }
    },
    {
      name: "mobile-touch",
      use: { ...devices["Pixel 7"] }
    },
    {
      name: "tablet-touch",
      use: { ...devices["iPad Pro 11"] }
    }
  ]
});
