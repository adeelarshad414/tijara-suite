from odoo import _, api, fields, models


class TijaraEcommerceDeliveryException(models.Model):
    _name = "tijara.ecommerce.delivery.exception"
    _description = "Tijara Ecommerce Delivery Exception"
    _order = "severity desc, detected_at desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("New Delivery Exception"))
    provider_id = fields.Many2one(
        "tijara.ecommerce.delivery.provider",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sale_order_id = fields.Many2one("sale.order", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    category = fields.Selection(
        [
            ("sla_breach", "SLA Breach"),
            ("failed_delivery", "Failed Delivery"),
            ("webhook_error", "Webhook Error"),
            ("retry_exhausted", "Retry Exhausted"),
            ("manual_review", "Manual Review"),
        ],
        required=True,
        default="manual_review",
        index=True,
    )
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        required=True,
        default="warning",
        index=True,
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("acknowledged", "Acknowledged"),
            ("resolved", "Resolved"),
            ("ignored", "Ignored"),
        ],
        default="open",
        required=True,
        index=True,
    )
    detected_at = fields.Datetime(default=fields.Datetime.now, required=True)
    deadline_at = fields.Datetime()
    acknowledged_at = fields.Datetime()
    resolved_at = fields.Datetime()
    owner_id = fields.Many2one("res.users", string="Owner")
    last_event_id = fields.Many2one("tijara.ecommerce.delivery.event", readonly=True)
    retry_id = fields.Many2one("tijara.ecommerce.delivery.retry", readonly=True)
    message = fields.Text(required=True)
    resolution_notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env["sale.order"].browse(vals.get("sale_order_id")).exists()
            provider = self.env["tijara.ecommerce.delivery.provider"].browse(vals.get("provider_id")).exists()
            if order and not vals.get("company_id"):
                vals["company_id"] = order.company_id.id
            if order and provider and vals.get("name") in (False, _("New Delivery Exception"), None):
                vals["name"] = "%s/%s/%s" % (
                    provider.code,
                    vals.get("category") or "exception",
                    order.name or order.id,
                )
        return super().create(vals_list)

    def action_acknowledge(self):
        self.write(
            {
                "state": "acknowledged",
                "acknowledged_at": fields.Datetime.now(),
                "owner_id": self.env.user.id,
            }
        )
        return True

    def action_resolve(self):
        self.write(
            {
                "state": "resolved",
                "resolved_at": fields.Datetime.now(),
                "owner_id": self.env.user.id,
            }
        )
        self.mapped("sale_order_id").write({"tijara_delivery_sla_state": "resolved"})
        return True

    def action_ignore(self):
        self.write(
            {
                "state": "ignored",
                "resolved_at": fields.Datetime.now(),
                "owner_id": self.env.user.id,
            }
        )
        return True

    @api.model
    def create_for_order(
        self,
        provider,
        order,
        category="manual_review",
        message="",
        severity="warning",
        event=False,
        retry=False,
        deadline=False,
    ):
        if not provider or not order:
            return self.browse()
        existing = self.search(
            [
                ("provider_id", "=", provider.id),
                ("sale_order_id", "=", order.id),
                ("category", "=", category),
                ("state", "in", ["open", "acknowledged"]),
            ],
            limit=1,
        )
        values = {
            "severity": severity,
            "message": message or _("Delivery operation needs manual review."),
            "deadline_at": deadline or order.tijara_delivery_sla_deadline or False,
            "last_event_id": event.id if event else False,
            "retry_id": retry.id if retry else False,
        }
        if existing:
            existing.write({key: value for key, value in values.items() if value not in (False, "")})
            return existing
        values.update(
            {
                "provider_id": provider.id,
                "sale_order_id": order.id,
                "company_id": order.company_id.id,
                "category": category,
            }
        )
        exception = self.create(values)
        order.write(
            {
                "tijara_delivery_sla_state": "breached"
                if category == "sla_breach"
                else order.tijara_delivery_sla_state,
                "tijara_delivery_exception_reason": message or order.tijara_delivery_exception_reason,
            }
        )
        provider._delivery_event(
            order=order,
            event_type="exception",
            status="failed",
            payload={
                "category": category,
                "severity": severity,
                "deadline": fields.Datetime.to_string(deadline) if deadline else "",
            },
            response={"exception_id": exception.id},
            message=message,
            tracking_number=order.tijara_delivery_tracking_number or "",
            external_reference=order.tijara_delivery_provider_reference or "",
        )
        return exception

    @api.model
    def run_sla_monitor(self, batch_size=200):
        now = fields.Datetime.now()
        orders = self.env["sale.order"].sudo().search(
            [
                ("tijara_ecommerce_channel_id", "!=", False),
                ("tijara_fulfillment_method", "in", ["delivery", "courier"]),
                ("tijara_delivery_provider_id", "!=", False),
                ("tijara_delivery_sla_deadline", "!=", False),
                ("tijara_delivery_sla_deadline", "<", now),
                ("tijara_delivery_status", "not in", ["delivered", "cancelled", "not_required"]),
            ],
            limit=max(int(batch_size or 200), 1),
        )
        created = self.browse()
        for order in orders:
            created |= self.create_for_order(
                order.tijara_delivery_provider_id,
                order,
                category="sla_breach",
                severity="critical",
                message=_("Delivery SLA breached for order %s.") % order.name,
                deadline=order.tijara_delivery_sla_deadline,
            )
        return len(created)
