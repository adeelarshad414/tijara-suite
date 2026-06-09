import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TijaraEcommerceDeliveryProvider(models.Model):
    _name = "tijara.ecommerce.delivery.provider"
    _description = "Tijara Ecommerce Delivery Provider"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    provider_type = fields.Selection(
        [
            ("in_house", "In House Fleet"),
            ("courier", "Courier"),
            ("aggregator", "Aggregator"),
            ("third_party", "Third Party"),
            ("dummy", "Dummy / Assumption Mode"),
        ],
        default="in_house",
        required=True,
    )
    service_level = fields.Selection(
        [
            ("standard", "Standard"),
            ("same_day", "Same Day"),
            ("express", "Express"),
            ("scheduled", "Scheduled"),
        ],
        default="standard",
        required=True,
    )
    dry_run = fields.Boolean(
        default=True,
        help="Keep enabled until a real courier/provider integration is certified.",
    )
    auto_assign = fields.Boolean(default=True)
    supports_delivery = fields.Boolean(default=True)
    supports_courier = fields.Boolean(default=True)
    supports_cod = fields.Boolean(default=True)
    api_base_url = fields.Char()
    tracking_url_template = fields.Char(
        help="Optional URL template. Use {tracking_number} where the provider tracking number should appear.",
    )
    contact_phone = fields.Char()
    webhook_secret_ref = fields.Char(
        help="Secret-manager reference only. Do not store raw courier webhook secrets here.",
    )
    shipment_count = fields.Integer(compute="_compute_shipment_count")
    notes = fields.Text()

    @api.depends("company_id")
    def _compute_shipment_count(self):
        order_model = self.env["sale.order"].sudo()
        for provider in self:
            provider.shipment_count = order_model.search_count(
                [("tijara_delivery_provider_id", "=", provider.id)]
            )

    @api.constrains("code", "company_id")
    def _check_unique_code(self):
        for provider in self:
            domain = [
                ("id", "!=", provider.id),
                ("company_id", "=", provider.company_id.id),
                ("code", "=", provider.code),
            ]
            if provider.code and self.search_count(domain):
                raise ValidationError(_("Delivery provider code must be unique per company."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["code"] = self._normalize_code(vals.get("code") or vals.get("name"))
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals:
            vals = dict(vals, code=self._normalize_code(vals.get("code")))
        return super().write(vals)

    @api.model
    def _normalize_code(self, value):
        value = re.sub(r"[^A-Za-z0-9]+", "-", value or "").strip("-").upper()
        return value or "DELIVERY"

    def _tracking_number_for_order(self, order):
        self.ensure_one()
        raw_order = re.sub(r"[^A-Za-z0-9]+", "", order.name or str(order.id))[-10:]
        raw_order = raw_order or str(order.id)
        return "%s-%s" % (self.code, raw_order)

    def _tracking_url_for_number(self, tracking_number):
        self.ensure_one()
        template = self.tracking_url_template or ""
        if not template:
            return ""
        return template.replace("{tracking_number}", tracking_number or "")

    def action_open_shipments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Provider Shipments"),
            "res_model": "sale.order",
            "view_mode": "list,form,pivot,graph",
            "domain": [("tijara_delivery_provider_id", "=", self.id)],
            "context": {"search_default_tijara_ecommerce": 1},
        }

    def action_test_provider(self):
        self.ensure_one()
        message = _("Dry-run provider is ready for assumed local certification.")
        if not self.dry_run:
            message = _("Provider is configured for live mode; complete courier certification before production.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Delivery Provider Check"),
                "message": message,
                "type": "success" if self.dry_run else "warning",
                "sticky": False,
            },
        }

    def tijara_prepare_shipment(self, order):
        self.ensure_one()
        tracking_number = order.tijara_delivery_tracking_number or self._tracking_number_for_order(order)
        tracking_url = order.tijara_delivery_tracking_url or self._tracking_url_for_number(tracking_number)
        payload = {
            "provider": self.code,
            "provider_type": self.provider_type,
            "service_level": self.service_level,
            "dry_run": self.dry_run,
            "order_id": order.id,
            "order_name": order.name,
            "fulfillment_method": order.tijara_fulfillment_method,
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
        }
        order.write(
            {
                "tijara_delivery_provider_id": self.id,
                "tijara_delivery_status": "assigned",
                "tijara_delivery_tracking_number": tracking_number,
                "tijara_delivery_tracking_url": tracking_url,
                "tijara_delivery_provider_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                "tijara_last_tracking_at": fields.Datetime.now(),
            }
        )
        return payload
