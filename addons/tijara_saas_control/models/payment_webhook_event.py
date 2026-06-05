import hashlib
import hmac
import json
import os
import time

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
    provider_fee_amount = fields.Monetary(currency_field="currency_id")
    net_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_net_amount",
        store=True,
    )
    payment_event_type = fields.Selection(
        [
            ("payment", "Payment"),
            ("settlement", "Settlement"),
            ("refund", "Refund"),
            ("chargeback", "Chargeback"),
            ("unknown", "Unknown"),
        ],
        default="payment",
        required=True,
    )
    provider_event_type = fields.Char()
    refund_reference = fields.Char()
    chargeback_reference = fields.Char()
    chargeback_reason = fields.Char()
    dispute_case_id = fields.Many2one("tijara.saas.payment.dispute")
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
    signature_algorithm = fields.Char()
    signature_status = fields.Selection(
        [
            ("unchecked", "Unchecked"),
            ("valid", "Valid"),
            ("invalid", "Invalid"),
        ],
        default="unchecked",
        required=True,
    )
    signature_checked_at = fields.Datetime()
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
    provider_audit_hash = fields.Char(copy=False, index=True)
    reconciliation_note = fields.Text()
    error_message = fields.Text()
    received_at = fields.Datetime(default=fields.Datetime.now)
    processed_at = fields.Datetime()

    @api.depends("amount", "provider_fee_amount")
    def _compute_net_amount(self):
        for event in self:
            event.net_amount = (event.amount or 0.0) - (event.provider_fee_amount or 0.0)

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
        if normalized in {"refunded", "reversed", "refund"}:
            return "refunded"
        if normalized in {"chargeback", "charged_back", "dispute", "disputed"}:
            return "failed"
        return "unknown"

    @api.model
    def _payload_float(self, value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @api.model
    def _payload_amount(self, provider, payload, provider_payload):
        if payload.get("amount") is not None:
            return self._payload_float(payload.get("amount"))
        if payload.get("amount_total") is not None:
            return self._payload_float(payload.get("amount_total"))
        if provider == "stripe":
            value = (
                provider_payload.get("amount_paid")
                or provider_payload.get("amount_received")
                or provider_payload.get("amount_total")
                or provider_payload.get("amount")
                or 0
            )
            return self._payload_float(value) / 100.0
        value = (
            provider_payload.get("pp_Amount")
            or provider_payload.get("amount")
            or provider_payload.get("Amount")
            or 0
        )
        return self._payload_float(value)

    @api.model
    def _payload_fee_amount(self, provider, payload, provider_payload):
        if payload.get("provider_fee_amount") is not None:
            return self._payload_float(payload.get("provider_fee_amount"))
        if provider == "stripe":
            value = (
                provider_payload.get("application_fee_amount")
                or provider_payload.get("fee")
                or payload.get("fee")
                or 0
            )
            return self._payload_float(value) / 100.0
        value = (
            provider_payload.get("pp_FeeAmount")
            or provider_payload.get("feeAmount")
            or provider_payload.get("fee")
            or 0
        )
        return self._payload_float(value)

    @api.model
    def _provider_payload(self, provider, payload):
        provider = provider or "other"
        if provider == "stripe":
            event_type = payload.get("type") or payload.get("status")
            obj = (payload.get("data") or {}).get("object") or payload
            metadata = obj.get("metadata") or {}
            status = obj.get("payment_status") or obj.get("status") or event_type
            payment_event_type = "payment"
            if event_type in {"invoice.payment_succeeded", "checkout.session.completed"}:
                status = "paid"
            if event_type in {"invoice.payment_failed", "payment_intent.payment_failed"}:
                status = "failed"
            if event_type in {"charge.refunded", "refund.created"}:
                status = "refunded"
                payment_event_type = "refund"
            if event_type in {"charge.dispute.created", "charge.dispute.closed"}:
                status = "chargeback"
                payment_event_type = "chargeback"
            if event_type in {"payout.paid", "payout.failed"}:
                payment_event_type = "settlement"
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
                "fee_amount": self._payload_fee_amount(provider, payload, obj),
                "settlement_batch": obj.get("balance_transaction") or "",
                "payment_event_type": payment_event_type,
                "provider_event_type": event_type,
                "refund_reference": obj.get("refund") or obj.get("id") if payment_event_type == "refund" else "",
                "chargeback_reference": obj.get("id") if payment_event_type == "chargeback" else "",
                "chargeback_reason": obj.get("reason") or obj.get("evidence_details", {}).get("due_by") or "",
            }
        if provider == "jazzcash":
            response_code = str(payload.get("pp_ResponseCode") or payload.get("response_code") or "")
            status = "paid" if response_code == "000" else payload.get("status")
            event_type = str(payload.get("event_type") or payload.get("pp_TxnType") or "").lower()
            payment_event_type = "payment"
            if "refund" in event_type or "reversal" in event_type:
                payment_event_type = "refund"
                status = "refunded"
            if "chargeback" in event_type or "dispute" in event_type:
                payment_event_type = "chargeback"
                status = "chargeback"
            if "settlement" in event_type:
                payment_event_type = "settlement"
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
                "fee_amount": self._payload_fee_amount(provider, payload, payload),
                "settlement_batch": payload.get("pp_SettlementExpiry") or "",
                "payment_event_type": payment_event_type,
                "provider_event_type": event_type or response_code,
                "refund_reference": payload.get("refund_reference") or payload.get("pp_RefundRefNo") or "",
                "chargeback_reference": payload.get("chargeback_reference") or "",
                "chargeback_reason": payload.get("chargeback_reason") or "",
            }
        if provider == "easypaisa":
            status = (
                payload.get("transactionStatus")
                or payload.get("status")
                or payload.get("payment_status")
            )
            event_type = str(payload.get("eventType") or payload.get("event_type") or "").lower()
            payment_event_type = "payment"
            if "refund" in event_type or "reversal" in event_type:
                payment_event_type = "refund"
                status = "refunded"
            if "chargeback" in event_type or "dispute" in event_type:
                payment_event_type = "chargeback"
                status = "chargeback"
            if "settlement" in event_type:
                payment_event_type = "settlement"
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
                "fee_amount": self._payload_fee_amount(provider, payload, payload),
                "settlement_batch": payload.get("settlementBatch") or "",
                "payment_event_type": payment_event_type,
                "provider_event_type": event_type or status,
                "refund_reference": payload.get("refundReference") or payload.get("refund_reference") or "",
                "chargeback_reference": payload.get("chargebackReference")
                or payload.get("chargeback_reference")
                or "",
                "chargeback_reason": payload.get("chargebackReason")
                or payload.get("chargeback_reason")
                or "",
            }
        payment_event_type = payload.get("payment_event_type") or payload.get("event_type") or "payment"
        if payment_event_type not in {"payment", "settlement", "refund", "chargeback"}:
            payment_event_type = "unknown"
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
            "fee_amount": self._payload_fee_amount(provider, payload, payload),
            "settlement_batch": payload.get("settlement_batch") or "",
            "payment_event_type": payment_event_type,
            "provider_event_type": payload.get("provider_event_type") or payload.get("event_type"),
            "refund_reference": payload.get("refund_reference") or "",
            "chargeback_reference": payload.get("chargeback_reference") or "",
            "chargeback_reason": payload.get("chargeback_reason") or "",
        }

    @api.model
    def _audit_hash(self, provider, payload, event_reference):
        raw = json.dumps(
            {
                "provider": provider,
                "event_reference": event_reference or "",
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @api.model
    def tijara_from_payload(
        self,
        provider,
        payload,
        signature=False,
        signature_status="unchecked",
        signature_algorithm=False,
    ):
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
                "provider_fee_amount": provider_values.get("fee_amount") or 0.0,
                "payment_event_type": provider_values.get("payment_event_type") or "payment",
                "provider_event_type": provider_values.get("provider_event_type") or "",
                "refund_reference": provider_values.get("refund_reference") or "",
                "chargeback_reference": provider_values.get("chargeback_reference") or "",
                "chargeback_reason": provider_values.get("chargeback_reason") or "",
                "payment_status": self._normalize_payment_status(provider_values.get("status")),
                "raw_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                "signature": signature or "",
                "signature_status": signature_status,
                "signature_algorithm": signature_algorithm or "",
                "signature_checked_at": fields.Datetime.now()
                if signature_status in ("valid", "invalid")
                else False,
                "provider_audit_hash": self._audit_hash(provider, payload, event_reference),
            }
        )
        if event.signature_status == "invalid":
            event.write(
                {
                    "status": "failed",
                    "reconciliation_status": "mismatch",
                    "processed_at": fields.Datetime.now(),
                    "error_message": _("Provider signature verification failed."),
                }
            )
            return event
        event.action_apply()
        return event

    @api.model
    def _header_value(self, headers, name):
        headers = headers or {}
        lowered = {str(key).lower(): value for key, value in headers.items()}
        return lowered.get(name.lower()) or ""

    @api.model
    def _config_or_env(self, param_name, env_name):
        return (
            self.env["ir.config_parameter"].sudo().get_param(param_name)
            or os.environ.get(env_name)
            or ""
        )

    @api.model
    def _strip_signature_prefix(self, signature):
        signature = str(signature or "").strip()
        if signature.startswith("sha256="):
            return signature.split("=", 1)[1]
        return signature

    @api.model
    def _verify_digest(self, expected, supplied):
        return hmac.compare_digest(
            str(expected or "").strip().lower(),
            self._strip_signature_prefix(supplied).strip().lower(),
        )

    @api.model
    def _jazzcash_signature_candidates(self, payload, secret):
        filtered = {
            key: value
            for key, value in (payload or {}).items()
            if key not in {"pp_SecureHash", "secure_hash", "signature"} and value not in (None, "")
        }
        values = [str(filtered[key]) for key in sorted(filtered)]
        plain_string = "&".join([secret] + values)
        hmac_string = "&".join(values)
        return {
            hashlib.sha256(plain_string.encode("utf-8")).hexdigest().upper(),
            hmac.new(secret.encode("utf-8"), hmac_string.encode("utf-8"), hashlib.sha256)
            .hexdigest()
            .upper(),
        }

    @api.model
    def _sorted_payload_hmac(self, payload, secret, excluded_keys):
        filtered = {
            key: value
            for key, value in (payload or {}).items()
            if key not in excluded_keys and value not in (None, "")
        }
        message = "&".join("%s=%s" % (key, filtered[key]) for key in sorted(filtered))
        return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    @api.model
    def tijara_verify_provider_signature(self, provider, payload, raw_body="", headers=None):
        provider = provider or "other"
        headers = headers or {}
        raw_body = raw_body or json.dumps(
            payload or {},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if provider == "stripe":
            secret = self._config_or_env(
                "tijara.saas.stripe_webhook_secret",
                "TIJARA_STRIPE_WEBHOOK_SECRET",
            )
            supplied = self._header_value(headers, "Stripe-Signature")
            if not secret or not supplied:
                return {
                    "signature": supplied,
                    "signature_status": "unchecked",
                    "signature_algorithm": "stripe-hmac-sha256",
                }
            parts = {}
            for chunk in supplied.split(","):
                if "=" in chunk:
                    key, value = chunk.split("=", 1)
                    parts.setdefault(key.strip(), []).append(value.strip())
            timestamp = (parts.get("t") or [""])[0]
            signed_payload = ("%s.%s" % (timestamp, raw_body)).encode("utf-8")
            expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            status = "valid" if any(self._verify_digest(expected, candidate) for candidate in parts.get("v1", [])) else "invalid"
            tolerance = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("tijara.saas.stripe_signature_tolerance_seconds", "300")
            )
            try:
                if status == "valid" and abs(time.time() - int(timestamp)) > tolerance:
                    status = "invalid"
            except (TypeError, ValueError):
                status = "invalid"
            return {
                "signature": supplied,
                "signature_status": status,
                "signature_algorithm": "stripe-hmac-sha256",
            }
        if provider == "jazzcash":
            secret = self._config_or_env(
                "tijara.saas.jazzcash_integrity_salt",
                "TIJARA_JAZZCASH_INTEGRITY_SALT",
            )
            supplied = (
                payload.get("pp_SecureHash")
                or payload.get("secure_hash")
                or self._header_value(headers, "X-JazzCash-Signature")
            )
            if not secret or not supplied:
                return {
                    "signature": supplied or "",
                    "signature_status": "unchecked",
                    "signature_algorithm": "jazzcash-secure-hash",
                }
            candidates = self._jazzcash_signature_candidates(payload, secret)
            return {
                "signature": supplied,
                "signature_status": "valid"
                if any(self._verify_digest(candidate, supplied) for candidate in candidates)
                else "invalid",
                "signature_algorithm": "jazzcash-secure-hash",
            }
        if provider == "easypaisa":
            secret = self._config_or_env(
                "tijara.saas.easypaisa_webhook_secret",
                "TIJARA_EASYPAISA_WEBHOOK_SECRET",
            )
            supplied = (
                payload.get("signature")
                or payload.get("secureHash")
                or self._header_value(headers, "X-Easypaisa-Signature")
            )
            if not secret or not supplied:
                return {
                    "signature": supplied or "",
                    "signature_status": "unchecked",
                    "signature_algorithm": "easypaisa-hmac-sha256",
                }
            raw_expected = hmac.new(
                secret.encode("utf-8"),
                raw_body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            sorted_expected = self._sorted_payload_hmac(
                payload,
                secret,
                {"signature", "secureHash"},
            )
            return {
                "signature": supplied,
                "signature_status": "valid"
                if self._verify_digest(raw_expected, supplied)
                or self._verify_digest(sorted_expected, supplied)
                else "invalid",
                "signature_algorithm": "easypaisa-hmac-sha256",
            }
        secret = self._config_or_env(
            "tijara.saas.payment_webhook_secret",
            "TIJARA_PAYMENT_WEBHOOK_SECRET",
        )
        supplied = self._header_value(headers, "X-Tijara-Signature")
        if not secret or not supplied:
            return {
                "signature": supplied or "",
                "signature_status": "unchecked",
                "signature_algorithm": "generic-hmac-sha256",
            }
        expected = hmac.new(secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "signature": supplied,
            "signature_status": "valid" if self._verify_digest(expected, supplied) else "invalid",
            "signature_algorithm": "generic-hmac-sha256",
        }

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
                if event.signature_status == "invalid":
                    raise UserError(_("Provider signature verification failed."))
                if event.payment_event_type == "settlement":
                    event.write(
                        {
                            "status": "applied",
                            "reconciliation_status": "pending",
                            "processed_at": fields.Datetime.now(),
                            "reconciliation_note": _(
                                "Settlement batch received without a matched subscription; reconcile against the PSP settlement report."
                            ),
                            "error_message": False,
                        }
                    )
                    continue
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
                elif event.payment_event_type == "chargeback":
                    values.update(
                        {
                            "payment_status": "failed",
                            "state": "past_due",
                            "suspension_reason": _(
                                "Provider chargeback received: %s"
                            )
                            % (event.chargeback_reason or event.chargeback_reference or event.name),
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
                if event.payment_event_type in ("refund", "chargeback"):
                    event._ensure_dispute_case(subscription)
                event.write(
                    {
                        "subscription_id": subscription.id,
                        "status": "applied",
                        "reconciliation_status": "matched",
                        "reconciled_at": fields.Datetime.now(),
                        "processed_at": fields.Datetime.now(),
                        "reconciliation_note": _("Matched to subscription %s.") % subscription.name,
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

    def _ensure_dispute_case(self, subscription=False):
        self.ensure_one()
        if self.payment_event_type not in ("refund", "chargeback"):
            return self.env["tijara.saas.payment.dispute"]
        if self.dispute_case_id:
            return self.dispute_case_id
        dispute_model = self.env["tijara.saas.payment.dispute"].sudo()
        existing = dispute_model.search(
            [("webhook_event_id", "=", self.id)],
            limit=1,
        )
        if existing:
            self.dispute_case_id = existing.id
            return existing
        case = dispute_model.create(
            {
                "name": "New",
                "case_type": self.payment_event_type,
                "provider": self.provider,
                "company_id": self.company_id.id,
                "subscription_id": (subscription or self.subscription_id).id
                if (subscription or self.subscription_id)
                else False,
                "invoice_id": self.invoice_id.id if self.invoice_id else False,
                "webhook_event_id": self.id,
                "provider_reference": self.refund_reference
                or self.chargeback_reference
                or self.event_reference
                or self.transaction_id,
                "transaction_id": self.transaction_id,
                "amount": abs(self.amount or 0.0),
                "provider_fee_amount": abs(self.provider_fee_amount or 0.0),
                "reason": self.chargeback_reason or self.provider_event_type or self.reconciliation_note or "",
                "due_date": fields.Date.context_today(self),
            }
        )
        self.dispute_case_id = case.id
        case.action_open()
        return case

    def action_create_dispute_case(self):
        for event in self:
            event._ensure_dispute_case(event.subscription_id)

    def action_mark_reconciled(self):
        self.write(
            {
                "reconciliation_status": "reconciled",
                "reconciled_at": fields.Datetime.now(),
                "reconciliation_note": _("Manually reconciled by %s.") % self.env.user.display_name,
            }
        )

    def action_mark_mismatch(self):
        self.write(
            {
                "reconciliation_status": "mismatch",
                "reconciliation_note": _("Marked as reconciliation mismatch by %s.") % self.env.user.display_name,
            }
        )
