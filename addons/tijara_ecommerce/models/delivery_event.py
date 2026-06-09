import hashlib
import json

from odoo import fields, models


class TijaraEcommerceDeliveryEvent(models.Model):
    _name = "tijara.ecommerce.delivery.event"
    _description = "Tijara Ecommerce Delivery Adapter Event"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    provider_id = fields.Many2one("tijara.ecommerce.delivery.provider", required=True, ondelete="cascade")
    sale_order_id = fields.Many2one("sale.order", string="Online Order", ondelete="set null")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    direction = fields.Selection(
        [("outbound", "Outbound"), ("inbound", "Inbound")],
        required=True,
        default="outbound",
    )
    event_type = fields.Selection(
        [
            ("shipment_create", "Shipment Create"),
            ("shipment_cancel", "Shipment Cancel"),
            ("label", "Label"),
            ("manifest", "Manifest"),
            ("webhook", "Webhook"),
            ("status_update", "Status Update"),
            ("exception", "Exception"),
        ],
        required=True,
        default="shipment_create",
    )
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("processed", "Processed"),
            ("failed", "Failed"),
            ("ignored", "Ignored"),
        ],
        required=True,
        default="queued",
    )
    signature_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("valid", "Valid"),
            ("missing", "Missing"),
            ("invalid", "Invalid"),
        ],
        default="not_required",
    )
    external_reference = fields.Char(copy=False)
    tracking_number = fields.Char(copy=False)
    manifest_reference = fields.Char(copy=False)
    payload_json = fields.Text(string="Payload JSON", copy=False)
    response_json = fields.Text(string="Response JSON", copy=False)
    message = fields.Text(copy=False)
    payload_hash = fields.Char(copy=False)

    def write_payload_hash(self):
        for event in self:
            raw = (event.payload_json or "") + "|" + (event.response_json or "")
            event.payload_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return True

    @classmethod
    def payload_to_json(cls, payload):
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
