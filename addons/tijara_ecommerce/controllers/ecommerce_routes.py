import html
import json

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class TijaraEcommerceController(http.Controller):
    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            headers=[("Content-Type", "application/json; charset=utf-8")],
            status=status,
        )

    def _request_json_payload(self):
        body = request.httprequest.get_data(as_text=True) or "{}"
        return self._json_payload_from_body(body)

    def _json_payload_from_body(self, body):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise UserError("Invalid ecommerce payload.") from error
        if not isinstance(payload, dict):
            raise UserError("Ecommerce payload must be a JSON object.")
        return payload

    def _find_channel(self, channel_code):
        return request.env["tijara.ecommerce.channel"].sudo().search(
            [
                ("active", "=", True),
                "|",
                ("code", "=", channel_code),
                ("url_slug", "=", channel_code),
            ],
            limit=1,
        )

    def _storefront_html(self, channel):
        title = html.escape(channel.name or "Tijara Store")
        catalog_url = json.dumps("/tijara/ecommerce/%s/catalog" % channel.url_slug)
        checkout_url = json.dumps("/tijara/ecommerce/%s/checkout" % channel.url_slug)
        track_href = html.escape("/tijara/ecommerce/%s/track" % channel.url_slug, quote=True)
        orders_href = html.escape("/tijara/ecommerce/%s/orders" % channel.url_slug, quote=True)
        return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { color-scheme: light; font-family: Inter, Arial, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: #f6f8f7; color: #14221d; }
header { position: sticky; top: 0; z-index: 3; padding: 14px 18px; background: #ffffff; border-bottom: 1px solid #dbe4df; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h1 { margin: 0; font-size: 22px; line-height: 1.2; letter-spacing: 0; }
a { color: #0f5f4d; font-weight: 700; text-decoration: none; }
.button-link { min-height: 44px; border: 1px solid #adc1b7; background: #ffffff; color: #14221d; border-radius: 6px; padding: 10px 12px; display: inline-flex; align-items: center; }
button, input, select, textarea { font: inherit; }
button { min-height: 44px; border: 1px solid #adc1b7; background: #ffffff; color: #14221d; border-radius: 6px; padding: 8px 12px; cursor: pointer; }
button.active, button.primary { background: #16634f; color: #ffffff; border-color: #16634f; }
main { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; padding: 16px; }
.toolbar, .panel { background: #ffffff; border: 1px solid #dbe4df; border-radius: 8px; padding: 12px; }
.toolbar { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; margin-bottom: 12px; }
.toolbar input { min-height: 44px; width: 100%; border: 1px solid #adc1b7; border-radius: 6px; padding: 8px 10px; }
.segments { display: flex; gap: 8px; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
.product { min-height: 160px; text-align: left; display: flex; flex-direction: column; justify-content: space-between; gap: 10px; padding: 12px; border-color: #d2ddd7; }
.product strong { display: block; font-size: 16px; line-height: 1.25; }
.product small { display: block; color: #52645c; min-height: 20px; }
.price { font-weight: 700; color: #0f5f4d; }
aside { position: sticky; top: 74px; align-self: start; }
.cart-lines { display: grid; gap: 8px; margin: 10px 0; }
.cart-line { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; padding: 10px; background: #f8fbf9; border: 1px solid #dbe4df; border-radius: 6px; }
.qty { display: flex; gap: 4px; align-items: center; }
.qty button { min-width: 38px; min-height: 38px; padding: 4px; }
.field { display: grid; gap: 4px; margin-bottom: 8px; }
.field label { font-size: 12px; color: #52645c; }
.field input, .field select, .field textarea { width: 100%; min-height: 42px; border: 1px solid #adc1b7; border-radius: 6px; padding: 8px; }
.totals { border-top: 1px solid #dbe4df; border-bottom: 1px solid #dbe4df; padding: 10px 0; margin: 10px 0; display: grid; gap: 5px; }
.totals div { display: flex; justify-content: space-between; gap: 10px; }
.status { min-height: 22px; color: #0f5f4d; font-weight: 600; }
@media (max-width: 860px) {
  main { grid-template-columns: 1fr; padding: 10px; }
  aside { position: static; }
  .toolbar { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <a class="button-link" href="__TRACK_HREF__">Track Order</a>
    <a class="button-link" href="__ORDERS_HREF__">Order History</a>
    <div class="status" id="status"></div>
  </div>
</header>
<main>
  <section>
    <div class="toolbar">
      <input id="search" autocomplete="off" placeholder="Search by name, SKU, or barcode">
      <div class="segments" id="audiences"></div>
      <button type="button" id="refresh">Refresh</button>
    </div>
    <div class="grid" id="products"></div>
  </section>
  <aside class="panel">
    <h2 style="font-size:18px;margin:0 0 10px;">Cart</h2>
    <div class="segments" id="fulfillment"></div>
    <div class="field">
      <label for="payment">Payment</label>
      <select id="payment"></select>
    </div>
    <div class="cart-lines" id="cartLines"></div>
    <div class="totals" id="totals"></div>
    <div class="field"><label for="customerName">Customer</label><input id="customerName" autocomplete="name"></div>
    <div class="field"><label for="mobile">Mobile</label><input id="mobile" autocomplete="tel"></div>
    <div class="field"><label for="email">Email</label><input id="email" autocomplete="email"></div>
    <div class="field"><label for="address">Delivery Address</label><textarea id="address" rows="2"></textarea></div>
    <button type="button" class="primary" id="checkout" style="width:100%;">Place Order</button>
    <div class="status" id="orderResult" style="margin-top:10px;"></div>
  </aside>
</main>
<script>
const catalogEndpoint = __CATALOG_URL__;
const checkoutEndpoint = __CHECKOUT_URL__;
let catalog = null;
let audience = "b2c";
let fulfillmentMethod = "delivery";
const cart = new Map();
const money = value => new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR" }).format(Number(value || 0));
const el = id => document.getElementById(id);
function setStatus(text) { el("status").textContent = text || ""; }
function activeButton(container, value) {
  [...container.querySelectorAll("button")].forEach(button => button.classList.toggle("active", button.dataset.value === value));
}
function itemPrice(item) { return audience === "b2b" ? item.b2b_price : item.b2c_price; }
function renderSegments() {
  const audiences = [];
  if (catalog.channel.allow_b2c) audiences.push("b2c");
  if (catalog.channel.allow_b2b) audiences.push("b2b");
  if (!audiences.includes(audience)) audience = audiences[0] || "b2c";
  el("audiences").innerHTML = audiences.map(value => `<button type="button" data-value="${value}">${value.toUpperCase()}</button>`).join("");
  activeButton(el("audiences"), audience);
  const fulfilments = catalog.fulfillment.methods || [];
  if (!fulfilments.includes(fulfillmentMethod)) fulfillmentMethod = fulfilments[0] || "delivery";
  el("fulfillment").innerHTML = fulfilments.map(value => `<button type="button" data-value="${value}">${value.replace("_", " ")}</button>`).join("");
  activeButton(el("fulfillment"), fulfillmentMethod);
  const payments = catalog.payment.methods || [];
  el("payment").innerHTML = payments.map(value => `<option value="${value}">${value.replace("_", " ")}</option>`).join("");
}
function renderProducts() {
  const query = el("search").value.trim().toLowerCase();
  const products = (catalog.products || []).filter(item => !query || [item.name, item.name_urdu, item.default_code, item.barcode].join(" ").toLowerCase().includes(query));
  el("products").innerHTML = products.map(item => `<button type="button" class="product" data-id="${item.product_id}"><span><strong>${item.name}</strong><small>${item.name_urdu || item.default_code || item.barcode || ""}</small></span><span class="price">${money(itemPrice(item))}</span></button>`).join("");
}
function cartSubtotal() {
  let subtotal = 0;
  cart.forEach(entry => subtotal += itemPrice(entry.item) * entry.qty);
  return subtotal;
}
function chargeBreakdown() {
  const subtotal = cartSubtotal();
  const policy = catalog.charges || {};
  const service = policy.service_charge_enabled ? subtotal * Number(policy.service_charge_percent || 0) / 100 : 0;
  const delivery = policy.delivery_charge_enabled && ["delivery", "courier"].includes(fulfillmentMethod) ? Number(policy.delivery_charge_amount || 0) : 0;
  const payment = el("payment").value;
  let taxRate = 0;
  if (policy.payment_tax_enabled) {
    taxRate = ["cash", "cod"].includes(payment) ? Number(policy.cash_tax_percent || 0) : (["card", "jazzcash", "easypaisa", "stripe"].includes(payment) ? Number(policy.card_tax_percent || 0) : 0);
  }
  const paymentTax = (subtotal + service + delivery) * taxRate / 100;
  return { subtotal, service, delivery, paymentTax, total: subtotal + service + delivery + paymentTax };
}
function renderCart() {
  el("cartLines").innerHTML = [...cart.values()].map(entry => `<div class="cart-line"><span>${entry.item.name}<br><small>${money(itemPrice(entry.item))}</small></span><span class="qty"><button type="button" data-dec="${entry.item.product_id}">-</button><strong>${entry.qty}</strong><button type="button" data-inc="${entry.item.product_id}">+</button></span></div>`).join("") || "<small>No items selected.</small>";
  const totals = chargeBreakdown();
  el("totals").innerHTML = `<div><span>Subtotal</span><strong>${money(totals.subtotal)}</strong></div><div><span>Service</span><strong>${money(totals.service)}</strong></div><div><span>Delivery</span><strong>${money(totals.delivery)}</strong></div><div><span>Payment tax</span><strong>${money(totals.paymentTax)}</strong></div><div><span>Total before GST</span><strong>${money(totals.total)}</strong></div>`;
}
function addProduct(productId) {
  const item = (catalog.products || []).find(row => row.product_id === productId);
  if (!item) return;
  const entry = cart.get(productId) || { item, qty: 0 };
  entry.qty += 1;
  cart.set(productId, entry);
  renderCart();
}
function renderTrackingLink(result) {
  const container = el("orderResult");
  container.textContent = "";
  if (!result.tracking_url) return;
  const link = document.createElement("a");
  link.id = "trackingLink";
  link.href = result.tracking_url;
  link.textContent = "Track order";
  container.appendChild(link);
}
async function loadCatalog() {
  const response = await fetch(catalogEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ audience }) });
  catalog = await response.json();
  if (catalog.status !== "ok") throw new Error(catalog.message || "Catalog unavailable");
  renderSegments();
  renderProducts();
  renderCart();
}
async function submitCheckout() {
  if (!cart.size) return setStatus("Add items before checkout.");
  const payload = {
    audience,
    fulfillment_method: fulfillmentMethod,
    payment_method: el("payment").value,
    customer: { name: el("customerName").value, mobile: el("mobile").value, email: el("email").value, delivery_address: el("address").value, loyalty_opt_in: true },
    lines: [...cart.values()].map(entry => ({ product_id: entry.item.product_id, quantity: entry.qty }))
  };
  const response = await fetch(checkoutEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json();
  if (result.status !== "ok") return setStatus(result.message || "Order failed");
  cart.clear();
  renderCart();
  renderTrackingLink(result);
  setStatus(`Order ${result.order_name} ready. Pickup ${result.pickup_code || "-"}`);
}
document.addEventListener("click", event => {
  const product = event.target.closest(".product");
  if (product) addProduct(Number(product.dataset.id));
  if (event.target.closest("#audiences button")) { audience = event.target.dataset.value; loadCatalog().catch(error => setStatus(error.message)); }
  if (event.target.closest("#fulfillment button")) { fulfillmentMethod = event.target.dataset.value; activeButton(el("fulfillment"), fulfillmentMethod); renderCart(); }
  if (event.target.dataset.inc) { const entry = cart.get(Number(event.target.dataset.inc)); if (entry) { entry.qty += 1; renderCart(); } }
  if (event.target.dataset.dec) { const id = Number(event.target.dataset.dec); const entry = cart.get(id); if (entry) { entry.qty -= 1; if (entry.qty <= 0) cart.delete(id); renderCart(); } }
});
el("search").addEventListener("input", renderProducts);
el("payment").addEventListener("change", renderCart);
el("refresh").addEventListener("click", () => loadCatalog().catch(error => setStatus(error.message)));
el("checkout").addEventListener("click", () => submitCheckout().catch(error => setStatus(error.message)));
loadCatalog().catch(error => setStatus(error.message));
</script>
</body>
</html>""".replace("__TITLE__", title).replace("__TRACK_HREF__", track_href).replace("__ORDERS_HREF__", orders_href).replace("__CATALOG_URL__", catalog_url).replace("__CHECKOUT_URL__", checkout_url)

    def _tracking_html(self, channel, tracking_token=""):
        title = html.escape("%s Order Tracking" % (channel.name or "Tijara Store"))
        status_url = json.dumps("/tijara/ecommerce/%s/track/status" % channel.url_slug)
        token_json = json.dumps(tracking_token or "")
        return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { color-scheme: light; font-family: Inter, Arial, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: #f6f8f7; color: #14221d; }
header { padding: 16px 18px; background: #ffffff; border-bottom: 1px solid #dbe4df; display: flex; justify-content: space-between; gap: 12px; align-items: center; }
main { max-width: 960px; margin: 0 auto; padding: 16px; display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 16px; }
h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
h2 { margin: 0 0 10px; font-size: 18px; letter-spacing: 0; }
a { color: #0f5f4d; font-weight: 700; text-decoration: none; }
.panel, .card { background: #ffffff; border: 1px solid #dbe4df; border-radius: 8px; padding: 14px; }
.field { display: grid; gap: 4px; margin-bottom: 10px; }
.field label { font-size: 12px; color: #52645c; }
input { min-height: 44px; border: 1px solid #adc1b7; border-radius: 6px; padding: 8px 10px; font: inherit; }
button { width: 100%; min-height: 44px; border: 1px solid #16634f; background: #16634f; color: #fff; border-radius: 6px; font: inherit; cursor: pointer; }
.status { color: #0f5f4d; font-weight: 700; min-height: 22px; }
.grid { display: grid; gap: 10px; }
.row { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid #edf2ef; }
.row span:first-child { color: #52645c; }
.badge { display: inline-flex; align-items: center; min-height: 32px; padding: 4px 10px; border-radius: 6px; background: #e8f5ef; color: #0f5f4d; font-weight: 700; }
@media (max-width: 780px) { main { grid-template-columns: 1fr; padding: 10px; } }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <a href="/tijara/ecommerce/__SLUG__">Storefront</a>
</header>
<main>
  <section class="panel">
    <h2>Find order</h2>
    <div class="field"><label for="lookup">Pickup code, order reference, or tracking number</label><input id="lookup" autocomplete="off"></div>
    <div class="field"><label for="mobile">Mobile</label><input id="mobile" autocomplete="tel"></div>
    <div class="field"><label for="email">Email</label><input id="email" autocomplete="email"></div>
    <button type="button" id="check">Check Status</button>
    <div class="status" id="status" style="margin-top:10px;"></div>
  </section>
  <section class="card">
    <h2>Order status</h2>
    <div class="grid" id="result"><span class="status">Enter tracking details or use your private tracking link.</span></div>
  </section>
</main>
<script>
const statusEndpoint = __STATUS_URL__;
const initialToken = __TOKEN__;
const el = id => document.getElementById(id);
const money = (value, currency) => new Intl.NumberFormat("en-PK", { style: "currency", currency: currency || "PKR" }).format(Number(value || 0));
function setStatus(text) { el("status").textContent = text || ""; }
function row(label, value) { return `<div class="row"><span>${label}</span><strong>${value || "-"}</strong></div>`; }
function render(payload) {
  const order = payload.order || {};
  const queue = payload.queue || {};
  const delivery = payload.delivery || {};
  const providerLink = delivery.tracking_url ? `<a href="${delivery.tracking_url}" target="_blank" rel="noopener">Provider tracking</a>` : "";
  el("result").innerHTML = [
    `<span class="badge">${payload.next_step || "Order received"}</span>`,
    row("Order", order.name),
    row("Reference", order.reference),
    row("Total", money(order.amount_total, order.currency)),
    row("Fulfillment", order.fulfillment_method),
    row("Payment", `${order.payment_method || "-"} / ${order.payment_status || "-"}`),
    row("Pickup code", order.pickup_code),
    row("Queue", [queue.number, queue.state].filter(Boolean).join(" / ")),
    row("Delivery", [delivery.provider, delivery.status].filter(Boolean).join(" / ")),
    row("Tracking", delivery.tracking_number),
    providerLink ? `<div class="row"><span>Provider link</span><strong>${providerLink}</strong></div>` : "",
  ].join("");
}
async function checkStatus(payload = {}) {
  const body = initialToken && !payload.lookup ? { tracking_token: initialToken } : {
    pickup_code: payload.lookup || el("lookup").value,
    mobile: payload.mobile || el("mobile").value,
    email: payload.email || el("email").value,
  };
  const response = await fetch(statusEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const result = await response.json();
  if (result.status !== "ok") { setStatus(result.message || "Order not found."); return; }
  setStatus("Status loaded.");
  render(result);
}
el("check").addEventListener("click", () => checkStatus().catch(error => setStatus(error.message)));
if (initialToken) checkStatus().catch(error => setStatus(error.message));
</script>
</body>
</html>""".replace("__TITLE__", title).replace("__SLUG__", html.escape(channel.url_slug, quote=True)).replace("__STATUS_URL__", status_url).replace("__TOKEN__", token_json)

    def _order_history_html(self, channel):
        title = html.escape("%s Order History" % (channel.name or "Tijara Store"))
        orders_url = json.dumps("/tijara/ecommerce/%s/orders/list" % channel.url_slug)
        return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { color-scheme: light; font-family: Inter, Arial, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: #f6f8f7; color: #14221d; }
header { padding: 16px 18px; background: #ffffff; border-bottom: 1px solid #dbe4df; display: flex; justify-content: space-between; gap: 12px; align-items: center; }
main { max-width: 1080px; margin: 0 auto; padding: 16px; display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 16px; }
h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
h2 { margin: 0 0 10px; font-size: 18px; letter-spacing: 0; }
a { color: #0f5f4d; font-weight: 700; text-decoration: none; }
.panel, .order { background: #ffffff; border: 1px solid #dbe4df; border-radius: 8px; padding: 14px; }
.field { display: grid; gap: 4px; margin-bottom: 10px; }
.field label { font-size: 12px; color: #52645c; }
input { min-height: 44px; border: 1px solid #adc1b7; border-radius: 6px; padding: 8px 10px; font: inherit; }
button { width: 100%; min-height: 44px; border: 1px solid #16634f; background: #16634f; color: #fff; border-radius: 6px; font: inherit; cursor: pointer; }
.status { color: #0f5f4d; font-weight: 700; min-height: 22px; }
.orders { display: grid; gap: 10px; }
.order { display: grid; gap: 8px; }
.order-head { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.badge { display: inline-flex; align-items: center; min-height: 30px; padding: 4px 10px; border-radius: 6px; background: #e8f5ef; color: #0f5f4d; font-weight: 700; }
.meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; color: #52645c; font-size: 13px; }
.meta strong { display: block; color: #14221d; font-size: 14px; margin-top: 2px; }
@media (max-width: 780px) { main { grid-template-columns: 1fr; padding: 10px; } .meta { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <a href="/tijara/ecommerce/__SLUG__">Storefront</a>
</header>
<main>
  <section class="panel">
    <h2>Find orders</h2>
    <div class="field"><label for="mobile">Mobile</label><input id="mobile" autocomplete="tel"></div>
    <div class="field"><label for="email">Email</label><input id="email" autocomplete="email"></div>
    <button type="button" id="lookup">Show Orders</button>
    <div class="status" id="status" style="margin-top:10px;"></div>
  </section>
  <section>
    <h2>Recent order history</h2>
    <div class="orders" id="orders"><span class="status">Enter mobile or email to load recent orders.</span></div>
  </section>
</main>
<script>
const ordersEndpoint = __ORDERS_URL__;
const el = id => document.getElementById(id);
const money = (value, currency) => new Intl.NumberFormat("en-PK", { style: "currency", currency: currency || "PKR" }).format(Number(value || 0));
function setStatus(text) { el("status").textContent = text || ""; }
function meta(label, value) { return `<span>${label}<strong>${value || "-"}</strong></span>`; }
function render(result) {
  if (!result.orders || !result.orders.length) {
    el("orders").innerHTML = `<span class="status">No matching orders found.</span>`;
    return;
  }
  el("orders").innerHTML = result.orders.map(order => `
    <article class="order">
      <div class="order-head">
        <strong>${order.name}</strong>
        <span class="badge">${order.delivery_status || order.fulfillment_method || "order"}</span>
      </div>
      <div class="meta">
        ${meta("Total", money(order.amount_total, order.currency))}
        ${meta("Payment", [order.payment_method, order.payment_status].filter(Boolean).join(" / "))}
        ${meta("Fulfillment", order.fulfillment_method)}
        ${meta("Pickup", order.pickup_code)}
        ${meta("Queue", [order.queue_number, order.queue_state].filter(Boolean).join(" / "))}
        ${meta("Delivery", [order.delivery_provider, order.delivery_adapter_state].filter(Boolean).join(" / "))}
      </div>
      ${order.tracking_url ? `<a href="${order.tracking_url}">Open tracking</a>` : ""}
    </article>
  `).join("");
}
async function loadOrders() {
  const response = await fetch(ordersEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mobile: el("mobile").value, email: el("email").value, limit: 20 })
  });
  const result = await response.json();
  if (result.status !== "ok") { setStatus(result.message || "Order history unavailable."); return; }
  setStatus(`${result.count} order(s) loaded.`);
  render(result);
}
el("lookup").addEventListener("click", () => loadOrders().catch(error => setStatus(error.message)));
</script>
</body>
</html>""".replace("__TITLE__", title).replace("__SLUG__", html.escape(channel.url_slug, quote=True)).replace("__ORDERS_URL__", orders_url)

    @http.route(
        "/tijara/ecommerce/<string:channel_code>",
        type="http",
        methods=["GET"],
        auth="public",
        csrf=False,
    )
    def storefront(self, channel_code, **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return request.not_found()
        if not channel.company_id.tijara_has_saas_feature("ecommerce_store"):
            return self._json_response({"status": "forbidden"}, status=403)
        return request.make_response(
            self._storefront_html(channel),
            headers=[("Content-Type", "text/html; charset=utf-8")],
        )

    @http.route(
        [
            "/tijara/ecommerce/<string:channel_code>/track",
            "/tijara/ecommerce/<string:channel_code>/track/<string:tracking_token>",
        ],
        type="http",
        methods=["GET"],
        auth="public",
        csrf=False,
    )
    def tracking_page(self, channel_code, tracking_token="", **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return request.not_found()
        if not channel.company_id.tijara_has_saas_feature("ecommerce_store"):
            return self._json_response({"status": "forbidden"}, status=403)
        return request.make_response(
            self._tracking_html(channel, tracking_token=tracking_token),
            headers=[("Content-Type", "text/html; charset=utf-8")],
        )

    @http.route(
        "/tijara/ecommerce/<string:channel_code>/orders",
        type="http",
        methods=["GET"],
        auth="public",
        csrf=False,
    )
    def order_history_page(self, channel_code, **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return request.not_found()
        if not channel.company_id.tijara_has_saas_feature("ecommerce_store"):
            return self._json_response({"status": "forbidden"}, status=403)
        return request.make_response(
            self._order_history_html(channel),
            headers=[("Content-Type", "text/html; charset=utf-8")],
        )

    @http.route(
        "/tijara/ecommerce/<string:channel_code>/catalog",
        type="http",
        methods=["GET", "POST"],
        auth="public",
        csrf=False,
    )
    def catalog(self, channel_code, **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return self._json_response({"status": "not_found"}, status=404)
        try:
            payload = self._request_json_payload() if request.httprequest.method == "POST" else kwargs
            result = channel.tijara_catalog_payload(
                audience=payload.get("audience") or kwargs.get("audience"),
                search=payload.get("search") or kwargs.get("search") or "",
                limit=int(payload.get("limit") or kwargs.get("limit") or 80),
            )
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(result)

    @http.route(
        "/tijara/ecommerce/delivery/webhook/<string:provider_code>",
        type="http",
        methods=["POST"],
        auth="public",
        csrf=False,
    )
    def delivery_provider_webhook(self, provider_code, **kwargs):
        provider_model = request.env["tijara.ecommerce.delivery.provider"].sudo()
        normalized_code = provider_model._normalize_code(provider_code)
        provider = provider_model.search([("active", "=", True), ("code", "=", normalized_code)], limit=1)
        if not provider:
            return self._json_response({"status": "not_found", "message": "Delivery provider not found."}, status=404)
        raw_body = request.httprequest.get_data(as_text=True) or "{}"
        try:
            payload = self._json_payload_from_body(raw_body)
            result = provider.tijara_process_webhook(
                payload,
                headers={key: value for key, value in request.httprequest.headers.items()},
                raw_body=raw_body,
            )
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        http_status = 200 if result.get("status") == "ok" else 400
        if result.get("signature_status") in {"missing", "invalid"}:
            http_status = 403
        return self._json_response(result, status=http_status)

    @http.route(
        "/tijara/ecommerce/<string:channel_code>/checkout",
        type="http",
        methods=["POST"],
        auth="public",
        csrf=False,
    )
    def checkout(self, channel_code, **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return self._json_response({"status": "not_found"}, status=404)
        try:
            order = channel.tijara_create_order(self._request_json_payload())
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(
            {
                "status": "ok",
                "order_id": order.id,
                "order_name": order.name,
                "amount_total": order.amount_total,
                "amount_service_charge": order.tijara_amount_service_charge,
                "amount_delivery_charge": order.tijara_amount_delivery_charge,
                "amount_payment_tax": order.tijara_amount_payment_tax,
                "estimated_gst": order.tijara_estimated_gst,
                "payment_status": order.tijara_payment_status,
                "pickup_code": order.tijara_pickup_code or "",
                "queue_number": order.tijara_queue_ticket_id.queue_number or "",
                "tracking_token": order.tijara_tracking_token or "",
                "tracking_url": order.tijara_tracking_url or "",
                "delivery_status": order.tijara_delivery_status or "",
                "delivery_adapter_state": order.tijara_delivery_adapter_state or "",
                "delivery_provider": order.tijara_delivery_provider_id.name or "",
                "delivery_provider_reference": order.tijara_delivery_provider_reference or "",
                "delivery_tracking_number": order.tijara_delivery_tracking_number or "",
                "delivery_tracking_url": order.tijara_delivery_tracking_url or "",
                "delivery_label_format": order.tijara_delivery_label_format or "",
                "delivery_manifest_reference": order.tijara_delivery_manifest_reference or "",
            }
        )

    @http.route(
        "/tijara/ecommerce/<string:channel_code>/track/status",
        type="http",
        methods=["POST"],
        auth="public",
        csrf=False,
    )
    def tracking_status(self, channel_code, **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return self._json_response({"status": "not_found"}, status=404)
        try:
            result = channel.tijara_tracking_payload(self._request_json_payload())
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(result)

    @http.route(
        "/tijara/ecommerce/<string:channel_code>/orders/list",
        type="http",
        methods=["POST"],
        auth="public",
        csrf=False,
    )
    def order_history_list(self, channel_code, **kwargs):
        channel = self._find_channel(channel_code)
        if not channel:
            return self._json_response({"status": "not_found"}, status=404)
        try:
            result = channel.tijara_order_history_payload(self._request_json_payload())
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(result)
