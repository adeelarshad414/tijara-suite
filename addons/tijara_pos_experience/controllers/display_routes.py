import html
import json

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


FEATURE_BY_DISPLAY_TYPE = {
    "kiosk": "pos_experience",
    "customer_display": "customer_display",
    "menu_board": "promotion_display",
    "deals_board": "promotion_display",
    "queue_display": "queue_system",
}


class TijaraDisplayController(http.Controller):
    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            headers=[("Content-Type", "application/json; charset=utf-8")],
            status=status,
        )

    def _request_json_payload(self):
        body = request.httprequest.get_data(as_text=True) or "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise UserError("Invalid checkout payload.") from error
        if not isinstance(payload, dict):
            raise UserError("Checkout payload must be a JSON object.")
        return payload

    def _find_screen(self, slug):
        return request.env["tijara.display.screen"].sudo().search(
            [
                ("active", "=", True),
                "|",
                ("url_slug", "=", slug),
                ("code", "=", slug),
            ],
            limit=1,
        )

    def _find_kiosk_profile(self, screen):
        profile = request.env["tijara.kiosk.profile"].sudo().search(
            [("active", "=", True), ("screen_id", "=", screen.id)],
            limit=1,
        )
        if profile:
            return profile
        return request.env["tijara.kiosk.profile"].sudo().search(
            [
                ("active", "=", True),
                ("company_id", "=", screen.company_id.id),
                ("screen_id", "=", False),
            ],
            limit=1,
        )

    def _screen_allowed(self, screen):
        feature_code = FEATURE_BY_DISPLAY_TYPE.get(screen.display_type)
        if not feature_code:
            return True
        return screen.company_id.tijara_has_saas_feature(feature_code)

    def _content_domain(self, screen):
        now = fields.Datetime.now()
        return [
            ("active", "=", True),
            ("company_id", "=", screen.company_id.id),
            ("screen_ids", "in", screen.id),
            "|",
            ("start_at", "=", False),
            ("start_at", "<=", now),
            "|",
            ("end_at", "=", False),
            ("end_at", ">=", now),
        ]

    def _product_prices(self, product):
        if not product:
            return 0.0, 0.0
        b2c_price = getattr(product, "tijara_b2c_price", 0.0) or product.lst_price
        b2b_price = getattr(product, "tijara_b2b_price", 0.0) or b2c_price
        return b2c_price, b2b_price

    def _content_payload(self, screen):
        contents = request.env["tijara.display.content"].sudo().search(
            self._content_domain(screen),
            order="sequence, name",
            limit=48 if screen.display_type == "kiosk" else 24,
        )
        result = []
        for content in contents:
            product = content.product_id
            product_b2c_price, product_b2b_price = self._product_prices(product)
            product_tmpl = product.product_tmpl_id if product else False
            result.append(
                {
                    "id": content.id,
                    "product_id": product.id if product else False,
                    "name": content.name,
                    "type": content.content_type,
                    "title_english": content.title_english or content.name,
                    "title_urdu": content.title_urdu
                    or (getattr(product_tmpl, "tijara_urdu_name", "") if product_tmpl else ""),
                    "subtitle_english": content.subtitle_english or "",
                    "subtitle_urdu": content.subtitle_urdu or "",
                    "product": product.display_name if product else "",
                    "barcode": product.barcode if product else "",
                    "default_code": product.default_code if product else "",
                    "b2c_price": content.b2c_price or product_b2c_price,
                    "b2b_price": content.b2b_price or product_b2b_price,
                    "promotion": content.promotion_id.display_name if content.promotion_id else "",
                }
            )
        return result

    def _queue_payload(self, screen):
        tickets = request.env["tijara.queue.ticket"].sudo().search(
            [
                ("company_id", "=", screen.company_id.id),
                ("state", "in", ("waiting", "preparing", "ready", "called")),
            ],
            order="create_date desc",
            limit=20,
        )
        return [
            {
                "number": ticket.queue_number or ticket.name,
                "state": ticket.state,
                "order_type": ticket.order_type,
                "pickup_code": ticket.pickup_code or "",
                "customer": ticket.customer_id.display_name or "",
            }
            for ticket in tickets
        ]

    def _promotion_payload(self, screen):
        now = fields.Datetime.now()
        visibility_field = {
            "kiosk": "show_on_kiosk",
            "customer_display": "show_on_customer_display",
            "menu_board": "show_on_menu_board",
            "deals_board": "show_on_deals_board",
        }.get(screen.display_type, "show_on_deals_board")
        promotions = request.env["tijara.promotion"].sudo().search(
            [
                ("active", "=", True),
                ("company_id", "=", screen.company_id.id),
                (visibility_field, "=", True),
                "|",
                ("start_at", "=", False),
                ("start_at", "<=", now),
                "|",
                ("end_at", "=", False),
                ("end_at", ">=", now),
            ],
            order="sequence, name",
            limit=12,
        )
        return [
            {
                "name": promo.name,
                "code": promo.code,
                "type": promo.promotion_type,
                "applies_to": promo.applies_to,
                "title_english": promo.title_english or promo.name,
                "title_urdu": promo.title_urdu or "",
                "description": promo.display_description or "",
                "discount_percent": promo.discount_percent,
                "fixed_price": promo.fixed_price,
            }
            for promo in promotions
        ]

    def _kiosk_allowed_order_types(self, profile):
        allowed = []
        if profile.allow_dine_in:
            allowed.append("dine_in")
        if profile.allow_takeaway:
            allowed.append("takeaway")
        if profile.allow_pickup:
            allowed.append("pickup")
        return allowed or [profile.default_order_type]

    def _kiosk_allowed_payment_methods(self, profile):
        allowed = []
        if profile.allow_cash:
            allowed.append("cash")
        if profile.allow_card:
            allowed.append("card")
        if profile.allow_bank_transfer:
            allowed.append("bank_transfer")
        return allowed or ["cash"]

    def _kiosk_allowed_audiences(self, profile):
        audiences = []
        company = profile.company_id
        if profile.allow_b2c:
            audiences.append("b2c")
        if profile.allow_b2b and company.tijara_has_saas_feature("b2b_sales"):
            audiences.append("b2b")
        return audiences or ["b2c"]

    def _fallback_kiosk_items(self, screen):
        products = request.env["product.product"].sudo().search(
            [
                ("sale_ok", "=", True),
                ("available_in_pos", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", screen.company_id.id),
            ],
            order="display_name",
            limit=48,
        )
        items = []
        for product in products:
            b2c_price, b2b_price = self._product_prices(product)
            tmpl = product.product_tmpl_id
            items.append(
                {
                    "id": False,
                    "product_id": product.id,
                    "name": product.display_name,
                    "type": "product",
                    "title_english": product.display_name,
                    "title_urdu": getattr(tmpl, "tijara_urdu_name", "") or "",
                    "subtitle_english": product.default_code or product.barcode or "",
                    "subtitle_urdu": "",
                    "product": product.display_name,
                    "barcode": product.barcode or "",
                    "default_code": product.default_code or "",
                    "b2c_price": b2c_price,
                    "b2b_price": b2b_price,
                    "promotion": "",
                }
            )
        return items

    def _kiosk_items_payload(self, screen):
        items = [
            item
            for item in self._content_payload(screen)
            if item["type"] in ("menu_item", "deal", "promotion", "product")
        ]
        return items or self._fallback_kiosk_items(screen)

    def _kiosk_payload(self, screen):
        profile = self._find_kiosk_profile(screen)
        profile_payload = {
            "id": profile.id if profile else False,
            "name": profile.name if profile else screen.name,
            "default_order_type": profile.default_order_type if profile else "takeaway",
            "allowed_order_types": self._kiosk_allowed_order_types(profile)
            if profile
            else ["takeaway"],
            "allowed_audiences": self._kiosk_allowed_audiences(profile) if profile else ["b2c"],
            "allowed_payment_methods": self._kiosk_allowed_payment_methods(profile)
            if profile
            else ["cash"],
            "require_customer_for_b2b": profile.require_customer_for_b2b if profile else True,
            "require_mobile_for_pickup": profile.require_mobile_for_pickup if profile else True,
        }
        return {
            "profile": profile_payload,
            "items": self._kiosk_items_payload(screen),
        }

    def _customer_display_payload(self, screen):
        state = request.env["tijara.customer.display.state"].sudo().search(
            [("active", "=", True), ("screen_id", "=", screen.id)],
            order="last_event_at desc, write_date desc, id desc",
            limit=1,
        )
        if not state:
            return {
                "status": "idle",
                "message_english": "Welcome",
                "message_urdu": "",
                "order_reference": "",
                "lines": [],
                "totals": {"subtotal": 0.0, "discount": 0.0, "tax": 0.0, "total": 0.0},
            }
        return state.tijara_payload()

    def _screen_payload(self, screen):
        payload = {
            "screen": {
                "name": screen.name,
                "code": screen.code,
                "display_type": screen.display_type,
                "language_mode": screen.language_mode,
                "orientation": screen.orientation,
                "price_mode": screen.price_mode,
                "refresh_seconds": max(screen.refresh_seconds or 15, 5),
                "company": screen.company_id.display_name,
            },
            "content": self._content_payload(screen),
            "queue": self._queue_payload(screen) if screen.display_type == "queue_display" else [],
            "promotions": self._promotion_payload(screen),
        }
        if screen.display_type == "kiosk":
            payload["kiosk"] = self._kiosk_payload(screen)
        if screen.display_type == "customer_display":
            payload["customer_display"] = self._customer_display_payload(screen)
        return payload

    def _display_html_shell(self, screen):
        title = html.escape(screen.name)
        refresh = max(screen.refresh_seconds or 15, 5)
        slug = html.escape(screen.url_slug or screen.code)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{refresh * 20}">
<title>{title}</title>
<style>
:root {{ color-scheme: light; font-family: Arial, sans-serif; }}
body {{ margin: 0; background: #f7f7f3; color: #171717; }}
.screen {{ min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }}
.header {{ padding: 24px 56px; background: #122620; color: white; display: flex; justify-content: space-between; gap: 24px; align-items: end; }}
.header h1 {{ margin: 0; font-size: 3.2rem; letter-spacing: 0; }}
.header span {{ font-size: 1.4rem; color: #d6e5df; }}
.grid {{ padding: 32px; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; }}
.tile {{ background: white; border: 1px solid #d9ddd6; border-radius: 8px; padding: 20px; min-height: 150px; display: grid; align-content: space-between; }}
.tile h2 {{ margin: 0 0 10px; font-size: 2rem; letter-spacing: 0; }}
.tile p {{ margin: 0; font-size: 1.1rem; color: #555; }}
.price {{ font-size: 2.3rem; font-weight: 700; margin-top: 16px; }}
.queue {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }}
.queue .tile {{ text-align: center; min-height: 120px; }}
.queue-number {{ font-size: 4rem; font-weight: 800; }}
.state {{ text-transform: uppercase; font-weight: 700; color: #0f6b56; }}
.customer-display {{ display: grid; grid-template-columns: 1.2fr .8fr; gap: 20px; width: 100%; }}
.line {{ display: grid; grid-template-columns: 1fr auto auto; gap: 14px; padding: 14px 0; border-bottom: 1px solid #e2e5df; font-size: 1.25rem; }}
.totals {{ background: #16251f; color: white; border-radius: 8px; padding: 24px; display: grid; gap: 12px; align-content: start; }}
.total-row {{ display: flex; justify-content: space-between; gap: 16px; font-size: 1.2rem; }}
.total-row.strong {{ font-size: 2.2rem; font-weight: 800; }}
@media (max-width: 720px) {{
  .header {{ display: block; padding: 20px; }}
  .header h1 {{ font-size: 2.2rem; }}
  .grid {{ grid-template-columns: 1fr; padding: 18px; }}
  .customer-display {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<main class="screen">
<header class="header"><h1>{title}</h1><span data-role="clock"></span></header>
<section class="grid" data-role="items"></section>
</main>
<script>
const endpoint = "/tijara/display/{slug}/data";
function escapeText(value) {{
  return String(value || "").replace(/[&<>"']/g, char => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[char]));
}}
function money(value) {{
  return new Intl.NumberFormat(undefined, {{ maximumFractionDigits: 2 }}).format(Number(value || 0));
}}
function renderTile(item, priceMode) {{
  const title = escapeText(item.title_english || item.name || item.number || "");
  const sub = escapeText(item.subtitle_english || item.description || item.product || item.state || "");
  const price = priceMode === "b2b" ? item.b2b_price : item.b2c_price;
  return `<article class="tile"><div><h2>${{title}}</h2><p>${{sub}}</p></div>${{price ? `<div class="price">PKR ${{money(price)}}</div>` : ""}}</article>`;
}}
function renderQueue(items) {{
  return `<div class="queue">${{items.map(item => `<article class="tile"><div class="queue-number">${{escapeText(item.number)}}</div><div class="state">${{escapeText(item.state)}}</div><p>${{escapeText(item.pickup_code || item.order_type)}}</p></article>`).join("")}}</div>`;
}}
function renderCustomerDisplay(display) {{
  const lines = display.lines || [];
  const totals = display.totals || {{}};
  const lineHtml = lines.map(line => `<div class="line"><span>${{escapeText(line.name)}}</span><span>${{money(line.quantity)}}</span><strong>PKR ${{money(line.subtotal)}}</strong></div>`).join("");
  return `<div class="customer-display"><article class="tile"><h2>${{escapeText(display.order_reference || display.message_english || "Welcome")}}</h2>${{lineHtml || `<p>${{escapeText(display.message_english || "Welcome")}}</p>`}}</article><aside class="totals"><div class="total-row"><span>Subtotal</span><strong>PKR ${{money(totals.subtotal)}}</strong></div><div class="total-row"><span>Discount</span><strong>PKR ${{money(totals.discount)}}</strong></div><div class="total-row"><span>Tax</span><strong>PKR ${{money(totals.tax)}}</strong></div><div class="total-row strong"><span>Total</span><strong>PKR ${{money(totals.total)}}</strong></div></aside></div>`;
}}
async function load() {{
  const data = await fetch(endpoint).then(response => response.json());
  document.querySelector('[data-role="clock"]').textContent = new Date().toLocaleTimeString([], {{ hour: "2-digit", minute: "2-digit" }});
  const items = document.querySelector('[data-role="items"]');
  if (data.customer_display) {{
    items.innerHTML = renderCustomerDisplay(data.customer_display);
    return;
  }}
  const queue = data.queue || [];
  if (queue.length) {{
    items.innerHTML = renderQueue(queue);
    return;
  }}
  const merged = [...(data.content || []), ...(data.promotions || [])];
  items.innerHTML = merged.map(item => renderTile(item, data.screen.price_mode)).join("");
}}
load();
setInterval(load, {refresh * 1000});
</script>
</body>
</html>"""

    def _kiosk_html_shell(self, screen):
        title = html.escape(screen.name)
        refresh = max(screen.refresh_seconds or 15, 5)
        slug = html.escape(screen.url_slug or screen.code)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light; font-family: Arial, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f4f5f0; color: #171717; }}
button, input, select {{ font: inherit; }}
.kiosk {{ min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }}
.topbar {{ background: #17332d; color: white; padding: 18px 24px; display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
.topbar h1 {{ margin: 0; font-size: 2rem; letter-spacing: 0; }}
.topbar span {{ color: #d7ece5; }}
.layout {{ display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 20px; padding: 20px; }}
.panel {{ background: white; border: 1px solid #dadecf; border-radius: 8px; }}
.toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; padding: 14px; border-bottom: 1px solid #e4e6df; }}
.segmented {{ display: inline-flex; gap: 6px; padding: 4px; background: #edf1ea; border-radius: 8px; }}
.segmented button, .checkout button {{ min-height: 46px; border: 0; border-radius: 7px; padding: 0 14px; background: transparent; color: #18201d; cursor: pointer; }}
.segmented button.active {{ background: #17332d; color: white; }}
.products {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; padding: 14px; }}
.product {{ min-height: 150px; display: grid; gap: 10px; align-content: space-between; border: 1px solid #dde1d7; border-radius: 8px; background: #fff; padding: 14px; text-align: left; cursor: pointer; }}
.product strong {{ font-size: 1.05rem; }}
.product small {{ color: #68706a; }}
.product .price {{ font-size: 1.25rem; font-weight: 800; color: #17332d; }}
.checkout {{ padding: 16px; display: grid; gap: 12px; align-content: start; }}
.checkout h2 {{ margin: 0; font-size: 1.4rem; }}
.cart-line {{ display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 10px 0; border-bottom: 1px solid #e6e8e1; }}
.qty {{ display: inline-flex; align-items: center; gap: 8px; }}
.qty button {{ min-width: 38px; min-height: 38px; background: #edf1ea; border: 0; border-radius: 7px; }}
.field {{ display: grid; gap: 5px; }}
.field label {{ font-size: .9rem; color: #59625b; }}
.field input, .field select {{ min-height: 44px; border: 1px solid #d1d7cd; border-radius: 7px; padding: 0 10px; }}
.summary {{ display: flex; justify-content: space-between; gap: 12px; font-size: 1.3rem; font-weight: 800; }}
.checkout-submit {{ min-height: 52px; background: #c23b22; color: white; border: 0; border-radius: 8px; font-weight: 800; cursor: pointer; }}
.muted {{ color: #66706a; }}
.result {{ min-height: 24px; font-weight: 700; color: #0b6b54; }}
@media (max-width: 900px) {{
  .layout {{ grid-template-columns: 1fr; padding: 12px; }}
  .topbar {{ display: block; }}
  .products {{ grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }}
}}
</style>
</head>
<body>
<main class="kiosk">
<header class="topbar"><h1>{title}</h1><span data-role="clock"></span></header>
<section class="layout">
  <div class="panel">
    <div class="toolbar">
      <div class="segmented" data-role="order-types"></div>
      <div class="segmented" data-role="audiences"></div>
    </div>
    <div class="products" data-role="kiosk-products"></div>
  </div>
  <aside class="panel checkout">
    <h2>Cart</h2>
    <div data-role="cart-lines" class="muted">Empty</div>
    <div class="summary"><span>Total</span><span data-role="cart-total">PKR 0</span></div>
    <div class="field"><label>Name</label><input data-role="customer-name" autocomplete="name"></div>
    <div class="field"><label>Mobile</label><input data-role="customer-mobile" inputmode="tel" autocomplete="tel"></div>
    <div class="field"><label>Payment</label><select data-role="payment-method"></select></div>
    <button class="checkout-submit" data-role="checkout-submit">Checkout</button>
    <div class="result" data-role="checkout-result"></div>
  </aside>
</section>
</main>
<script>
const dataEndpoint = "/tijara/kiosk/{slug}/data";
const checkoutEndpoint = "/tijara/kiosk/{slug}/checkout";
const cart = new Map();
let kioskData = null;
let currentAudience = "b2c";
let currentOrderType = "takeaway";
function escapeText(value) {{
  return String(value || "").replace(/[&<>"']/g, char => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[char]));
}}
function money(value) {{
  return `PKR ${{new Intl.NumberFormat(undefined, {{ maximumFractionDigits: 2 }}).format(Number(value || 0))}}`;
}}
function itemPrice(item) {{
  return currentAudience === "b2b" ? Number(item.b2b_price || item.b2c_price || 0) : Number(item.b2c_price || 0);
}}
function setActive(container, value) {{
  [...container.querySelectorAll("button")].forEach(button => button.classList.toggle("active", button.dataset.value === value));
}}
function renderSegments() {{
  const profile = kioskData.kiosk.profile;
  const orderTypes = document.querySelector('[data-role="order-types"]');
  const audiences = document.querySelector('[data-role="audiences"]');
  orderTypes.innerHTML = profile.allowed_order_types.map(type => `<button type="button" data-value="${{type}}">${{escapeText(type.replace("_", " "))}}</button>`).join("");
  audiences.innerHTML = profile.allowed_audiences.map(type => `<button type="button" data-value="${{type}}">${{escapeText(type.toUpperCase())}}</button>`).join("");
  currentOrderType = profile.allowed_order_types.includes(profile.default_order_type) ? profile.default_order_type : profile.allowed_order_types[0];
  currentAudience = profile.allowed_audiences[0] || "b2c";
  orderTypes.addEventListener("click", event => {{ if (event.target.dataset.value) {{ currentOrderType = event.target.dataset.value; setActive(orderTypes, currentOrderType); }} }});
  audiences.addEventListener("click", event => {{ if (event.target.dataset.value) {{ currentAudience = event.target.dataset.value; setActive(audiences, currentAudience); renderProducts(); renderCart(); }} }});
  setActive(orderTypes, currentOrderType);
  setActive(audiences, currentAudience);
  const payment = document.querySelector('[data-role="payment-method"]');
  payment.innerHTML = profile.allowed_payment_methods.map(method => `<option value="${{method}}">${{escapeText(method.replace("_", " "))}}</option>`).join("");
}}
function renderProducts() {{
  const products = document.querySelector('[data-role="kiosk-products"]');
  products.innerHTML = kioskData.kiosk.items.map(item => `<button type="button" class="product" data-key="${{item.id ? `content:${{item.id}}` : `product:${{item.product_id}}`}}"><strong>${{escapeText(item.title_english || item.product || item.name)}}</strong><small>${{escapeText(item.subtitle_english || item.default_code || item.barcode || "")}}</small><span class="price">${{money(itemPrice(item))}}</span></button>`).join("");
}}
function renderCart() {{
  const lines = document.querySelector('[data-role="cart-lines"]');
  const total = [...cart.values()].reduce((sum, entry) => sum + itemPrice(entry.item) * entry.qty, 0);
  document.querySelector('[data-role="cart-total"]').textContent = money(total);
  if (!cart.size) {{
    lines.className = "muted";
    lines.innerHTML = "Empty";
    return;
  }}
  lines.className = "";
  lines.innerHTML = [...cart.entries()].map(([key, entry]) => `<div class="cart-line"><span>${{escapeText(entry.item.title_english || entry.item.product || entry.item.name)}}<br><small>${{money(itemPrice(entry.item))}}</small></span><span class="qty"><button type="button" data-dec="${{key}}">-</button><strong>${{entry.qty}}</strong><button type="button" data-inc="${{key}}">+</button></span></div>`).join("");
}}
function addToCart(item) {{
  const key = item.id ? `content:${{item.id}}` : `product:${{item.product_id}}`;
  const existing = cart.get(key) || {{ item, qty: 0 }};
  existing.qty += 1;
  cart.set(key, existing);
  renderCart();
}}
async function submitCheckout() {{
  const lines = [...cart.values()].map(entry => ({{ content_id: entry.item.id || false, product_id: entry.item.product_id || false, qty: entry.qty }}));
  const payload = {{
    order_type: currentOrderType,
    audience: currentAudience,
    payment_method: document.querySelector('[data-role="payment-method"]').value,
    customer_name: document.querySelector('[data-role="customer-name"]').value,
    customer_mobile: document.querySelector('[data-role="customer-mobile"]').value,
    lines,
  }};
  const result = document.querySelector('[data-role="checkout-result"]');
  result.textContent = "";
  const response = await fetch(checkoutEndpoint, {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify(payload) }});
  const data = await response.json();
  if (!response.ok) {{
    result.style.color = "#b11f1f";
    result.textContent = data.message || "Checkout failed";
    return;
  }}
  cart.clear();
  renderCart();
  result.style.color = "#0b6b54";
  result.textContent = `${{data.order_name}} ready for queue ${{data.queue_number || data.pickup_code || ""}}`;
}}
async function load() {{
  kioskData = await fetch(dataEndpoint).then(response => response.json());
  document.querySelector('[data-role="clock"]').textContent = new Date().toLocaleTimeString([], {{ hour: "2-digit", minute: "2-digit" }});
  renderSegments();
  renderProducts();
  renderCart();
}}
document.querySelector('[data-role="kiosk-products"]').addEventListener("click", event => {{
  const button = event.target.closest("button[data-key]");
  if (!button) return;
  const item = kioskData.kiosk.items.find(candidate => (candidate.id ? `content:${{candidate.id}}` : `product:${{candidate.product_id}}`) === button.dataset.key);
  if (item) addToCart(item);
}});
document.querySelector('[data-role="cart-lines"]').addEventListener("click", event => {{
  const inc = event.target.dataset.inc;
  const dec = event.target.dataset.dec;
  if (inc && cart.has(inc)) {{ cart.get(inc).qty += 1; renderCart(); }}
  if (dec && cart.has(dec)) {{ const entry = cart.get(dec); entry.qty -= 1; if (entry.qty <= 0) cart.delete(dec); renderCart(); }}
}});
document.querySelector('[data-role="checkout-submit"]').addEventListener("click", submitCheckout);
load();
setInterval(() => {{
  document.querySelector('[data-role="clock"]').textContent = new Date().toLocaleTimeString([], {{ hour: "2-digit", minute: "2-digit" }});
}}, {refresh * 1000});
</script>
</body>
</html>"""

    def _html_shell(self, screen):
        if screen.display_type == "kiosk":
            return self._kiosk_html_shell(screen)
        return self._display_html_shell(screen)

    def _catalog_entry_from_payload_item(self, item):
        return {
            "content_id": item["id"] or False,
            "product_id": item["product_id"] or False,
            "display_name": item["title_english"] or item["product"] or item["name"],
            "b2c_price": item["b2c_price"],
            "b2b_price": item["b2b_price"] or item["b2c_price"],
        }

    def _kiosk_catalog(self, screen):
        catalog = {}
        for item in self._kiosk_items_payload(screen):
            entry = self._catalog_entry_from_payload_item(item)
            if item["id"]:
                catalog[("content", item["id"])] = entry
            if item["product_id"]:
                catalog[("product", item["product_id"])] = entry
        return catalog

    def _create_kiosk_order_from_payload(self, screen, payload):
        profile = self._find_kiosk_profile(screen)
        if not profile:
            raise UserError("No active kiosk profile is configured for this screen.")
        if not self._screen_allowed(screen):
            raise UserError("Kiosk feature is not enabled for this tenant.")

        allowed_order_types = self._kiosk_allowed_order_types(profile)
        order_type = payload.get("order_type") or profile.default_order_type
        if order_type not in allowed_order_types:
            raise UserError("This order type is not available on this kiosk.")

        allowed_audiences = self._kiosk_allowed_audiences(profile)
        audience = payload.get("audience") or (allowed_audiences[0] if allowed_audiences else "b2c")
        if audience not in allowed_audiences:
            raise UserError("This sale type is not available on this kiosk.")

        allowed_payment_methods = self._kiosk_allowed_payment_methods(profile)
        payment_method = payload.get("payment_method") or allowed_payment_methods[0]
        if payment_method not in allowed_payment_methods:
            raise UserError("This payment method is not available on this kiosk.")

        customer_name = (payload.get("customer_name") or "").strip()
        customer_mobile = (payload.get("customer_mobile") or "").strip()
        if audience == "b2b" and profile.require_customer_for_b2b and not customer_name:
            raise UserError("Customer name is required for B2B kiosk orders.")
        if order_type == "pickup" and profile.require_mobile_for_pickup and not customer_mobile:
            raise UserError("Mobile number is required for pickup kiosk orders.")

        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise UserError("Add at least one item before checkout.")

        catalog = self._kiosk_catalog(screen)
        line_values = []
        for raw_line in raw_lines:
            content_id = int(raw_line.get("content_id") or 0)
            product_id = int(raw_line.get("product_id") or 0)
            qty = float(raw_line.get("qty") or raw_line.get("quantity") or 0)
            if qty <= 0:
                raise UserError("Kiosk order quantities must be greater than zero.")
            if qty > 99:
                raise UserError("Kiosk order quantity is too high for one line.")
            entry = catalog.get(("content", content_id)) if content_id else False
            if not entry and product_id:
                entry = catalog.get(("product", product_id))
            if not entry:
                raise UserError("One or more kiosk order items are not available.")
            price_unit = entry["b2b_price"] if audience == "b2b" else entry["b2c_price"]
            line_values.append(
                (
                    0,
                    0,
                    {
                        "display_content_id": entry["content_id"],
                        "product_id": entry["product_id"],
                        "name": entry["display_name"],
                        "quantity": qty,
                        "price_unit": price_unit,
                    },
                )
            )

        order = request.env["tijara.kiosk.order"].sudo().create(
            {
                "profile_id": profile.id,
                "screen_id": screen.id,
                "company_id": screen.company_id.id,
                "customer_name": customer_name,
                "customer_mobile": customer_mobile,
                "customer_email": (payload.get("customer_email") or "").strip(),
                "order_type": order_type,
                "audience": audience,
                "payment_method": payment_method,
                "payment_provider": payload.get("payment_provider") or "manual",
                "payment_status": payload.get("payment_status") or "pay_at_counter",
                "payment_reference": (payload.get("payment_reference") or "").strip(),
                "payment_terminal_id": (payload.get("payment_terminal_id") or "").strip(),
                "notes": (payload.get("notes") or "").strip(),
                "line_ids": line_values,
            }
        )
        order.action_submit()
        return order

    @http.route(
        ["/tijara/display/<string:slug>/data", "/tijara/kiosk/<string:slug>/data"],
        type="http",
        auth="public",
        csrf=False,
    )
    def display_data(self, slug, **kwargs):
        screen = self._find_screen(slug)
        if not screen:
            return self._json_response({"status": "not_found"}, status=404)
        if not self._screen_allowed(screen):
            return self._json_response({"status": "forbidden"}, status=403)
        return self._json_response(self._screen_payload(screen))

    @http.route(
        ["/tijara/kiosk/<string:slug>/checkout"],
        type="http",
        methods=["POST"],
        auth="public",
        csrf=False,
    )
    def kiosk_checkout(self, slug, **kwargs):
        screen = self._find_screen(slug)
        if not screen or screen.display_type != "kiosk":
            return self._json_response({"status": "not_found"}, status=404)
        try:
            order = self._create_kiosk_order_from_payload(screen, self._request_json_payload())
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(
            {
                "status": "ok",
                "order_id": order.id,
                "order_name": order.name,
                "pickup_code": order.pickup_code or "",
                "queue_number": order.queue_ticket_id.queue_number or "",
                "amount_total": order.amount_total,
                "payment_status": order.payment_status,
                "pos_order_id": order.pos_order_id.id or False,
                "pos_sync_error": order.pos_sync_error or "",
            }
        )

    @http.route(
        "/tijara/customer-display/publish",
        type="json",
        methods=["POST"],
        auth="user",
        csrf=False,
    )
    def publish_customer_display(self, config_id=False, order=False, status="building", **kwargs):
        config = request.env["pos.config"].sudo().browse(int(config_id or 0)).exists()
        if not config or not config.tijara_customer_display_enabled or not config.tijara_customer_display_id:
            return {"status": "ignored"}
        screen = config.tijara_customer_display_id
        if not screen.company_id.tijara_has_saas_feature("customer_display"):
            return {"status": "forbidden"}
        state = request.env["tijara.customer.display.state"].sudo().tijara_publish_frontend_order(
            screen,
            order or {},
            status=status or "building",
        )
        return {"status": "ok", "state_id": state.id}

    @http.route(
        "/tijara/offline-pos/capture",
        type="http",
        methods=["POST"],
        auth="user",
        csrf=False,
    )
    def offline_pos_capture(self, **kwargs):
        try:
            request_payload = self._request_json_payload()
            payload = request_payload.get("payload") or request_payload
            replay = request_payload.get("replay", True)
            if isinstance(replay, str):
                replay = replay.strip().lower() not in ("0", "false", "no")
            result = request.env["tijara.offline.pos.queue"].sudo().tijara_capture_from_browser(
                payload,
                replay=bool(replay),
            )
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(result)

    @http.route(
        "/tijara/offline-pos/replay",
        type="http",
        methods=["POST"],
        auth="user",
        csrf=False,
    )
    def offline_pos_replay(self, **kwargs):
        try:
            payload = self._request_json_payload()
            result = request.env["tijara.offline.pos.queue"].sudo().tijara_replay_pending(
                limit=int(payload.get("limit") or 20),
                source_device_id=(payload.get("source_device_id") or "").strip() or False,
            )
        except (UserError, ValidationError, ValueError) as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(result)

    @http.route(
        "/tijara/offline-pos/status",
        type="http",
        methods=["GET"],
        auth="user",
        csrf=False,
    )
    def offline_pos_status(self, **kwargs):
        domain = []
        source_device_id = (kwargs.get("source_device_id") or "").strip()
        if source_device_id:
            domain.append(("source_device_id", "=", source_device_id))
        rows = request.env["tijara.offline.pos.queue"].sudo().read_group(
            domain,
            ["state"],
            ["state"],
        )
        counts = {row["state"]: row["state_count"] for row in rows}
        return self._json_response({"status": "ok", "counts": counts})

    @http.route(
        ["/tijara/display/<string:slug>", "/tijara/kiosk/<string:slug>"],
        type="http",
        auth="public",
        csrf=False,
    )
    def display_screen(self, slug, **kwargs):
        screen = self._find_screen(slug)
        if not screen:
            return request.make_response("Display screen not found", status=404)
        if not self._screen_allowed(screen):
            return request.make_response("Display screen feature is not enabled", status=403)
        return request.make_response(
            self._html_shell(screen),
            headers=[("Content-Type", "text/html; charset=utf-8")],
        )
