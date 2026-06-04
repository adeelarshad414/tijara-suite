import hmac
import json
import os

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class TijaraSaasPaymentWebhookController(http.Controller):
    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            headers=[("Content-Type", "application/json; charset=utf-8")],
            status=status,
        )

    def _webhook_secret(self):
        return (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("tijara.saas.payment_webhook_secret")
            or os.environ.get("TIJARA_PAYMENT_WEBHOOK_SECRET")
            or ""
        )

    def _payload(self):
        body = request.httprequest.get_data(as_text=True) or "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise UserError("Invalid payment webhook JSON.") from error
        if not isinstance(payload, dict):
            raise UserError("Payment webhook payload must be a JSON object.")
        return payload

    @http.route(
        "/tijara/saas/payment/webhook/<string:provider>",
        type="http",
        methods=["POST"],
        auth="public",
        csrf=False,
    )
    def payment_webhook(self, provider, **kwargs):
        secret = self._webhook_secret()
        provided = request.httprequest.headers.get("X-Tijara-Webhook-Secret", "")
        if not secret or not hmac.compare_digest(secret, provided):
            return self._json_response({"status": "forbidden"}, status=403)
        signature = request.httprequest.headers.get("X-Tijara-Signature", "")
        try:
            event = (
                request.env["tijara.saas.payment.webhook.event"]
                .sudo()
                .tijara_from_payload(
                    provider,
                    self._payload(),
                    signature=signature,
                    signature_status="valid",
                )
            )
        except UserError as error:
            return self._json_response({"status": "error", "message": str(error)}, status=400)
        return self._json_response(
            {
                "status": event.status,
                "event_id": event.id,
                "subscription_id": event.subscription_id.id or False,
            }
        )
