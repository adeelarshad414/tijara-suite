import { expect, test } from "@playwright/test";
import { login, odooCallKw } from "./helpers.mjs";

const visibleTimeout = 15000;

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function openPosUi(page) {
  const action = await odooCallKw(page, "pos.config", "open_ui", [
    [Number(process.env.TIJARA_POS_CONFIG_ID)],
  ]);
  await page.goto(action.url || `/pos/ui/${process.env.TIJARA_POS_CONFIG_ID}?from_backend=True`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("body")).toContainText(
    /Point of Sale|Products|Payment|Receipt|Register|Orders|Pay|Cart/i,
    { timeout: 30000 }
  );
}

async function clickFirstVisible(page, selectors, label) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      await locator.waitFor({ state: "visible", timeout: 4000 });
      await locator.click();
      return selector;
    } catch {
      // Try the next selector; Odoo POS labels/classes differ by version/theme.
    }
  }
  throw new Error(`Could not find visible ${label}. Tried: ${selectors.join(", ")}`);
}

async function fillSearchIfVisible(page, value) {
  const selectors = [
    "input[placeholder*='Search' i]",
    "input[aria-label*='Search' i]",
    ".search input",
    ".pos-search input",
    "input[type='text']",
  ];
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      await locator.waitFor({ state: "visible", timeout: 3000 });
      await locator.fill(value);
      await page.keyboard.press("Enter").catch(() => null);
      return selector;
    } catch {
      // Continue through selector fallbacks.
    }
  }
  return "";
}

test("direct cashier POS UI search, cart, payment, and optional receipt print flow", async ({ page }) => {
  test.skip(
    process.env.TIJARA_RUN_DIRECT_POS_CLICKTHROUGH !== "1" ||
      (test.info().project.name !== "chromium-desktop" &&
        process.env.TIJARA_RUN_MOBILE_DIRECT_POS_UI_E2E !== "1") ||
      !process.env.ODOO_USERNAME ||
      !process.env.ODOO_PASSWORD ||
      !process.env.TIJARA_POS_CONFIG_ID ||
      !process.env.TIJARA_E2E_PRODUCT_NAME,
    "Set TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1, Odoo credentials, TIJARA_POS_CONFIG_ID, and TIJARA_E2E_PRODUCT_NAME for direct cashier POS UI E2E."
  );

  const productName = process.env.TIJARA_E2E_PRODUCT_NAME;
  await login(page);
  await openPosUi(page);

  await test.step("search and add seeded product to the cart", async () => {
    const searchSelector = await fillSearchIfVisible(page, productName);
    test.info().annotations.push({
      type: "selector",
      description: searchSelector ? `Product search selector: ${searchSelector}` : "Product search selector not needed/found.",
    });

    await expect(page.getByText(new RegExp(escapeRegExp(productName), "i")).first()).toBeVisible({
      timeout: visibleTimeout,
    });
    await page.getByText(new RegExp(escapeRegExp(productName), "i")).first().click();
    await expect(page.locator("body")).toContainText(/Total|Pay|Payment|Order|Cart|Qty|Quantity/i);
  });

  await test.step("navigate to payment screen", async () => {
    const selector = await clickFirstVisible(
      page,
      [
        "button:has-text('Payment')",
        "button:has-text('Pay')",
        ".pay-button",
        ".payment-button",
        "[data-name='payment']",
      ],
      "payment button"
    );
    test.info().annotations.push({ type: "selector", description: `Payment selector: ${selector}` });
    await expect(page.locator("body")).toContainText(/Payment|Validate|Cash|Card|Method|Amount Due/i, {
      timeout: visibleTimeout,
    });
  });

  await test.step("select payment method when available", async () => {
    const paymentMethodName = process.env.TIJARA_E2E_PAYMENT_METHOD_NAME || "";
    if (!paymentMethodName) {
      test.info().annotations.push({
        type: "note",
        description: "Payment-method click skipped because TIJARA_E2E_PAYMENT_METHOD_NAME is not set.",
      });
      return;
    }
    const method = page.getByText(new RegExp(escapeRegExp(paymentMethodName), "i")).first();
    await method.waitFor({ state: "visible", timeout: visibleTimeout });
    await method.click();
    await expect(page.locator("body")).toContainText(/Validate|Payment|Amount|Tendered|Change|Receipt/i);
  });

  await test.step("optionally validate order and exercise receipt print controls", async () => {
    if (process.env.TIJARA_RUN_DIRECT_POS_VALIDATE_E2E !== "1") {
      test.info().annotations.push({
        type: "note",
        description: "Receipt validation skipped; set TIJARA_RUN_DIRECT_POS_VALIDATE_E2E=1 on a staging POS register prepared for real browser sales.",
      });
      return;
    }
    await clickFirstVisible(
      page,
      [
        "button:has-text('Validate')",
        "button:has-text('Confirm')",
        "button:has-text('Pay')",
        ".validation-button",
      ],
      "validate button"
    );
    await expect(page.locator("body")).toContainText(/Receipt|Print|New Order|Thank|Invoice/i, {
      timeout: 30000,
    });
    const printSelector = await clickFirstVisible(
      page,
      [
        "button:has-text('Print Receipt')",
        "button:has-text('Print')",
        ".print",
        ".print-button",
      ],
      "receipt print button"
    );
    test.info().annotations.push({ type: "selector", description: `Receipt print selector: ${printSelector}` });
  });
});

test("direct refund form opens and accepts invoice barcode input", async ({ page }) => {
  test.skip(
    process.env.TIJARA_RUN_DIRECT_REFUND_FORM_E2E !== "1" ||
      !process.env.ODOO_USERNAME ||
      !process.env.ODOO_PASSWORD ||
      !process.env.TIJARA_REFUND_ACTION_URL ||
      !process.env.TIJARA_E2E_REFUND_BARCODE,
    "Set TIJARA_RUN_DIRECT_REFUND_FORM_E2E=1, Odoo credentials, TIJARA_REFUND_ACTION_URL, and TIJARA_E2E_REFUND_BARCODE for refund form click-through E2E."
  );

  await login(page);
  await page.goto(process.env.TIJARA_REFUND_ACTION_URL, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText(/Refund|Exchange|Invoice Barcode|Scan Invoice/i);

  const barcodeInput = page
    .locator(
      "input[name='scanned_invoice_barcode'], input[aria-label*='Barcode' i], input[placeholder*='Barcode' i], input[type='text']"
    )
    .first();
  await barcodeInput.waitFor({ state: "visible", timeout: visibleTimeout });
  await barcodeInput.fill(process.env.TIJARA_E2E_REFUND_BARCODE);
  await expect(barcodeInput).toHaveValue(process.env.TIJARA_E2E_REFUND_BARCODE);

  const scanButton = page.locator("button:has-text('Scan Invoice'), button:has-text('Scan')").first();
  if (await scanButton.isVisible().catch(() => false)) {
    await scanButton.click();
    await expect(page.locator("body")).toContainText(/Matched|Found|Refund|Exchange|Line|Product/i, {
      timeout: visibleTimeout,
    });
  }
});
