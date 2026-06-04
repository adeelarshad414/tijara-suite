import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TijaraSaasPaymentWebhookEvent(models.Model):
    _name = "tijara.saas.payment.webhook.event"
    _description = "Tijara SaaS Payment Webhook Event"
    _order = "received_at desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    provider = fields.Selection(
        [
            ("manual", "Manual / Bank"),
            ("jazzcash", "JazzCash"),
            ("easypaisa", "Easypaisa"),
            ("stripe", "Stripe"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    event_reference = fields.Char()
    provider_reference = fields.Char()
    transaction_id = fields.Char()
    settlement_batch = fields.Char()
    subscription_id = fields.Many2one("tijara.saas.subscription")
    database_name = fields.Char()
    invoice_id = fields.Many2one("account.move")
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    amount = fields.Monetary(currency_field="currency_id")
    payment_status = fields.Selection(
        [
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("past_due", "Past Due"),
            ("refunded", "Refunded"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        required=True,
    )
    status = fields.Selection(
        [
            ("received", "Received"),
            ("applied", "Applied"),
            ("failed", "Failed"),
        ],
        default="received",
        required=True,
    )
    raw_payload = fields.Text()
    signature = fields.Char()
    signature_status = fields.Selection(
        [
            ("unchecked", "Unchecked"),
            ("valid", "Valid"),
            ("invalid", "Invalid"),
        ],
        default="unchecked",
        required=True,
    )
    reconciliation_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("matched", "Matched"),
            ("mismatch", "Mismatch"),
            ("reconciled", "Reconciled"),
        ],
        default="pending",
        required=True,
    )
    reconciled_at = fields.Datetime()
    error_message = fields.Text()
    received_at = fields.Datetime(default=fields.Datetime.now)
    processed_at = fields.Datetime()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for event in records:
            if event.name == "New":
                event.name = "PWH-%05d" % event.id
        return records

    @api.model
    def _normalize_payment_status(self, value):
        normalized = str(value or "").strip().lower()
        if normalized in {"paid", "succeeded", "success", "completed", "captured"}:
            return "paid"
        if normalized in {"failed", "failure", "declined", "cancelled", "canceled"}:
            return "failed"
        if normalized in {"past_due", "overdue", "expired"}:
            return "past_due"
        if normalized in {"refunded", "reversed"}:
            return "refunded"
        return "unknown"

    @api.model
    def _payload_amount(self, provider, payload, provider_payload):
        if payload.get("amount") is not None:
            return float(payload.get("amount") or 0.0)
        if payload.get("amount_total") is not None:
            return float(payload.get("amount_total") or 0.0)
        if provider == "stripe":
            value = (
                provider_payload.get("amount_paid")
                or provider_payload.get("amount_received")
                or provider_payload.get("amount_total")
                or provider_payload.get("amount")
                or 0
            )
            return float(value or 0.0) / 100.0
        value = (
            provider_payload.get("pp_Amount")
            or provider_payload.get("amount")
            or provider_payload.get("Amount")
            or 0
        )
        return float(value or 0.0)

    @api.model
    def _provider_payload(self, provider, payload):
        provider = provider or "other"
        if provider == "stripe":
            event_type = payload.get("type") or payload.get("status")
            obj = (payload.get("data") or {}).get("object") or payload
            metadata = obj.get("metadata") or {}
            status = obj.get("payment_status") or obj.get("status") or event_type
            if event_type in {"invoice.payment_succeeded", "checkout.session.completed"}:
                status = "paid"
            if event_type in {"invoice.payment_failed", "payment_intent.payment_failed"}:
                status = "failed"
            if event_type in {"charge.refunded", "refund.created"}:
                status = "refunded"
            return {
                "event_reference": payload.get("id") or obj.get("id"),
                "provider_reference": obj.get("id"),
                "transaction_id": obj.get("payment_intent") or obj.get("charge") or obj.get("id"),
                "subscription_id": metadata.get("subscription_id") or payload.get("subscription_id"),
                "database_name": metadata.get("database_name") or payload.get("database_name"),
                "invoice_id": metadata.get("invoice_id") or payload.get("invoice_id"),
                "invoice_ref": metadata.get("invoice_ref") or payload.get("invoice_ref"),
                "external_payment_reference": metadata.get("external_payment_reference")
                or obj.get("client_reference_id")
                or payload.get("external_payment_reference"),
                "status": status,
                "amount": self._payload_amount(provider, payload, obj),
                "settlement_batch": obj.get("balance_transaction") or "",
            }
        if provider == "jazzcash":
            response_code = str(payload.get("pp_ResponseCode") or payload.get("response_code") or "")
            status = "paid" if response_code == "000" else payload.get("status")
            return {
                "event_reference": payload.get("event_reference")
                or payload.get("pp_TxnRefNo")
                or payload.get("transaction_id"),
                "provider_reference": payload.get("pp_TxnRefNo") or payload.get("reference"),
                "transaction_id": payload.get("pp_RetreivalReferenceNo")
                or payload.get("transaction_id")
                or payload.get("pp_TxnRefNo"),
                "database_name": payload.get("database_name") or payload.get("pp_BillReference"),
                "invoice_ref": payload.get("invoice_ref") or payload.get("pp_BillReference"),
                "external_payment_reference": payload.get("external_payment_reference")
                or payload.get("pp_TxnRefNo"),
                "status": status,
                "amount": self._payload_amount(provider, payload, payload),
                "settlement_batch": payload.get("pp_SettlementExpiry") or "",
            }
        if provider == "easypaisa":
            status = (
                payload.get("transactionStatus")
                or payload.get("status")
                or payload.get("payment_status")
            )
            return {
                "event_reference": payload.get("event_reference")
                or payload.get("transactionId")
                or payload.get("orderId"),
                "provider_reference": payload.get("orderId") or payload.get("reference"),
                "transaction_id": payload.get("transactionId") or payload.get("storeId"),
                "database_name": payload.get("database_name") or payload.get("accountNum"),
                "invoice_ref": payload.get("invoice_ref") or payload.get("orderId"),
                "external_payment_reference": payload.get("external_payment_reference")
                or payload.get("orderId"),
                "status": status,
                "amount": self._payload_amount(provider, payload, payload),
                "settlement_batch": payload.get("settlementBatch") or "",
            }
        return {
            "event_reference": payload.get("event_reference")
            or payload.get("event_id")
            or payload.get("id")
            or payload.get("transaction_id")
            or payload.get("reference"),
            "provider_reference": payload.get("provider_reference") or payload.get("reference"),
            "transaction_id": payload.get("transaction_id") or "",
            "database_name": payload.get("database_name") or "",
            "invoice_ref": payload.get("invoice_ref") or payload.get("invoice_name"),
            "external_payment_reference": payload.get("external_payment_reference")
            or payload.get("reference"),
            "status": payload.get("payment_status") or payload.get("status"),
            "amount": self._payload_amount(provider, payload, payload),
            "settlement_batch": payload.get("settlement_batch") or "",
        }

    @api.model
    def tijara_from_payload(self, provider, payload, signature=False, signature_status="unchecked"):
        if not isinstance(payload, dict):
            raise UserError(_("Payment webhook payload must be a JSON object."))
        provider_values = self._provider_payload(provider, payload)
        event_reference = provider_values.get("event_reference")
        if event_reference:
            existing = self.sudo().search(
                [
                    ("provider", "=", provider),
                    ("event_reference", "=", event_reference),
                ],
                limit=1,
            )
            if existing:
                return existing
        match_payload = dict(payload, **provider_values)
        subscription = self._match_subscription(match_payload)
        invoice = self._match_invoice(match_payload)
        company = subscription.company_id or invoice.company_id or self.env.company
        event = self.sudo().create(
            {
                "provider": provider,
                "event_reference": event_reference,
                "provider_reference": provider_values.get("provider_reference") or "",
                "transaction_id": provider_values.get("transaction_id") or "",
                "settlement_batch": provider_values.get("settlement_batch") or "",
                "subscription_id": subscription.id if subscription else False,
                "database_name": provider_values.get("database_name") or "",
                "invoice_id": invoice.id if invoice else False,
                "company_id": company.id,
                "amount": provider_values.get("amount") or 0.0,
                "payment_status": self._normalize_payment_status(provider_values.get("status")),
                "raw_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                "signature": signature or "",
                "signature_status": signature_status,
            }
        )
        event.action_apply()
        return event

    @api.model
    def _match_subscription(self, payload):
        subscription_model = self.env["tijara.saas.subscription"].sudo()
        subscription_id = int(payload.get("subscription_id") or 0)
        if subscription_id:
            subscription = subscription_model.browse(subscription_id).exists()
            if subscription:
                return subscription
        database_name = payload.get("database_name")
        if database_name:
            subscription = subscription_model.search(
                [("database_name", "=", database_name)],
                limit=1,
            )
            if subscription:
                return subscription
        reference = payload.get("external_payment_reference") or payload.get("reference")
        if reference:
            return subscription_model.search(
                [("external_payment_reference", "=", reference)],
                limit=1,
            )
        return subscription_model

    @api.model
    def _match_invoice(self, payload):
        invoice_id = int(payload.get("invoice_id") or 0)
        if invoice_id:
            return self.env["account.move"].sudo().browse(invoice_id).exists()
        invoice_ref = payload.get("invoice_ref") or payload.get("invoice_name")
        if invoice_ref:
            return self.env["account.move"].sudo().search(
                [
                    "|",
                    ("name", "=", invoice_ref),
                    ("ref", "=", invoice_ref),
                ],
                limit=1,
            )
        return self.env["account.move"]

    def action_apply(self):
        for event in self:
            try:
                subscription = event.subscription_id
                if not subscription and event.database_name:
                    subscription = self.env["tijara.saas.subscription"].sudo().search(
                        [("database_name", "=", event.database_name)],
                        limit=1,
                    )
                if not subscription and event.invoice_id.tijara_saas_subscription_id:
                    subscription = event.invoice_id.tijara_saas_subscription_id
                if not subscription:
                    raise UserError(_("No subscription matched this payment webhook."))
                values = {
                    "payment_provider": event.provider,
                    "external_payment_reference": event.event_reference
                    or subscription.external_payment_reference,
                }
                if event.payment_status == "paid":
                    values.update(
                        {
                            "payment_status": "paid",
                            "state": "active",
                            "paid_at": fields.Datetime.now(),
                            "dunning_level": 0,
                            "grace_until": False,
                            "suspension_reason": False,
                        }
                    )
                elif event.payment_status == "failed":
                    values.update({"payment_status": "failed"})
                    if subscription.state == "active":
                        values["state"] = "past_due"
                elif event.payment_status == "past_due":
                    values.update({"payment_status": "past_due"})
                    if subscription.state == "active":
                        values["state"] = "past_due"
                elif event.payment_status == "refunded":
                    values.update({"payment_status": "failed", "state": "past_due"})
                else:
                    raise UserError(_("Unsupported or unknown payment webhook status."))
                subscription.write(values)
                event.write(
                    {
                        "subscription_id": subscription.id,
                        "status": "applied",
                        "reconciliation_status": "matched",
                        "reconciled_at": fields.Datetime.now(),
                        "processed_at": fields.Datetime.now(),
                        "error_message": False,
                    }
                )
            except UserError as error:
                event.write(
                    {
                        "status": "failed",
                        "reconciliation_status": "mismatch",
                        "processed_at": fields.Datetime.now(),
                        "error_message": str(error),
                    }
                )
