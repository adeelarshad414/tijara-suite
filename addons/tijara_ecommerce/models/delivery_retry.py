import hashlib
import json
from datetime import timedelta

from odoo import _, api, fields, models


class TijaraEcommerceDeliveryRetry(models.Model):
    _name = "tijara.ecommerce.delivery.retry"
    _description = "Tijara Ecommerce Delivery Retry Queue"
    _order = "priority desc, next_attempt_at, create_date"

    name = fields.Char(required=True, default=lambda self: _("New Delivery Retry"))
    provider_id = fields.Many2one(
        "tijara.ecommerce.delivery.provider",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sale_order_id = fields.Many2one("sale.order", index=True, ondelete="set null")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    operation = fields.Selection(
        [
            ("shipment_create", "Create Shipment"),
            ("shipment_cancel", "Cancel Shipment"),
            ("label", "Generate Label"),
            ("manifest", "Create Manifest"),
            ("status_update", "Status Update"),
        ],
        required=True,
        default="shipment_create",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    priority = fields.Integer(default=10)
    attempt_count = fields.Integer(default=0)
    max_attempts = fields.Integer(default=5)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, index=True)
    last_attempt_at = fields.Datetime()
    last_event_id = fields.Many2one("tijara.ecommerce.delivery.event", readonly=True)
    endpoint_snapshot = fields.Char()
    api_base_url_snapshot = fields.Char()
    payload_json = fields.Text()
    last_response_json = fields.Text()
    payload_hash = fields.Char(index=True)
    error_message = fields.Text()
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            provider = self.env["tijara.ecommerce.delivery.provider"].browse(vals.get("provider_id")).exists()
            if provider and not vals.get("company_id"):
                vals["company_id"] = provider.company_id.id
            if provider and vals.get("name") in (False, _("New Delivery Retry"), None):
                vals["name"] = "%s/%s/%s" % (
                    provider.code,
                    vals.get("operation") or "delivery",
                    fields.Datetime.now(),
                )
        records = super().create(vals_list)
        records._write_payload_hash()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "payload_json" in vals:
            self._write_payload_hash()
        return result

    def _write_payload_hash(self):
        for retry in self:
            payload = retry.payload_json or ""
            retry.payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _payload_dict(self):
        self.ensure_one()
        try:
            payload = json.loads(self.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {"raw": self.payload_json or ""}
        return payload if isinstance(payload, dict) else {"payload": payload}

    def _backoff_delta(self, next_attempt_count):
        self.ensure_one()
        provider = self.provider_id
        base_minutes = max(provider.retry_initial_delay_minutes or 5, 1)
        multiplier = max(provider.retry_backoff_multiplier or 2.0, 1.0)
        minutes = min(base_minutes * (multiplier ** max(next_attempt_count - 1, 0)), 1440)
        return timedelta(minutes=minutes)

    def _json_dump(self, payload):
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)

    def _mark_failed(self, error_message):
        self.ensure_one()
        next_attempt_count = self.attempt_count + 1
        exhausted = next_attempt_count >= max(self.max_attempts or 1, 1)
        values = {
            "attempt_count": next_attempt_count,
            "last_attempt_at": fields.Datetime.now(),
            "state": "failed" if exhausted else "pending",
            "error_message": error_message or "",
        }
        if not exhausted:
            values["next_attempt_at"] = fields.Datetime.now() + self._backoff_delta(next_attempt_count)
        self.write(values)
        if exhausted:
            self.provider_id._raise_delivery_exception(
                self.sale_order_id,
                category="retry_exhausted",
                message=error_message or _("Delivery retry queue exhausted."),
                severity="critical",
                retry=self,
                event=self.last_event_id,
            )

    def _run_attempt(self):
        self.ensure_one()
        if self.state == "cancelled":
            return False
        self.write({"state": "running", "last_attempt_at": fields.Datetime.now()})
        try:
            payload = self._payload_dict()
            response = self.provider_id._assumed_http_adapter_response(
                self.operation,
                payload,
                order=self.sale_order_id,
            )
            event = self.provider_id._delivery_event(
                order=self.sale_order_id,
                event_type=self.operation,
                status="processed",
                payload=payload,
                response=response,
                external_reference=response.get("external_reference") or "",
                tracking_number=response.get("tracking_number") or "",
                manifest_reference=response.get("manifest_reference") or "",
                message=_("Retry queue processed by assumed HTTP JSON adapter."),
            )
            self.write(
                {
                    "state": "done",
                    "attempt_count": self.attempt_count + 1,
                    "last_attempt_at": fields.Datetime.now(),
                    "last_event_id": event.id,
                    "last_response_json": self._json_dump(response),
                    "error_message": "",
                }
            )
            return True
        except Exception as error:
            self._mark_failed(str(error))
            return False

    def action_run_now(self):
        for retry in self:
            retry.write({"next_attempt_at": fields.Datetime.now()})
            retry._run_attempt()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Delivery Retry Queue"),
                "message": _("Selected delivery retry item(s) processed."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_reset(self):
        self.write(
            {
                "state": "pending",
                "attempt_count": 0,
                "next_attempt_at": fields.Datetime.now(),
                "error_message": "",
            }
        )
        return True

    @api.model
    def run_due_retries(self, batch_size=50):
        now = fields.Datetime.now()
        due_retries = self.search(
            [
                ("state", "in", ["pending", "failed"]),
                ("next_attempt_at", "<=", now),
            ],
            order="priority desc, next_attempt_at, create_date",
            limit=max(int(batch_size or 50), 1),
        )
        processed = 0
        for retry in due_retries:
            if retry.attempt_count >= max(retry.max_attempts or 1, 1):
                retry._mark_failed(retry.error_message or _("Delivery retry queue exhausted."))
                continue
            if retry._run_attempt():
                processed += 1
        return processed
