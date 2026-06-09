import json
from datetime import datetime, time

from odoo import Command, _, api, fields, models


class TijaraEcommerceDeliveryReconciliation(models.Model):
    _name = "tijara.ecommerce.delivery.reconciliation"
    _description = "Tijara Ecommerce Delivery Reconciliation"
    _order = "date_to desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("New Delivery Reconciliation"))
    provider_id = fields.Many2one(
        "tijara.ecommerce.delivery.provider",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("reviewed", "Reviewed"),
            ("approved", "Approved"),
        ],
        default="draft",
        required=True,
    )
    line_ids = fields.One2many(
        "tijara.ecommerce.delivery.reconciliation.line",
        "reconciliation_id",
        string="Lines",
    )
    order_count = fields.Integer(compute="_compute_totals", store=True)
    delivered_count = fields.Integer(compute="_compute_totals", store=True)
    failed_count = fields.Integer(compute="_compute_totals", store=True)
    cancelled_count = fields.Integer(compute="_compute_totals", store=True)
    cod_order_count = fields.Integer(compute="_compute_totals", store=True)
    amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    cod_amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    delivery_charge_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    provider_fee_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    net_receivable = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    report_json = fields.Text()
    notes = fields.Text()

    @api.depends(
        "line_ids.amount_total",
        "line_ids.cod_amount",
        "line_ids.delivery_charge",
        "line_ids.provider_fee",
        "line_ids.net_receivable",
        "line_ids.delivery_status",
        "line_ids.payment_method",
    )
    def _compute_totals(self):
        for reconciliation in self:
            lines = reconciliation.line_ids
            reconciliation.order_count = len(lines)
            reconciliation.delivered_count = len(lines.filtered(lambda line: line.delivery_status == "delivered"))
            reconciliation.failed_count = len(lines.filtered(lambda line: line.delivery_status == "failed"))
            reconciliation.cancelled_count = len(lines.filtered(lambda line: line.delivery_status == "cancelled"))
            cod_lines = lines.filtered(lambda line: line.payment_method == "cod")
            reconciliation.cod_order_count = len(cod_lines)
            reconciliation.amount_total = sum(lines.mapped("amount_total"))
            reconciliation.cod_amount_total = sum(lines.mapped("cod_amount"))
            reconciliation.delivery_charge_total = sum(lines.mapped("delivery_charge"))
            reconciliation.provider_fee_total = sum(lines.mapped("provider_fee"))
            reconciliation.net_receivable = sum(lines.mapped("net_receivable"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            provider = self.env["tijara.ecommerce.delivery.provider"].browse(vals.get("provider_id")).exists()
            if provider and not vals.get("company_id"):
                vals["company_id"] = provider.company_id.id
            if provider and vals.get("name") in (False, _("New Delivery Reconciliation"), None):
                vals["name"] = "%s %s to %s" % (
                    provider.code,
                    vals.get("date_from") or fields.Date.context_today(self),
                    vals.get("date_to") or fields.Date.context_today(self),
                )
        return super().create(vals_list)

    def _date_domain(self):
        self.ensure_one()
        start = datetime.combine(self.date_from, time.min)
        end = datetime.combine(self.date_to, time.max)
        return [
            ("date_order", ">=", start),
            ("date_order", "<=", end),
        ]

    def _line_values_for_order(self, order):
        self.ensure_one()
        provider = self.provider_id
        cod_amount = order.amount_total if order.tijara_payment_method == "cod" else 0.0
        provider_fee = provider.provider_fee_flat + (cod_amount * provider.cod_fee_percent / 100.0)
        delivery_charge = order.tijara_amount_delivery_charge or 0.0
        net_receivable = cod_amount - provider_fee
        return {
            "sale_order_id": order.id,
            "order_name": order.name,
            "tracking_number": order.tijara_delivery_tracking_number or "",
            "delivery_status": order.tijara_delivery_status or "not_required",
            "payment_method": order.tijara_payment_method or "",
            "payment_status": order.tijara_payment_status or "",
            "amount_total": order.amount_total,
            "cod_amount": cod_amount,
            "delivery_charge": delivery_charge,
            "provider_fee": provider_fee,
            "net_receivable": net_receivable,
        }

    def _summary_payload(self):
        self.ensure_one()
        return {
            "provider": self.provider_id.code,
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
            "order_count": self.order_count,
            "delivered_count": self.delivered_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "cod_order_count": self.cod_order_count,
            "amount_total": self.amount_total,
            "cod_amount_total": self.cod_amount_total,
            "delivery_charge_total": self.delivery_charge_total,
            "provider_fee_total": self.provider_fee_total,
            "net_receivable": self.net_receivable,
        }

    def action_generate_lines(self):
        order_model = self.env["sale.order"].sudo()
        for reconciliation in self:
            orders = order_model.search(
                [
                    ("tijara_delivery_provider_id", "=", reconciliation.provider_id.id),
                    ("tijara_ecommerce_channel_id", "!=", False),
                ]
                + reconciliation._date_domain(),
                order="date_order asc, id asc",
            )
            reconciliation.line_ids.unlink()
            reconciliation.write(
                {
                    "line_ids": [
                        Command.create(reconciliation._line_values_for_order(order))
                        for order in orders
                    ],
                    "state": "draft",
                }
            )
            reconciliation.report_json = json.dumps(
                reconciliation._summary_payload(),
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        return True

    def action_mark_reviewed(self):
        self.write({"state": "reviewed"})
        return True

    def action_approve(self):
        self.write({"state": "approved"})
        return True


class TijaraEcommerceDeliveryReconciliationLine(models.Model):
    _name = "tijara.ecommerce.delivery.reconciliation.line"
    _description = "Tijara Ecommerce Delivery Reconciliation Line"
    _order = "order_name"

    reconciliation_id = fields.Many2one(
        "tijara.ecommerce.delivery.reconciliation",
        required=True,
        ondelete="cascade",
    )
    provider_id = fields.Many2one(
        "tijara.ecommerce.delivery.provider",
        related="reconciliation_id.provider_id",
        store=True,
    )
    company_id = fields.Many2one("res.company", related="reconciliation_id.company_id", store=True)
    currency_id = fields.Many2one("res.currency", related="reconciliation_id.currency_id", store=True)
    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    order_name = fields.Char()
    tracking_number = fields.Char()
    delivery_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending Assignment"),
            ("assigned", "Assigned"),
            ("picked", "Picked"),
            ("out_for_delivery", "Out For Delivery"),
            ("delivered", "Delivered"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="not_required",
    )
    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
            ("jazzcash", "JazzCash"),
            ("easypaisa", "Easypaisa"),
            ("stripe", "Stripe"),
            ("cod", "Cash on Delivery"),
        ],
    )
    payment_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("cod", "Cash on Delivery"),
            ("pay_at_pickup", "Pay at Pickup"),
        ],
    )
    amount_total = fields.Monetary(currency_field="currency_id")
    cod_amount = fields.Monetary(currency_field="currency_id")
    delivery_charge = fields.Monetary(currency_field="currency_id")
    provider_fee = fields.Monetary(currency_field="currency_id")
    net_receivable = fields.Monetary(currency_field="currency_id")
