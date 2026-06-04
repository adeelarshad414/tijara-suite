from odoo import api, fields, models


class TijaraCustomerDisplayState(models.Model):
    _name = "tijara.customer.display.state"
    _description = "Tijara Customer Display State"
    _order = "last_event_at desc, id desc"

    name = fields.Char(required=True, default="Customer Display State")
    active = fields.Boolean(default=True)
    screen_id = fields.Many2one(
        "tijara.display.screen",
        required=True,
        domain=[("display_type", "=", "customer_display")],
    )
    company_id = fields.Many2one(
        "res.company",
        related="screen_id.company_id",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    status = fields.Selection(
        [
            ("idle", "Idle"),
            ("building", "Building Order"),
            ("payment", "Payment"),
            ("paid", "Paid"),
            ("thank_you", "Thank You"),
        ],
        default="idle",
        required=True,
    )
    order_reference = fields.Char()
    cashier_name = fields.Char()
    customer_name = fields.Char()
    audience = fields.Selection([("b2c", "B2C"), ("b2b", "B2B")], default="b2c")
    order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
        ],
        default="takeaway",
    )
    line_ids = fields.One2many(
        "tijara.customer.display.line",
        "state_id",
        string="Lines",
    )
    amount_subtotal = fields.Monetary(currency_field="currency_id")
    discount_amount = fields.Monetary(currency_field="currency_id")
    tax_amount = fields.Monetary(currency_field="currency_id")
    amount_total = fields.Monetary(currency_field="currency_id")
    payment_summary = fields.Char()
    message_english = fields.Char(default="Welcome")
    message_urdu = fields.Char()
    last_event_at = fields.Datetime(default=fields.Datetime.now)

    def action_set_idle(self):
        self.write(
            {
                "status": "idle",
                "order_reference": False,
                "cashier_name": False,
                "customer_name": False,
                "amount_subtotal": 0,
                "discount_amount": 0,
                "tax_amount": 0,
                "amount_total": 0,
                "payment_summary": False,
                "message_english": "Welcome",
                "message_urdu": False,
                "last_event_at": fields.Datetime.now(),
                "line_ids": [(5, 0, 0)],
            }
        )

    def tijara_payload(self):
        self.ensure_one()
        return {
            "status": self.status,
            "order_reference": self.order_reference or "",
            "cashier": self.cashier_name or "",
            "customer": self.customer_name or "",
            "audience": self.audience,
            "order_type": self.order_type,
            "payment_summary": self.payment_summary or "",
            "message_english": self.message_english or "",
            "message_urdu": self.message_urdu or "",
            "updated_at": fields.Datetime.to_string(self.last_event_at) if self.last_event_at else "",
            "lines": [
                {
                    "name": line.name,
                    "urdu_name": line.urdu_name or "",
                    "quantity": line.quantity,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "subtotal": line.price_subtotal,
                }
                for line in self.line_ids.sorted(lambda line: (line.sequence, line.id))
            ],
            "totals": {
                "subtotal": self.amount_subtotal,
                "discount": self.discount_amount,
                "tax": self.tax_amount,
                "total": self.amount_total,
            },
        }

    @api.model
    def tijara_publish_pos_order(self, screen, order, status="paid"):
        lines = []
        for sequence, line in enumerate(order.lines, start=1):
            product = line.product_id
            tmpl = product.product_tmpl_id if product else False
            lines.append(
                (
                    0,
                    0,
                    {
                        "sequence": sequence,
                        "product_id": product.id if product else False,
                        "name": product.display_name if product else line.full_product_name or line.name,
                        "urdu_name": getattr(tmpl, "tijara_urdu_name", "") if tmpl else "",
                        "quantity": line.qty,
                        "price_unit": line.price_unit,
                        "discount": line.discount,
                        "price_subtotal": line.price_subtotal_incl,
                    },
                )
            )
        state = self.sudo().search(
            [("screen_id", "=", screen.id), ("active", "=", True)],
            limit=1,
        )
        values = {
            "name": "%s Live State" % screen.name,
            "screen_id": screen.id,
            "status": status,
            "order_reference": order.pos_reference or order.name,
            "cashier_name": order.user_id.display_name,
            "customer_name": order.partner_id.display_name,
            "audience": order.tijara_audience or "b2c",
            "order_type": order.tijara_order_type or "takeaway",
            "amount_subtotal": order.amount_total - order.amount_tax,
            "discount_amount": order.tijara_bill_discount_amount,
            "tax_amount": order.amount_tax,
            "amount_total": order.amount_total,
            "payment_summary": ", ".join(order.payment_ids.mapped("payment_method_id.name")),
            "message_english": "Thank you" if status in ("paid", "thank_you") else "Order in progress",
            "last_event_at": fields.Datetime.now(),
            "line_ids": [(5, 0, 0)] + lines,
        }
        if state:
            state.write(values)
        else:
            state = self.sudo().create(values)
        return state

    @api.model
    def tijara_publish_frontend_order(self, screen, payload, status="building"):
        state = self.sudo().search(
            [("screen_id", "=", screen.id), ("active", "=", True)],
            limit=1,
        )
        totals = payload.get("totals") or {}
        values = {
            "name": "%s Live State" % screen.name,
            "screen_id": screen.id,
            "status": status,
            "order_reference": payload.get("order_reference") or "",
            "cashier_name": payload.get("cashier_name") or "",
            "customer_name": payload.get("customer_name") or "",
            "audience": payload.get("audience") or "b2c",
            "order_type": payload.get("order_type") or "takeaway",
            "amount_subtotal": totals.get("subtotal") or 0.0,
            "discount_amount": totals.get("discount") or 0.0,
            "tax_amount": totals.get("tax") or 0.0,
            "amount_total": totals.get("total") or 0.0,
            "payment_summary": payload.get("payment_summary") or "",
            "message_english": payload.get("message_english") or "Order in progress",
            "message_urdu": payload.get("message_urdu") or "",
            "last_event_at": fields.Datetime.now(),
            "line_ids": [(5, 0, 0)]
            + [
                (
                    0,
                    0,
                    {
                        "sequence": sequence * 10,
                        "product_id": line.get("product_id") or False,
                        "name": line.get("name") or "",
                        "urdu_name": line.get("urdu_name") or "",
                        "quantity": line.get("quantity") or 0.0,
                        "price_unit": line.get("price_unit") or 0.0,
                        "discount": line.get("discount") or 0.0,
                        "price_subtotal": line.get("subtotal") or 0.0,
                    },
                )
                for sequence, line in enumerate(payload.get("lines") or [], start=1)
            ],
        }
        if state:
            state.write(values)
        else:
            state = self.sudo().create(values)
        return state


class TijaraCustomerDisplayLine(models.Model):
    _name = "tijara.customer.display.line"
    _description = "Tijara Customer Display Line"
    _order = "state_id, sequence, id"

    state_id = fields.Many2one(
        "tijara.customer.display.state",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product")
    name = fields.Char(required=True)
    urdu_name = fields.Char()
    quantity = fields.Float(default=1.0)
    price_unit = fields.Monetary(currency_field="currency_id")
    discount = fields.Float()
    price_subtotal = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        related="state_id.currency_id",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="state_id.company_id",
        store=True,
    )
