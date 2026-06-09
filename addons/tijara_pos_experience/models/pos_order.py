from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    tijara_order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
            ("delivery", "Delivery"),
        ],
        string="Order Type",
        default="takeaway",
    )
    tijara_audience = fields.Selection(
        [("b2c", "B2C"), ("b2b", "B2B")],
        string="Sale Type",
        default="b2c",
    )
    tijara_queue_ticket_id = fields.Many2one("tijara.queue.ticket")
    tijara_pickup_code = fields.Char(string="Pickup Code")
    tijara_promised_at = fields.Datetime(string="Promised At")
    tijara_bill_discount_mode = fields.Selection(
        [("percent", "Percentage"), ("amount", "Amount")],
        string="Bill Discount Entry Mode",
        default="percent",
    )
    tijara_bill_discount_base_amount = fields.Monetary(
        string="Bill Discount Base",
        currency_field="currency_id",
    )
    tijara_bill_discount_percent = fields.Float(string="Bill Discount %")
    tijara_bill_discount_amount = fields.Monetary(
        string="Bill Discount Amount",
        currency_field="currency_id",
    )
    tijara_bill_discount_net_amount = fields.Monetary(
        string="Net After Bill Discount",
        currency_field="currency_id",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._tijara_autopublish_customer_display()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched = {
            "state",
            "lines",
            "payment_ids",
            "amount_total",
            "amount_paid",
            "tijara_order_type",
            "tijara_audience",
            "tijara_pickup_code",
        }
        if watched.intersection(vals):
            self._tijara_autopublish_customer_display()
        return result

    @api.model
    def _load_pos_data_fields(self, config):
        field_names = super()._load_pos_data_fields(config)
        tijara_fields = [
            "tijara_order_type",
            "tijara_audience",
            "tijara_pickup_code",
            "tijara_promised_at",
            "tijara_bill_discount_mode",
            "tijara_bill_discount_base_amount",
            "tijara_bill_discount_percent",
            "tijara_bill_discount_amount",
            "tijara_bill_discount_net_amount",
        ]
        return field_names + [field for field in tijara_fields if field not in field_names]

    @api.onchange(
        "tijara_bill_discount_mode",
        "tijara_bill_discount_percent",
        "tijara_bill_discount_amount",
        "lines",
        "lines.price_subtotal_incl",
    )
    def _onchange_tijara_bill_discount(self):
        for order in self:
            order._sync_tijara_bill_discount_amounts()

    def _get_tijara_discount_lines(self):
        self.ensure_one()
        discount_product = self.config_id.discount_product_id
        if not discount_product:
            return self.env["pos.order.line"]
        return self.lines.filtered(lambda line: line.product_id == discount_product)

    def _get_tijara_bill_discount_base_amount(self):
        self.ensure_one()
        discount_lines = self._get_tijara_discount_lines()
        base_lines = self.lines - discount_lines
        return sum(base_lines.mapped("price_subtotal_incl"))

    def _sync_tijara_bill_discount_amounts(self):
        for order in self:
            currency = order.currency_id
            base_amount = order._get_tijara_bill_discount_base_amount()
            discount_lines = order._get_tijara_discount_lines()
            actual_discount_amount = abs(sum(discount_lines.mapped("price_subtotal_incl")))

            denominator = abs(base_amount)
            if actual_discount_amount:
                amount = actual_discount_amount
                percent = (amount / denominator * 100.0) if denominator else 0.0
            elif order.tijara_bill_discount_mode == "amount":
                amount = min(max(order.tijara_bill_discount_amount, 0.0), denominator)
                percent = (amount / denominator * 100.0) if denominator else 0.0
            else:
                percent = min(max(order.tijara_bill_discount_percent, 0.0), 100.0)
                amount = denominator * percent / 100.0 if denominator else 0.0

            if currency:
                base_amount = currency.round(base_amount)
                amount = currency.round(amount)

            order.tijara_bill_discount_base_amount = base_amount
            order.tijara_bill_discount_amount = amount
            order.tijara_bill_discount_percent = percent
            order.tijara_bill_discount_net_amount = (
                base_amount - amount if base_amount >= 0 else base_amount + amount
            )

    def action_tijara_publish_customer_display(self):
        for order in self:
            screen = order.config_id.tijara_customer_display_id
            if not screen:
                continue
            self.env["tijara.customer.display.state"].tijara_publish_pos_order(
                screen,
                order,
                status="paid" if order.state in ("paid", "done", "invoiced") else "building",
            )

    def _tijara_autopublish_customer_display(self):
        for order in self:
            config = order.config_id
            if (
                not config
                or not config.tijara_customer_display_enabled
                or not config.tijara_customer_display_id
            ):
                continue
            if not order.company_id.tijara_has_saas_feature("customer_display"):
                continue
            order.action_tijara_publish_customer_display()
