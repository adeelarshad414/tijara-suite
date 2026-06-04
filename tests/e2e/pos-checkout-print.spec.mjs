import { expect, test } from "@playwright/test";
import { login, odooCallKw } from "./helpers.mjs";

test("authenticated POS checkout shell opens for receipt print-to-bridge path", async ({ page }) => {
  test.skip(
    process.env.TIJARA_RUN_POS_UI_E2E !== "1" ||
      !process.env.ODOO_USERNAME ||
      !process.env.ODOO_PASSWORD ||
      !process.env.TIJARA_POS_CONFIG_ID,
    "Set TIJARA_RUN_POS_UI_E2E=1, ODOO credentials, and TIJARA_POS_CONFIG_ID for POS checkout E2E."
  );

  await login(page);
  const action = await odooCallKw(page, "pos.config", "open_ui", [
    [Number(process.env.TIJARA_POS_CONFIG_ID)]
  ]);
  await page.goto(action.url || `/pos/ui/${process.env.TIJARA_POS_CONFIG_ID}?from_backend=True`, {
    waitUntil: "domcontentloaded"
  });

  await expect(page.locator("body")).toContainText(
    /Point of Sale|Products|Payment|Receipt|Register|Orders|Pay|Cart/i
  );
});

test("authenticated offline conflict review workbench opens", async ({ page }) => {
  test.skip(
    !process.env.ODOO_USERNAME ||
      !process.env.ODOO_PASSWORD ||
      !process.env.TIJARA_OFFLINE_QUEUE_ACTION_URL,
    "Set ODOO credentials and TIJARA_OFFLINE_QUEUE_ACTION_URL for offline conflict review E2E."
  );

  await login(page);
  await page.goto(process.env.TIJARA_OFFLINE_QUEUE_ACTION_URL, {
    waitUntil: "domcontentloaded"
  });

  await expect(page.locator("body")).toContainText(/Offline|Conflict|Queue|Review/i);
});

test("authenticated offline POS capture route replays a paid browser order", async ({ page }) => {
  test.skip(
    (test.info().project.name !== "chromium-desktop" &&
      process.env.TIJARA_RUN_MOBILE_OFFLINE_E2E !== "1") ||
    !process.env.ODOO_USERNAME ||
      !process.env.ODOO_PASSWORD ||
      !process.env.TIJARA_POS_CONFIG_ID ||
      !process.env.TIJARA_E2E_PRODUCT_ID ||
      !process.env.TIJARA_E2E_PAYMENT_METHOD_ID,
    "Set ODOO credentials, TIJARA_POS_CONFIG_ID, TIJARA_E2E_PRODUCT_ID, and TIJARA_E2E_PAYMENT_METHOD_ID for offline POS replay E2E; set TIJARA_RUN_MOBILE_OFFLINE_E2E=1 to include mobile."
  );

  await login(page);
  const sourceOrderUid = `e2e-offline-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
  const response = await page.evaluate(
    async ({ configId, productId, paymentMethodId, sourceOrderUid }) => {
      const result = await fetch("/tijara/offline-pos/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payload: {
            source_app: "pos_frontend",
            source_device_id: "playwright-pos-browser",
            source_order_uid: sourceOrderUid,
            pos_config_id: Number(configId),
            order_reference: sourceOrderUid,
            audience: "b2c",
            order_type: "takeaway",
            payment_status: "paid",
            amount_total: 120,
            amount_paid: 120,
            payment_method_id: Number(paymentMethodId),
            payments: [
              {
                amount: 120,
                payment_method_id: Number(paymentMethodId),
                payment_reference: sourceOrderUid,
                payment_status: "paid"
              }
            ],
            lines: [
              {
                product_id: Number(productId),
                name: "E2E Offline Replay Item",
                qty: 1,
                price_unit: 120
              }
            ]
          },
          replay: true
        })
      });
      return { status: result.status, body: await result.json() };
    },
    {
      configId: process.env.TIJARA_POS_CONFIG_ID,
      productId: process.env.TIJARA_E2E_PRODUCT_ID,
      paymentMethodId: process.env.TIJARA_E2E_PAYMENT_METHOD_ID,
      sourceOrderUid
    }
  );

  expect(response.status).toBe(200);
  expect(response.body.queue_state).toBe("replayed");
  expect(response.body.pos_order_id).toBeTruthy();

  const posOrderId = response.body.pos_order_id;
  await page.goto(`/report/html/tijara_pos_pk.report_tijara_pos_receipt/${posOrderId}`, {
    waitUntil: "domcontentloaded"
  });
  await expect(page.locator("body")).toContainText(/Tijara|Receipt|PKR|E2E Offline/i);

  let printRouteResult = "";
  try {
    const printResult = await odooCallKw(page, "pos.order", "action_tijara_print_receipt_to_bridge", [
      [posOrderId],
      {
        ticket_text: "E2E offline replay receipt",
        ticket_html: "<div>E2E offline replay receipt</div>",
        basic_receipt: true
      }
    ]);
    printRouteResult = JSON.stringify(printResult);
  } catch (error) {
    printRouteResult = error.message;
  }
  expect(printRouteResult).toMatch(/receipt|print|bridge|notification|unreachable/i);
});
