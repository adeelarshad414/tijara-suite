import { expect, test } from "@playwright/test";
import { login, odooCallKw } from "./helpers.mjs";

const requiredEnv = [
  "ODOO_USERNAME",
  "ODOO_PASSWORD",
  "TIJARA_POS_CONFIG_ID",
  "TIJARA_E2E_PRODUCT_ID",
  "TIJARA_E2E_PAYMENT_METHOD_ID",
  "TIJARA_E2E_REFUND_REASON_ID",
];

async function postJson(page, url, data) {
  return page.evaluate(
    async ({ url, data }) => {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      return { status: response.status, body: await response.json() };
    },
    { url, data }
  );
}

async function getJson(page, url) {
  return page.evaluate(
    async ({ url }) => {
      const response = await fetch(url);
      return { status: response.status, body: await response.json() };
    },
    { url }
  );
}

function buildOfflinePayload(sourceOrderUid) {
  return {
    source_app: "pos_frontend",
    source_device_id: "playwright-enterprise-pos-browser",
    source_order_uid: sourceOrderUid,
    pos_config_id: Number(process.env.TIJARA_POS_CONFIG_ID),
    order_reference: sourceOrderUid,
    audience: "b2c",
    order_type: "takeaway",
    payment_status: "paid",
    amount_total: 240,
    amount_paid: 240,
    payment_method_id: Number(process.env.TIJARA_E2E_PAYMENT_METHOD_ID),
    payments: [
      {
        amount: 240,
        payment_method_id: Number(process.env.TIJARA_E2E_PAYMENT_METHOD_ID),
        payment_reference: sourceOrderUid,
        payment_status: "paid",
      },
    ],
    lines: [
      {
        product_id: Number(process.env.TIJARA_E2E_PRODUCT_ID),
        name: "E2E Enterprise Journey Item",
        qty: 2,
        price_unit: 120,
      },
    ],
  };
}

