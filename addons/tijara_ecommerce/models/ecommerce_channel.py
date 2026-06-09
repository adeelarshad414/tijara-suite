import json

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class TijaraEcommerceChannel(models.Model):
    _name = "tijara.ecommerce.channel"
    _description = "Tijara Ecommerce Channel"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    url_slug = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    website_id = fields.Many2one("website")
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True)
    warehouse_id = fields.Many2one("stock.warehouse", default=lambda self: self._default_warehouse())
    stock_location_id = fields.Many2one("stock.location", string="Stock Location")
    default_audience = fields.Selection([("b2c", "B2C"), ("b2b", "B2B")], default="b2c", required=True)
    allow_b2c = fields.Boolean(default=True)
    allow_b2b = fields.Boolean(default=True)
    allow_guest_checkout = fields.Boolean(default=True)
    require_mobile_for_pickup_delivery = fields.Boolean(default=True)
    allow_delivery = fields.Boolean(default=True)
    allow_pickup = fields.Boolean(default=True)
    allow_store_pickup = fields.Boolean(default=True)
    allow_courier = fields.Boolean()
    allow_takeaway = fields.Boolean(default=True)
    allow_dine_in = fields.Boolean()
    allow_cash = fields.Boolean(default=True)
    allow_card = fields.Boolean(default=True)
    allow_bank_transfer = fields.Boolean(default=True)
    allow_cod = fields.Boolean(default=True)
    allow_jazzcash = fields.Boolean()
    allow_easypaisa = fields.Boolean()
    allow_stripe = fields.Boolean()
    auto_confirm_sale_order = fields.Boolean(string="Auto Confirm Sale Order")
    auto_queue_pickup_delivery = fields.Boolean(string="Auto Queue Pickup/Delivery", default=True)
    show_stock_qty = fields.Boolean(default=True)
    low_stock_threshold = fields.Float(default=10.0)
    promotion_ids = fields.Many2many(
        "tijara.promotion",
        "tijara_ecommerce_channel_promotion_rel",
        "channel_id",
        "promotion_id",
        string="Online Promotions",
    )
    product_count = fields.Integer(compute="_compute_counts")
    sale_order_count = fields.Integer(compute="_compute_counts")
    queue_ticket_count = fields.Integer(compute="_compute_counts")
    notes = fields.Text()

    @api.model
    def _default_warehouse(self):
        return self.env["stock.warehouse"].sudo().search([("company_id", "=", self.env.company.id)], limit=1)

    @api.depends("company_id")
    def _compute_counts(self):
        product_model = self.env["product.template"].sudo()
        order_model = self.env["sale.order"].sudo()
        ticket_model = self.env["tijara.queue.ticket"].sudo()
        for channel in self:
            product_domain = channel._public_product_domain()
            channel.product_count = product_model.search_count(product_domain)
            channel.sale_order_count = order_model.search_count([("tijara_ecommerce_channel_id", "=", channel.id)])
            channel.queue_ticket_count = ticket_model.search_count([("sale_order_id.tijara_ecommerce_channel_id", "=", channel.id)])

    @api.constrains("default_audience", "allow_b2b", "allow_b2c")
    def _check_audience_config(self):
        for channel in self:
            if channel.default_audience == "b2b" and not channel.allow_b2b:
                raise ValidationError(_("Default audience is B2B but B2B is disabled."))
            if channel.default_audience == "b2c" and not channel.allow_b2c:
                raise ValidationError(_("Default audience is B2C but B2C is disabled."))
            if not channel.allow_b2b and not channel.allow_b2c:
                raise ValidationError(_("Enable at least one ecommerce audience."))

    @api.constrains("code", "url_slug", "company_id")
    def _check_unique_code_and_slug(self):
        for channel in self:
            domain = [("id", "!=", channel.id), ("company_id", "=", channel.company_id.id)]
            if channel.code and self.search_count(domain + [("code", "=", channel.code)]):
                raise ValidationError(_("The ecommerce channel code must be unique per company."))
            if channel.url_slug and self.search_count(domain + [("url_slug", "=", channel.url_slug)]):
                raise ValidationError(_("The ecommerce URL slug must be unique per company."))

    def _public_product_domain(self):
        self.ensure_one()
        domain = [
            ("sale_ok", "=", True),
            ("active", "=", True),
            ("tijara_ecommerce_published", "=", True),
        ]
        if "company_id" in self.env["product.template"]._fields:
            domain = domain + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
        return domain

    def _normalize_audience(self, audience=False):
        self.ensure_one()
        audience = audience or self.default_audience or "b2c"
        if audience not in {"b2c", "b2b"}:
            raise UserError(_("Unsupported ecommerce audience."))
        if audience == "b2c" and not self.allow_b2c:
            raise UserError(_("B2C ecommerce is disabled on this channel."))
        if audience == "b2b":
            if not self.allow_b2b:
                raise UserError(_("B2B ecommerce is disabled on this channel."))
            if not self.company_id.tijara_has_saas_feature("b2b_sales"):
                raise UserError(_("B2B selling is not enabled for this tenant plan."))
        return audience

    def _allowed_fulfillment_methods(self):
        self.ensure_one()
        methods = []
        if self.allow_delivery:
            methods.append("delivery")
        if self.allow_pickup:
            methods.append("pickup")
        if self.allow_store_pickup:
            methods.append("store_pickup")
        if self.allow_courier:
            methods.append("courier")
        if self.allow_takeaway:
            methods.append("takeaway")
        if self.allow_dine_in:
            methods.append("dine_in")
        return methods

    def _normalize_fulfillment_method(self, method=False):
        self.ensure_one()
        allowed = self._allowed_fulfillment_methods()
        if not allowed:
            raise UserError(_("Configure at least one ecommerce fulfillment method."))
        method = method or allowed[0]
        if method not in allowed:
            raise UserError(_("This fulfillment method is disabled on the ecommerce channel."))
        return method

    def _allowed_payment_methods(self):
        self.ensure_one()
        methods = []
        if self.allow_cash:
            methods.append("cash")
        if self.allow_card:
            methods.append("card")
        if self.allow_bank_transfer:
            methods.append("bank_transfer")
        if self.allow_cod:
            methods.append("cod")
        if self.allow_jazzcash:
            methods.append("jazzcash")
        if self.allow_easypaisa:
            methods.append("easypaisa")
        if self.allow_stripe:
            methods.append("stripe")
        return methods

    def _normalize_payment_method(self, method=False, fulfillment_method=False):
        self.ensure_one()
        allowed = self._allowed_payment_methods()
        if not allowed:
            raise UserError(_("Configure at least one ecommerce payment method."))
        method = method or ("cod" if fulfillment_method in {"delivery", "courier"} and "cod" in allowed else allowed[0])
        if method not in allowed:
            raise UserError(_("This payment method is disabled on the ecommerce channel."))
        return method

    def _check_saas_entitlement(self):
        self.ensure_one()
        if not self.company_id.tijara_has_saas_feature("ecommerce_store"):
            raise UserError(_("Ecommerce Store is not enabled for this tenant plan."))

    def action_check_saas_entitlement(self):
        for channel in self:
            channel._check_saas_entitlement()
        return True

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Online Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("tijara_ecommerce_channel_id", "=", self.id)],
            "context": {"default_tijara_ecommerce_channel_id": self.id},
        }

    def action_open_storefront(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "target": "new",
            "url": "/tijara/ecommerce/%s" % self.url_slug,
        }

    def _product_price(self, product, audience):
        tmpl = product.product_tmpl_id
        b2c_price = getattr(tmpl, "tijara_b2c_price", 0.0) or product.lst_price or tmpl.list_price
        b2b_price = getattr(tmpl, "tijara_b2b_price", 0.0) or b2c_price
        return b2b_price if audience == "b2b" else b2c_price

    def _product_stock_qty(self, product):
        self.ensure_one()
        product = product.with_company(self.company_id)
        if self.stock_location_id:
            product = product.with_context(location=self.stock_location_id.id)
        return product.free_qty if "free_qty" in product._fields else product.qty_available

    def _taxes_for_product(self, product):
        self.ensure_one()
        if not getattr(self.company_id, "tijara_gst_enabled", True):
            return self.env["account.tax"]
        return product.taxes_id.filtered(lambda tax: not tax.company_id or tax.company_id == self.company_id)

    def _active_promotions(self, product=False, audience="b2c"):
        self.ensure_one()
        now = fields.Datetime.now()
        promotions = self.promotion_ids or self.env["tijara.promotion"].sudo().search(
            [
                ("active", "=", True),
                ("company_id", "=", self.company_id.id),
                ("applies_to", "in", [audience, "both"]),
                "|",
                ("start_at", "=", False),
                ("start_at", "<=", now),
                "|",
                ("end_at", "=", False),
                ("end_at", ">=", now),
            ],
            order="sequence, name",
            limit=24,
        )
        promotions = promotions.filtered(lambda promo: promo.applies_to in (audience, "both"))
        if product:
            promotions = promotions.filtered(lambda promo: not promo.product_ids or product in promo.product_ids)
        return promotions

    def _promotion_payload(self, promotions):
        return [
            {
                "id": promotion.id,
                "name": promotion.name,
                "code": promotion.code,
                "type": promotion.promotion_type,
                "applies_to": promotion.applies_to,
                "title_english": promotion.title_english or promotion.name,
                "title_urdu": promotion.title_urdu or "",
                "description": promotion.display_description or "",
                "discount_percent": promotion.discount_percent,
                "fixed_price": promotion.fixed_price,
            }
            for promotion in promotions
        ]

    def _product_payload(self, product, audience):
        self.ensure_one()
        tmpl = product.product_tmpl_id
        b2c_price = self._product_price(product, "b2c")
        b2b_price = self._product_price(product, "b2b")
        stock_qty = self._product_stock_qty(product)
        return {
            "product_id": product.id,
            "product_template_id": tmpl.id,
            "name": product.display_name,
            "name_urdu": getattr(tmpl, "tijara_urdu_name", "") or "",
            "short_description": tmpl.tijara_ecommerce_short_description_en or "",
            "short_description_urdu": tmpl.tijara_ecommerce_short_description_ur or "",
            "default_code": product.default_code or tmpl.default_code or "",
            "barcode": product.barcode or tmpl.barcode or "",
            "vertical": getattr(tmpl, "tijara_vertical_tag", "") or "",
            "b2c_price": b2c_price,
            "b2b_price": b2b_price,
            "price": b2b_price if audience == "b2b" else b2c_price,
            "stock_qty": stock_qty if self.show_stock_qty else False,
            "low_stock": bool(stock_qty <= self.low_stock_threshold),
            "uom": product.uom_id.name if product.uom_id else "",
            "promotions": self._promotion_payload(self._active_promotions(product, audience)),
        }

    def _charges_policy_payload(self):
        self.ensure_one()
        return {
            "gst_enabled": bool(getattr(self.company_id, "tijara_gst_enabled", True)),
            "service_charge_enabled": bool(
                self.company_id.tijara_service_charge_enabled
                and self.company_id.tijara_has_cafe_service_charge_policy()
            ),
            "service_charge_percent": self.company_id.tijara_service_charge_percent,
            "delivery_charge_enabled": bool(self.company_id.tijara_delivery_charge_enabled),
            "delivery_charge_amount": self.company_id.tijara_delivery_charge_amount,
            "payment_tax_enabled": bool(
                self.company_id.tijara_food_payment_tax_enabled
                and self.company_id.tijara_has_cafe_restaurant_payment_tax_policy()
            ),
            "card_tax_percent": self.company_id.tijara_food_card_tax_percent,
            "cash_tax_percent": self.company_id.tijara_food_cash_tax_percent,
        }

    def tijara_catalog_payload(self, audience=False, search="", limit=80):
        self.ensure_one()
        self._check_saas_entitlement()
        audience = self._normalize_audience(audience)
        product_domain = self._public_product_domain()
        search = (search or "").strip()
        if search:
            product_domain += [
                "|",
                "|",
                "|",
                ("name", "ilike", search),
                ("default_code", "ilike", search),
                ("barcode", "ilike", search),
                ("tijara_ecommerce_meta_keywords", "ilike", search),
            ]
        templates = self.env["product.template"].sudo().search(
            product_domain,
            order="tijara_ecommerce_featured desc, tijara_ecommerce_sequence, name",
            limit=max(1, min(int(limit or 80), 200)),
        )
        products = templates.mapped("product_variant_id")
        return {
            "status": "ok",
            "channel": {
                "id": self.id,
                "name": self.name,
                "code": self.code,
                "slug": self.url_slug,
                "currency": self.currency_id.name,
                "allow_b2c": self.allow_b2c,
                "allow_b2b": self.allow_b2b,
                "default_audience": self.default_audience,
            },
            "fulfillment": {"methods": self._allowed_fulfillment_methods()},
            "payment": {"methods": self._allowed_payment_methods()},
            "charges": self._charges_policy_payload(),
            "promotions": self._promotion_payload(self._active_promotions(audience=audience)),
            "products": [self._product_payload(product, audience) for product in products],
        }

    def _line_tax_amount(self, product, price_unit, quantity, partner=False):
        self.ensure_one()
        taxes = self._taxes_for_product(product)
        if not taxes:
            return price_unit * quantity, 0.0
        values = taxes.compute_all(
            price_unit,
            self.currency_id,
            quantity,
            product=product,
            partner=partner or False,
        )
        return values["total_excluded"], values["total_included"] - values["total_excluded"]

    def _payment_tax_rate(self, payment_method):
        self.ensure_one()
        if not (
            self.company_id.tijara_food_payment_tax_enabled
            and self.company_id.tijara_has_cafe_restaurant_payment_tax_policy()
        ):
            return 0.0
        if payment_method in {"cash", "cod"}:
            return self.company_id.tijara_food_cash_tax_percent
        if payment_method in {"card", "jazzcash", "easypaisa", "stripe"}:
            return self.company_id.tijara_food_card_tax_percent
        return 0.0

    def _amount_breakdown(self, resolved_lines, fulfillment_method, payment_method, partner=False):
        self.ensure_one()
        untaxed = 0.0
        gst = 0.0
        for line in resolved_lines:
            line_untaxed, line_gst = self._line_tax_amount(
                line["product"],
                line["price_unit"],
                line["quantity"],
                partner=partner,
            )
            untaxed += line_untaxed
            gst += line_gst
        service_charge = 0.0
        if (
            self.company_id.tijara_service_charge_enabled
            and self.company_id.tijara_has_cafe_service_charge_policy()
        ):
            service_charge = untaxed * self.company_id.tijara_service_charge_percent / 100.0
        delivery_charge = 0.0
        if self.company_id.tijara_delivery_charge_enabled and fulfillment_method in {"delivery", "courier"}:
            delivery_charge = self.company_id.tijara_delivery_charge_amount
        payment_tax = (untaxed + service_charge + delivery_charge) * self._payment_tax_rate(payment_method) / 100.0
        currency = self.currency_id
        values = {
            "untaxed": untaxed,
            "gst": gst,
            "service_charge": service_charge,
            "delivery_charge": delivery_charge,
            "payment_tax": payment_tax,
            "total": untaxed + gst + service_charge + delivery_charge + payment_tax,
        }
        if currency:
            values = {key: currency.round(value) for key, value in values.items()}
        return values

    def _find_product_for_checkout(self, raw_line):
        self.ensure_one()
        product = self.env["product.product"].sudo()
        product_id = int(raw_line.get("product_id") or 0)
        if product_id:
            product = product.browse(product_id).exists()
        if not product:
            default_code = (raw_line.get("default_code") or raw_line.get("sku") or "").strip()
            barcode = (raw_line.get("barcode") or "").strip()
            domain = []
            if default_code and barcode:
                domain = ["|", ("default_code", "=", default_code), ("barcode", "=", barcode)]
            elif default_code:
                domain = [("default_code", "=", default_code)]
            elif barcode:
                domain = [("barcode", "=", barcode)]
            if domain:
                product = self.env["product.product"].sudo().search(domain, limit=1)
        if not product or not product.product_tmpl_id.tijara_ecommerce_published:
            raise UserError(_("One or more ecommerce checkout products are not available online."))
        if product.product_tmpl_id not in self.env["product.template"].sudo().search(self._public_product_domain()):
            raise UserError(_("One or more ecommerce checkout products are not available on this channel."))
        return product

    def _resolve_checkout_lines(self, raw_lines, audience):
        self.ensure_one()
        if not isinstance(raw_lines, list) or not raw_lines:
            raise UserError(_("Add at least one ecommerce checkout line."))
        resolved = []
        for raw_line in raw_lines:
            product = self._find_product_for_checkout(raw_line)
            quantity = float(raw_line.get("quantity") or raw_line.get("qty") or 0.0)
            if quantity <= 0:
                raise UserError(_("Ecommerce checkout quantities must be greater than zero."))
            if quantity > 999:
                raise UserError(_("Ecommerce checkout quantity is too high for one line."))
            resolved.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "price_unit": self._product_price(product, audience),
                    "name": raw_line.get("name") or product.display_name,
                }
            )
        return resolved

    def _partner_from_payload(self, payload, audience):
        self.ensure_one()
        partner_payload = payload.get("customer") or {}
        if not isinstance(partner_payload, dict):
            raise UserError(_("Customer payload must be a JSON object."))
        name = (partner_payload.get("name") or "").strip()
        mobile = (partner_payload.get("mobile") or partner_payload.get("phone") or "").strip()
        email = (partner_payload.get("email") or "").strip()
        if not self.allow_guest_checkout and not (name and (mobile or email)):
            raise UserError(_("Customer name plus mobile or email is required for this ecommerce channel."))
        if self.require_mobile_for_pickup_delivery and not mobile and payload.get("fulfillment_method") in {
            "delivery",
            "pickup",
            "store_pickup",
            "courier",
            "takeaway",
        }:
            raise UserError(_("Mobile number is required for pickup, takeaway, courier, or delivery checkout."))
        partner_model = self.env["res.partner"].sudo()
        partner = partner_model
        domain = []
        if mobile:
            domain = ["|", ("mobile", "=", mobile), ("phone", "=", mobile)] if "mobile" in partner_model._fields else [("phone", "=", mobile)]
        elif email:
            domain = [("email", "=", email)]
        if domain:
            partner = partner_model.search(domain, limit=1)
        values = {
            "name": name or mobile or email or _("Online Guest"),
            "phone": mobile or False,
            "email": email or False,
            "company_id": self.company_id.id,
            "tijara_customer_type": "wholesale" if audience == "b2b" else "retail",
            "tijara_loyalty_opt_in": bool(partner_payload.get("loyalty_opt_in")),
        }
        if "mobile" in partner_model._fields:
            values["mobile"] = mobile or False
        if partner_payload.get("ntn"):
            values["tijara_ntn"] = partner_payload.get("ntn")
        if partner_payload.get("cnic"):
            values["tijara_cnic"] = partner_payload.get("cnic")
        if partner:
            partner.write({key: value for key, value in values.items() if value not in (False, "")})
        else:
            partner = partner_model.create(values)
        return partner

    def _ensure_charge_product(self, default_code, name):
        template_model = self.env["product.template"].sudo()
        template = template_model.search([("default_code", "=", default_code)], limit=1)
        values = {
            "name": name,
            "default_code": default_code,
            "type": "service",
            "sale_ok": True,
            "purchase_ok": False,
            "list_price": 0.0,
            "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        }
        if "available_in_pos" in template_model._fields:
            values["available_in_pos"] = True
        if "invoice_policy" in template_model._fields:
            values["invoice_policy"] = "order"
        if template:
            template.write(values)
        else:
            template = template_model.create(values)
        return template.product_variant_id

    def _sale_order_line_values(self, line):
        self.ensure_one()
        product = line["product"]
        tax_field = "tax_ids" if "tax_ids" in self.env["sale.order.line"]._fields else "tax_id"
        values = {
            "product_id": product.id,
            "name": line["name"],
            "product_uom_qty": line["quantity"],
            "price_unit": line["price_unit"],
            tax_field: [Command.set(self._taxes_for_product(product).ids)],
        }
        return values

    def _charge_line_values(self, label, amount, default_code):
        self.ensure_one()
        product = self._ensure_charge_product(default_code, label)
        tax_field = "tax_ids" if "tax_ids" in self.env["sale.order.line"]._fields else "tax_id"
        return {
            "product_id": product.id,
            "name": label,
            "product_uom_qty": 1.0,
            "price_unit": amount,
            tax_field: [Command.clear()],
        }

    def _payment_status_for_method(self, payment_method):
        if payment_method == "cod":
            return "cod"
        if payment_method == "cash":
            return "pay_at_pickup"
        return "pending"

    def _fulfillment_to_queue_order_type(self, fulfillment_method):
        return {
            "delivery": "delivery",
            "courier": "delivery",
            "pickup": "pickup",
            "store_pickup": "pickup",
            "takeaway": "takeaway",
            "dine_in": "dine_in",
        }.get(fulfillment_method)

    def _pickup_code_for_order(self, order):
        return (order.name or "WEB").replace("/", "")[-6:]

    def tijara_create_order(self, payload):
        self.ensure_one()
        self._check_saas_entitlement()
        if not isinstance(payload, dict):
            raise UserError(_("Ecommerce checkout payload must be a JSON object."))
        audience = self._normalize_audience(payload.get("audience"))
        fulfillment_method = self._normalize_fulfillment_method(payload.get("fulfillment_method") or payload.get("order_type"))
        payment_method = self._normalize_payment_method(payload.get("payment_method"), fulfillment_method=fulfillment_method)
        payload = dict(payload, fulfillment_method=fulfillment_method)
        partner = self._partner_from_payload(payload, audience)
        resolved_lines = self._resolve_checkout_lines(payload.get("lines") or [], audience)
        amounts = self._amount_breakdown(resolved_lines, fulfillment_method, payment_method, partner=partner)
        order_lines = [Command.create(self._sale_order_line_values(line)) for line in resolved_lines]
        charge_specs = [
            ("Service Charge", amounts["service_charge"], "TIJARA-ECOM-SERVICE-CHARGE"),
            ("Delivery Charge", amounts["delivery_charge"], "TIJARA-ECOM-DELIVERY-CHARGE"),
            ("Payment Tax", amounts["payment_tax"], "TIJARA-ECOM-PAYMENT-TAX"),
        ]
        for label, amount, default_code in charge_specs:
            if amount:
                order_lines.append(Command.create(self._charge_line_values(label, amount, default_code)))
        order = (
            self.env["sale.order"]
            .sudo()
            .with_company(self.company_id)
            .create(
                {
                    "partner_id": partner.id,
                    "company_id": self.company_id.id,
                    "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
                    "origin": payload.get("source") or _("Tijara Ecommerce"),
                    "client_order_ref": (payload.get("reference") or "").strip() or False,
                    "tijara_ecommerce_channel_id": self.id,
                    "tijara_ecommerce_reference": (payload.get("reference") or "").strip() or False,
                    "tijara_ecommerce_audience": audience,
                    "tijara_fulfillment_method": fulfillment_method,
                    "tijara_payment_method": payment_method,
                    "tijara_payment_status": self._payment_status_for_method(payment_method),
                    "tijara_delivery_mobile": (payload.get("customer") or {}).get("mobile") or False,
                    "tijara_delivery_address": (payload.get("customer") or {}).get("delivery_address") or False,
                    "tijara_amount_service_charge": amounts["service_charge"],
                    "tijara_amount_delivery_charge": amounts["delivery_charge"],
                    "tijara_amount_payment_tax": amounts["payment_tax"],
                    "tijara_estimated_gst": amounts["gst"],
                    "tijara_ecommerce_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    "order_line": order_lines,
                }
            )
        )
        order.tijara_pickup_code = payload.get("pickup_code") or self._pickup_code_for_order(order)
        if self.auto_confirm_sale_order:
            order.action_confirm()
        if self.auto_queue_pickup_delivery:
            order.action_tijara_create_ecommerce_queue_ticket()
        return order
