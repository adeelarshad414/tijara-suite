import { expect, test } from "@playwright/test";
import { login, odooCallKw } from "./helpers.mjs";

const slug = process.env.TIJARA_ECOMMERCE_SLUG;

function requireSlug() {
  test.skip(!slug, "Set TIJARA_ECOMMERCE_SLUG to run ecommerce storefront E2E.");
  return slug;
}

function databaseHeaders() {
  return process.env.ODOO_DATABASE ? { "X-Odoo-Database": process.env.ODOO_DATABASE } : {};
}

async function loadCatalog(request, audience = "b2c") {
  const activeSlug = requireSlug();
  const response = await request.post(`/tijara/ecommerce/${activeSlug}/catalog`, {
    headers: databaseHeaders(),
    data: { audience, limit: 30 },
  });
  const payload = await response.json();
  expect(response.status(), payload.message || JSON.stringify(payload)).toBe(200);
  expect(payload.status).toBe("ok");
  return payload;
}

function firstOrderableProduct(catalog) {
  const product = (catalog.products || []).find(
    (candidate) => candidate.product_id && candidate.b2c_price > 0 && candidate.b2b_price > 0,
  );
  expect(product).toBeTruthy();
  return product;
}

async function checkout(request, payload) {
  const activeSlug = requireSlug();
  const response = await request.post(`/tijara/ecommerce/${activeSlug}/checkout`, {
    headers: databaseHeaders(),
    data: payload,
  });
  const result = await response.json();
  expect(response.status(), result.message || JSON.stringify(result)).toBe(200);
  expect(result.status).toBe("ok");
  return result;
}

async function trackOrder(request, payload) {
  const activeSlug = requireSlug();
  const response = await request.post(`/tijara/ecommerce/${activeSlug}/track/status`, {
    headers: databaseHeaders(),
    data: payload,
  });
  const result = await response.json();
  expect(response.status(), result.message || JSON.stringify(result)).toBe(200);
  expect(result.status).toBe("ok");
  return result;
}

test("ecommerce catalog exposes PKR, Urdu names, B2C, B2B, stock, promotions, and fulfillment", async ({ request }) => {
  const b2cCatalog = await loadCatalog(request, "b2c");
  expect(b2cCatalog.channel.currency).toBe("PKR");
  expect(b2cCatalog.channel.allow_b2c).toBe(true);
  expect(b2cCatalog.channel.allow_b2b).toBe(true);
  expect(b2cCatalog.fulfillment.methods).toEqual(expect.arrayContaining(["pickup", "delivery"]));
  expect(b2cCatalog.payment.methods.length).toBeGreaterThan(0);
  expect(b2cCatalog.promotions.length).toBeGreaterThan(0);

  const b2cProduct = firstOrderableProduct(b2cCatalog);
  expect(b2cProduct.name_urdu).toBeTruthy();
  expect(b2cProduct.default_code || b2cProduct.barcode).toBeTruthy();
  expect(typeof b2cProduct.low_stock).toBe("boolean");
  expect(b2cProduct.price).toBe(b2cProduct.b2c_price);

  const b2bCatalog = await loadCatalog(request, "b2b");
  const b2bProduct = b2bCatalog.products.find((candidate) => candidate.product_id === b2cProduct.product_id);
  expect(b2bProduct).toBeTruthy();
  expect(b2bProduct.price).toBe(b2bProduct.b2b_price);
  expect(b2bProduct.b2b_price).toBeGreaterThan(0);
});