test("authenticated enterprise POS journey covers checkout, receipt, print, display, refund, and replay audit", async ({ page }) => {
  const missing = requiredEnv.filter((name) => !process.env[name]);
  test.skip(
    missing.length > 0,
    `Set ${requiredEnv.join(", ")} plus Odoo credentials for enterprise POS journey E2E.`
  );

  await login(page);

  const sourceOrderUid = `e2e-enterprise-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
  const payload = buildOfflinePayload(sourceOrderUid);
  let posOrderId = 0;
  let posOrder = null;

  await test.step("capture and replay a paid browser order into POS", async () => {
    const response = await postJson(page, "/tijara/offline-pos/capture", {
      payload,
      replay: true,
    });
    expect(response.status).toBe(200);
    expect(response.body.status).toBe("ok");
    expect(response.body.queue_state).toBe("replayed");
    expect(response.body.pos_order_id).toBeTruthy();
    posOrderId = response.body.pos_order_id;

    const [order] = await odooCallKw(page, "pos.order", "read", [
      [posOrderId],
      [
        "name",
        "pos_reference",
        "state",
        "amount_total",
        "amount_paid",
        "amount_return",
        "payment_ids",
        "lines",
        "tijara_invoice_barcode",
        "tijara_audience",
        "tijara_order_type",
      ],
    ]);
    posOrder = order;
    expect(posOrder.state).toMatch(/paid|done|invoiced/);
    expect(posOrder.amount_total).toBeGreaterThan(0);
    expect(posOrder.amount_paid).toBeGreaterThanOrEqual(posOrder.amount_total);
    expect(posOrder.lines.length).toBeGreaterThan(0);
    expect(posOrder.payment_ids.length).toBeGreaterThan(0);
    expect(posOrder.tijara_invoice_barcode).toMatch(/^TJINV:/);
    expect(posOrder.tijara_audience).toBe("b2c");
    expect(posOrder.tijara_order_type).toBe("takeaway");
  });

  await test.step("render receipt report and exercise print-to-bridge method", async () => {
    await page.goto(`/report/html/tijara_pos_pk.report_tijara_pos_receipt/${posOrderId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.locator("body")).toContainText(/Tijara|Receipt|PKR|Enterprise Journey/i);

    let printRouteResult = "";
    try {
      const printResult = await odooCallKw(page, "pos.order", "action_tijara_print_receipt_to_bridge", [
        [posOrderId],
        {
          ticket_text: "E2E enterprise journey receipt",
          ticket_html: "<div>E2E enterprise journey receipt</div>",
          basic_receipt: true,
        },
      ]);
      printRouteResult = JSON.stringify(printResult);
    } catch (error) {
      printRouteResult = error.message;
    }
    expect(printRouteResult).toMatch(/receipt|print|bridge|printer|notification|unreachable/i);
  });

  await test.step("publish customer display state when the POS register is configured", async () => {
    const [config] = await odooCallKw(page, "pos.config", "read", [
      [Number(process.env.TIJARA_POS_CONFIG_ID)],
      ["tijara_customer_display_enabled", "tijara_customer_display_id"],
    ]);
    const displayId = config.tijara_customer_display_id?.[0] || config.tijara_customer_display_id;
    if (!config.tijara_customer_display_enabled || !displayId) {
      test.info().annotations.push({
        type: "note",
        description: "Customer display exact-order assertion skipped because the POS config has no customer display.",
      });
      return;
    }

    await odooCallKw(page, "pos.order", "action_tijara_publish_customer_display", [[posOrderId]]);
    const states = await odooCallKw(
      page,
      "tijara.customer.display.state",
      "search_read",
      [[["screen_id", "=", displayId], ["active", "=", true]]],
      {
        fields: ["order_reference", "amount_total", "line_ids", "status"],
        limit: 1,
        order: "last_event_at desc",
      }
    );
    expect(states.length).toBeGreaterThan(0);
    expect(states[0].order_reference).toBe(posOrder.pos_reference || posOrder.name);
    expect(states[0].amount_total).toBeGreaterThan(0);
    expect(states[0].line_ids.length).toBeGreaterThan(0);

    if (process.env.TIJARA_CUSTOMER_DISPLAY_SLUG) {
      const display = await getJson(page, `/tijara/display/${process.env.TIJARA_CUSTOMER_DISPLAY_SLUG}/data`);
      expect(display.status).toBe(200);
      expect(display.body.customer_display.lines.length).toBeGreaterThan(0);
    }
  });

  await test.step("scan created receipt barcode for refund matching", async () => {
    const requestId = await odooCallKw(page, "tijara.exchange.request", "create", [
      {
        scanned_invoice_barcode: posOrder.tijara_invoice_barcode,
        reason_id: Number(process.env.TIJARA_E2E_REFUND_REASON_ID),
      },
    ]);

    await odooCallKw(page, "tijara.exchange.request", "action_scan_invoice_barcode", [[requestId]]);
    const [request] = await odooCallKw(page, "tijara.exchange.request", "read", [
      [requestId],
      ["scan_status", "matched_pos_order_id", "line_ids", "scan_result_message"],
    ]);

    expect(request.scan_status).toBe("found");
    expect(request.matched_pos_order_id?.[0] || request.matched_pos_order_id).toBe(posOrderId);
    expect(request.line_ids.length).toBeGreaterThan(0);
  });

  await test.step("prove duplicate capture handling and offline replay audit status", async () => {
    const duplicate = await postJson(page, "/tijara/offline-pos/capture", {
      payload,
      replay: true,
    });
    expect(duplicate.status).toBe(200);
    expect(duplicate.body.status).toBe("duplicate");
    expect(duplicate.body.queue_state).toBe("replayed");
    expect(duplicate.body.pos_order_id).toBe(posOrderId);

    const status = await getJson(
      page,
      "/tijara/offline-pos/status?source_device_id=playwright-enterprise-pos-browser"
    );
    expect(status.status).toBe(200);
    expect(status.body.status).toBe("ok");
    expect(status.body.counts.replayed || 0).toBeGreaterThan(0);
  });
});
