import { expect, test } from "@playwright/test";
import { login, odooCallKw } from "./helpers.mjs";

test("refund/exchange backend route opens for invoice barcode scanning", async ({ page }) => {
  test.skip(
    !process.env.ODOO_USERNAME || !process.env.ODOO_PASSWORD || !process.env.TIJARA_REFUND_ACTION_URL,
    "Set ODOO_USERNAME, ODOO_PASSWORD, and TIJARA_REFUND_ACTION_URL for refund E2E."
  );

  await login(page);
  await page.goto(process.env.TIJARA_REFUND_ACTION_URL, { waitUntil: "domcontentloaded" });

  await expect(page.locator("body")).toContainText(/Refund|Exchange|Invoice Barcode|Scan Invoice/i);
});

test("authenticated refund barcode scan matches a seeded POS receipt", async ({ page }) => {
  test.skip(
    !process.env.ODOO_USERNAME ||
      !process.env.ODOO_PASSWORD ||
      !process.env.TIJARA_E2E_REFUND_BARCODE ||
      !process.env.TIJARA_E2E_REFUND_REASON_ID,
    "Set ODOO credentials, TIJARA_E2E_REFUND_BARCODE, and TIJARA_E2E_REFUND_REASON_ID for refund barcode scan E2E."
  );

  await login(page);
  const requestId = await odooCallKw(page, "tijara.exchange.request", "create", [
    {
      scanned_invoice_barcode: process.env.TIJARA_E2E_REFUND_BARCODE,
      reason_id: Number(process.env.TIJARA_E2E_REFUND_REASON_ID)
    }
  ]);

  await odooCallKw(page, "tijara.exchange.request", "action_scan_invoice_barcode", [[requestId]]);
  const [request] = await odooCallKw(page, "tijara.exchange.request", "read", [
    [requestId],
    ["scan_status", "matched_pos_order_id", "line_ids", "scan_result_message"]
  ]);

  expect(request.scan_status).toBe("found");
  expect(request.matched_pos_order_id?.[0] || request.matched_pos_order_id).toBeTruthy();
  expect(request.line_ids.length).toBeGreaterThan(0);
});

test("backend Tijara receipt or invoice report URL renders", async ({ page }) => {
  test.skip(
    !process.env.ODOO_USERNAME || !process.env.ODOO_PASSWORD || !process.env.TIJARA_REPORT_ORDER_URL,
    "Set ODOO_USERNAME, ODOO_PASSWORD, and TIJARA_REPORT_ORDER_URL for report E2E."
  );

  await login(page);
  await page.goto(process.env.TIJARA_REPORT_ORDER_URL, { waitUntil: "domcontentloaded" });

  await expect(page.locator("body")).toContainText(/Tijara|Invoice|Receipt|PKR/i);
});