test("ecommerce storefront renders and completes a pickup checkout from the browser", async ({ page }) => {
  const activeSlug = requireSlug();
  await page.setExtraHTTPHeaders(databaseHeaders());
  await page.goto(`/tijara/ecommerce/${activeSlug}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("h1")).toContainText(/Tijara/i);
  await expect(page.locator(".product").first()).toBeVisible();

  await page.locator("button[data-value='b2b']").click();
  await page.locator("button[data-value='pickup']").click();
  await page.locator(".product").first().click();
  await expect(page.locator("#cartLines .cart-line")).toHaveCount(1);
  await page.locator("#customerName").fill("E2E Ecommerce Pickup");
  await page.locator("#mobile").fill("03000000021");
  await page.locator("#email").fill("ecommerce.pickup@example.test");
  await page.locator("#checkout").click();
  await expect(page.locator("#status")).toContainText(/Order .* ready/i);
  await expect(page.locator("#trackingLink")).toBeVisible();
});

test("ecommerce API delivery checkout applies charges and creates a queue handoff", async ({ request }) => {
  const catalog = await loadCatalog(request, "b2c");
  const product = firstOrderableProduct(catalog);
  test.skip(!catalog.fulfillment.methods.includes("delivery"), "Ecommerce channel does not allow delivery.");

  const result = await checkout(request, {
    audience: "b2c",
    fulfillment_method: "delivery",
    payment_method: catalog.payment.methods.includes("cod") ? "cod" : catalog.payment.methods[0],
    reference: `E2E-ECOM-DELIVERY-${Date.now()}`,
    customer: {
      name: "E2E Ecommerce Delivery",
      mobile: "03000000022",
      email: "ecommerce.delivery@example.test",
      delivery_address: "E2E delivery address, Karachi",
      loyalty_opt_in: true,
    },
    lines: [{ product_id: product.product_id, quantity: 2 }],
  });

  expect(result.order_id).toBeGreaterThan(0);
  expect(result.amount_total).toBeGreaterThan(0);
  if (catalog.charges.delivery_charge_enabled) {
    expect(result.amount_delivery_charge).toBeGreaterThan(0);
  }
  expect(result.pickup_code).toBeTruthy();
  expect(result.queue_number).toBeTruthy();
  expect(result.tracking_token).toBeTruthy();
  expect(result.tracking_url).toContain("/track/");
  expect(result.delivery_status).toBeTruthy();
  expect(result.delivery_adapter_state).toBe("created");
  expect(result.delivery_provider_reference).toBeTruthy();
  const tracking = await trackOrder(request, { tracking_token: result.tracking_token });
  expect(tracking.order.pickup_code).toBe(result.pickup_code);
  expect(tracking.queue.number).toBe(result.queue_number);
  expect(tracking.delivery.required).toBe(true);
  expect(tracking.delivery.adapter_state).toBe("created");
  expect(tracking.delivery.provider_reference).toBe(result.delivery_provider_reference);
  expect(tracking.delivery.event_count).toBeGreaterThan(0);
  expect(tracking.delivery.tracking_number || result.delivery_tracking_number).toBeTruthy();
});

test("ecommerce customer can track an order with pickup code and mobile", async ({ request }) => {
  const catalog = await loadCatalog(request, "b2c");
  const product = firstOrderableProduct(catalog);
  const mobile = "03000000024";
  const result = await checkout(request, {
    audience: "b2c",
    fulfillment_method: catalog.fulfillment.methods.includes("delivery") ? "delivery" : catalog.fulfillment.methods[0],
    payment_method: catalog.payment.methods.includes("cod") ? "cod" : catalog.payment.methods[0],
    reference: `E2E-ECOM-TRACK-${Date.now()}`,
    customer: {
      name: "E2E Ecommerce Tracking",
      mobile,
      email: "ecommerce.tracking@example.test",
      delivery_address: "Tracking delivery address, Lahore",
      loyalty_opt_in: true,
    },
    lines: [{ product_id: product.product_id, quantity: 1 }],
  });

  const tracking = await trackOrder(request, {
    pickup_code: result.pickup_code,
    mobile,
  });
  expect(tracking.order.name).toBe(result.order_name);
  expect(tracking.order.customer_tracking_url).toContain("/track/");
  expect(["pending", "assigned", "not_required"]).toContain(tracking.delivery.status);
  expect(tracking.next_step).toBeTruthy();
});

test("authenticated ecommerce manager can review the created ecommerce sale order and queue ticket", async ({
  page,
  request,
}) => {
  requireSlug();
  test.skip(
    !process.env.ODOO_USERNAME || !process.env.ODOO_PASSWORD || !process.env.ODOO_DATABASE,
    "Set ODOO_USERNAME, ODOO_PASSWORD, and ODOO_DATABASE to run authenticated ecommerce review E2E.",
  );

  const catalog = await loadCatalog(request, "b2b");
  test.skip(!catalog.fulfillment.methods.includes("delivery"), "Ecommerce channel does not allow delivery.");
  const product = firstOrderableProduct(catalog);
  const reference = `E2E-ECOM-REVIEW-${Date.now()}`;
  const result = await checkout(request, {
    audience: "b2b",
    fulfillment_method: "delivery",
    payment_method: catalog.payment.methods[0],
    reference,
    customer: {
      name: "E2E Ecommerce B2B Review",
      mobile: "03000000023",
      email: "ecommerce.b2b@example.test",
      loyalty_opt_in: true,
    },
    lines: [{ product_id: product.product_id, quantity: 1 }],
  });

  await login(page);
  const orders = await odooCallKw(
    page,
    "sale.order",
    "search_read",
    [[["id", "=", result.order_id]]],
    {
      fields: [
        "id",
        "name",
        "client_order_ref",
        "tijara_ecommerce_audience",
        "tijara_fulfillment_method",
        "tijara_payment_method",
        "tijara_pickup_code",
        "tijara_queue_ticket_id",
        "tijara_delivery_provider_id",
        "tijara_delivery_tracking_number",
        "tijara_delivery_adapter_state",
        "tijara_delivery_provider_reference",
      ],
      limit: 1,
    },
  );
  expect(orders).toHaveLength(1);
  expect(orders[0].client_order_ref).toBe(reference);
  expect(orders[0].tijara_ecommerce_audience).toBe("b2b");
  expect(orders[0].tijara_pickup_code).toBeTruthy();
  expect(orders[0].tijara_queue_ticket_id).toBeTruthy();
  expect(orders[0].tijara_delivery_adapter_state).toBe("created");
  expect(orders[0].tijara_delivery_provider_reference).toBeTruthy();
  expect(orders[0].tijara_delivery_provider_id).toBeTruthy();

  await odooCallKw(page, "sale.order", "action_tijara_generate_delivery_label", [[result.order_id]]);
  await odooCallKw(page, "sale.order", "action_tijara_create_delivery_manifest", [[result.order_id]]);

  const updatedOrders = await odooCallKw(
    page,
    "sale.order",
    "search_read",
    [[["id", "=", result.order_id]]],
    {
      fields: [
        "id",
        "tijara_delivery_provider_id",
        "tijara_delivery_tracking_number",
        "tijara_delivery_adapter_state",
        "tijara_delivery_label_format",
        "tijara_delivery_manifest_reference",
      ],
      limit: 1,
    },
  );
  expect(updatedOrders).toHaveLength(1);
  expect(updatedOrders[0].tijara_delivery_adapter_state).toBe("manifested");
  expect(updatedOrders[0].tijara_delivery_label_format).toBeTruthy();
  expect(updatedOrders[0].tijara_delivery_manifest_reference).toBeTruthy();

  const providerId = updatedOrders[0].tijara_delivery_provider_id[0];
  const providers = await odooCallKw(
    page,
    "tijara.ecommerce.delivery.provider",
    "search_read",
    [[["id", "=", providerId]]],
    { fields: ["id", "code"], limit: 1 },
  );
  expect(providers).toHaveLength(1);

  const webhookResponse = await request.post(`/tijara/ecommerce/delivery/webhook/${providers[0].code}`, {
    headers: {
      ...databaseHeaders(),
      "X-Tijara-Delivery-Signature": "tijara-dry-run",
    },
    data: {
      tracking_number: updatedOrders[0].tijara_delivery_tracking_number,
      status: "delivered",
    },
  });
  const webhook = await webhookResponse.json();
  expect(webhookResponse.status(), JSON.stringify(webhook)).toBe(200);
  expect(webhook.status).toBe("ok");
  expect(webhook.signature_status).toBe("valid");
  const postWebhookTracking = await trackOrder(request, { tracking_token: result.tracking_token });
  expect(postWebhookTracking.delivery.status).toBe("delivered");
  expect(postWebhookTracking.delivery.adapter_state).toBe("webhook_synced");

  const tickets = await odooCallKw(
    page,
    "tijara.queue.ticket",
    "search_read",
    [[["sale_order_id", "=", result.order_id]]],
    { fields: ["id", "queue_number", "source", "state"], limit: 1 },
  );
  expect(tickets).toHaveLength(1);
  expect(tickets[0].source).toBe("ecommerce");
  expect(tickets[0].queue_number).toBeTruthy();
});
