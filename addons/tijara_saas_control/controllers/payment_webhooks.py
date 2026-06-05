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

    def _payload(self, body):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise UserError("Invalid payment webhook JSON.") from error
        if not isinstance(payload, dict):
            raise UserError("Payment webhook payload must be a JSON object.")
        return payload

    def _require_native_signature(self):
        value = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("tijara.saas.payment_require_native_signatures")
            or os.environ.get("TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES")
            or ""
        )
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

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
        raw_body = request.httprequest.get_data(as_text=True) or "{}"
        event_model = request.env["tijara.saas.payment.webhook.event"].sudo()
        try:
            payload = self._payload(raw_body)
            verification = event_model.tijara_verify_provider_signature(
                provider,
                payload,
                raw_body=raw_body,
                headers=dict(request.httprequest.headers),
            )
            if verification["signature_status"] == "invalid" or (
                self._require_native_signature()
                and verification["signature_status"] != "valid"
            ):
                return self._json_response(
                    {
                        "status": "forbidden",
                        "message": "Provider signature verification failed.",
                    },
                    status=403,
                )
            event = (
                event_model.tijara_from_payload(
                    provider,
                    payload,
                    signature=verification["signature"],
                    signature_status=verification["signature_status"],
                    signature_algorithm=verification["signature_algorithm"],
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
