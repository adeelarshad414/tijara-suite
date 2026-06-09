import { expect, test } from "@playwright/test";
import { selectDatabase, selectPageDatabase } from "./helpers.mjs";

test("public display route returns menu/deal data", async ({ request }) => {
  const slug = process.env.TIJARA_DISPLAY_SLUG;
  test.skip(!slug, "Set TIJARA_DISPLAY_SLUG to run display route E2E.");

  await selectDatabase(request);
  const response = await request.get(`/tijara/display/${slug}/data`);
  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload.screen.name).toBeTruthy();
  expect(Array.isArray(payload.content)).toBe(true);
});

test("public kiosk route renders the touch shell", async ({ page }) => {
  const slug = process.env.TIJARA_KIOSK_SLUG || process.env.TIJARA_DISPLAY_SLUG;
  test.skip(!slug, "Set TIJARA_KIOSK_SLUG or TIJARA_DISPLAY_SLUG to run kiosk E2E.");

  await selectPageDatabase(page);
  await page.goto(`/tijara/kiosk/${slug}`);
  await expect(page.locator("main.kiosk")).toBeVisible();
  await expect(page.locator("[data-role='kiosk-products']")).toBeVisible();
});

test("public kiosk checkout submits a seeded order", async ({ request }) => {
  const slug = process.env.TIJARA_KIOSK_SLUG;
  test.skip(!slug, "Set TIJARA_KIOSK_SLUG to run kiosk checkout E2E.");

  await selectDatabase(request);
  const dataResponse = await request.get(`/tijara/kiosk/${slug}/data`);
  expect(dataResponse.status()).toBe(200);
  const data = await dataResponse.json();
  const item = data.kiosk.items.find((candidate) => candidate.id || candidate.product_id);
  expect(item).toBeTruthy();

  const checkoutResponse = await request.post(`/tijara/kiosk/${slug}/checkout`, {
    data: {
      order_type: data.kiosk.profile.default_order_type,
      audience: "b2c",
      payment_method: data.kiosk.profile.allowed_payment_methods[0],
      customer_name: "E2E Browser",
      customer_mobile: "03000000000",
      lines: [{ content_id: item.id || false, product_id: item.product_id || false, qty: 1 }],
    },
  });
  expect(checkoutResponse.status()).toBe(200);
  const checkout = await checkoutResponse.json();
  expect(checkout.status).toBe("ok");
  expect(checkout.amount_total).toBeGreaterThan(0);
});

test("public kiosk delivery checkout applies delivery and food-service charge policy", async ({ request }) => {
  const slug = process.env.TIJARA_KIOSK_SLUG;
  test.skip(!slug, "Set TIJARA_KIOSK_SLUG to run kiosk delivery charge E2E.");

  await selectDatabase(request);
  const dataResponse = await request.get(`/tijara/kiosk/${slug}/data`);
  expect(dataResponse.status()).toBe(200);
  const data = await dataResponse.json();
  const item = data.kiosk.items.find((candidate) => candidate.id || candidate.product_id);
  expect(item).toBeTruthy();

  const charges = data.kiosk.profile.charges || {};
  test.skip(
    !(data.kiosk.profile.allowed_order_types || []).includes("delivery"),
    "Seeded kiosk profile does not allow delivery orders."
  );
  const allowedMethods = data.kiosk.profile.allowed_payment_methods || [];
  const paymentMethod = allowedMethods.includes("card") ? "card" : allowedMethods[0] || "cash";
  const checkoutResponse = await request.post(`/tijara/kiosk/${slug}/checkout`, {
    data: {
      order_type: "delivery",
      audience: "b2c",
      payment_method: paymentMethod,
      customer_name: "E2E Delivery Charge",
      customer_mobile: "03000000001",
      lines: [{ content_id: item.id || false, product_id: item.product_id || false, qty: 2 }],
    },
  });
  const checkout = await checkoutResponse.json();
  expect(checkoutResponse.status(), checkout.message || JSON.stringify(checkout)).toBe(200);
  expect(checkout.status).toBe("ok");
  expect(checkout.amount_untaxed).toBeGreaterThan(0);
  expect(checkout.amount_total).toBeGreaterThan(checkout.amount_untaxed);

  if (charges.delivery_charge_enabled) {
    expect(checkout.amount_delivery_charge).toBeGreaterThan(0);
  }
  if (charges.service_charge_enabled) {
    expect(checkout.amount_service_charge).toBeGreaterThan(0);
  }
  if (charges.food_payment_tax_enabled && ["cash", "card"].includes(paymentMethod)) {
    expect(checkout.amount_payment_tax).toBeGreaterThan(0);
  }
});

test("public customer display route returns live order state", async ({ request }) => {
  const slug = process.env.TIJARA_CUSTOMER_DISPLAY_SLUG;
  test.skip(!slug, "Set TIJARA_CUSTOMER_DISPLAY_SLUG to run customer display E2E.");

  await selectDatabase(request);
  const response = await request.get(`/tijara/display/${slug}/data`);
  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload.customer_display.order_reference).toBeTruthy();
  expect(payload.customer_display.lines.length).toBeGreaterThan(0);
});
