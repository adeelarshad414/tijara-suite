import json
import os

from odoo import _, api, models


PROVIDER_CONTRACTS = {
    "manual": {
        "label": "Manual / Bank",
        "webhook_route": "/tijara/saas/payment/webhook/manual",
        "signature_algorithm": "generic-hmac-sha256",
        "signature_required": False,
        "secret_param": "tijara.saas.payment_webhook_secret",
        "secret_env": "TIJARA_PAYMENT_WEBHOOK_SECRET",
        "settlement_parser_profile": "manual_bank_v1",
        "event_types": ["payment", "settlement", "refund", "chargeback"],
        "refund_fields": ["refund_reference", "amount", "external_payment_reference"],
        "chargeback_fields": ["chargeback_reference", "chargeback_reason", "amount"],
        "settlement_fields": ["reference", "amount", "fee", "net", "settlement_date"],
        "certification_required": False,
    },
    "jazzcash": {
        "label": "JazzCash",
        "webhook_route": "/tijara/saas/payment/webhook/jazzcash",
        "signature_algorithm": "jazzcash-secure-hash",
        "signature_required": True,
        "secret_param": "tijara.saas.jazzcash_integrity_salt",
        "secret_env": "TIJARA_JAZZCASH_INTEGRITY_SALT",
        "settlement_parser_profile": "jazzcash_merchant_v1",
        "event_types": ["payment", "settlement", "refund", "chargeback"],
        "refund_fields": ["pp_RefundRefNo", "pp_TxnRefNo", "pp_Amount"],
        "chargeback_fields": ["chargeback_reference", "chargeback_reason", "pp_TxnRefNo"],
        "settlement_fields": ["pp_TxnRefNo", "pp_Amount", "pp_FeeAmount", "pp_TxnDateTime"],
        "certification_required": True,
    },
    "easypaisa": {
        "label": "Easypaisa",
        "webhook_route": "/tijara/saas/payment/webhook/easypaisa",
        "signature_algorithm": "easypaisa-hmac-sha256",
        "signature_required": True,
        "secret_param": "tijara.saas.easypaisa_webhook_secret",
        "secret_env": "TIJARA_EASYPAISA_WEBHOOK_SECRET",
        "settlement_parser_profile": "easypaisa_merchant_v1",
        "event_types": ["payment", "settlement", "refund", "chargeback"],
        "refund_fields": ["refundReference", "transactionId", "amount"],
        "chargeback_fields": ["chargebackReference", "chargebackReason", "transactionId"],
        "settlement_fields": ["transactionId", "orderId", "amount", "fee", "settlementBatch"],
        "certification_required": True,
    },
    "stripe": {
        "label": "Stripe",
        "webhook_route": "/tijara/saas/payment/webhook/stripe",
        "signature_algorithm": "stripe-hmac-sha256",
        "signature_required": True,
        "secret_param": "tijara.saas.stripe_webhook_secret",
        "secret_env": "TIJARA_STRIPE_WEBHOOK_SECRET",
        "settlement_parser_profile": "stripe_balance_v1",
        "event_types": ["payment", "settlement", "refund", "chargeback"],
        "refund_fields": ["refund", "id", "amount"],
        "chargeback_fields": ["id", "reason", "evidence_details"],
        "settlement_fields": ["balance_transaction", "amount", "fee", "net", "available_on"],
        "certification_required": True,
    },
    "other": {
        "label": "Other PSP",
        "webhook_route": "/tijara/saas/payment/webhook/other",
        "signature_algorithm": "generic-hmac-sha256",
        "signature_required": True,
        "secret_param": "tijara.saas.payment_webhook_secret",
        "secret_env": "TIJARA_PAYMENT_WEBHOOK_SECRET",
        "settlement_parser_profile": "auto",
        "event_types": ["payment", "settlement", "refund", "chargeback"],
        "refund_fields": ["refund_reference", "transaction_id", "amount"],
        "chargeback_fields": ["chargeback_reference", "chargeback_reason", "transaction_id"],
        "settlement_fields": ["event_reference", "amount", "fee", "net", "settlement_date"],
        "certification_required": True,
    },
}


class TijaraSaasPaymentProviderAdapter(models.AbstractModel):
    _name = "tijara.saas.payment.provider.adapter"
    _description = "Tijara SaaS Payment Provider Adapter"

    @api.model
    def _truthy(self, value):
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    @api.model
    def _config_or_env_present(self, param_name, env_name):
        value = (
            self.env["ir.config_parameter"].sudo().get_param(param_name)
            or os.environ.get(env_name)
            or ""
        )
        return bool(str(value).strip())

    @api.model
    def _provider_key(self, provider):
        provider = provider or "other"
        return provider if provider in PROVIDER_CONTRACTS else "other"

    @api.model
    def _require_native_signature(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("tijara.saas.payment_require_native_signatures")
            or os.environ.get("TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES")
        )
        return self._truthy(value)

    @api.model
    def tijara_provider_contract(self, provider):
        provider_key = self._provider_key(provider)
        contract = dict(PROVIDER_CONTRACTS[provider_key])
        contract["provider"] = provider_key
        return contract

    @api.model
    def tijara_provider_parser_profiles(self):
        return {
            contract["settlement_parser_profile"]
            for contract in PROVIDER_CONTRACTS.values()
            if contract.get("settlement_parser_profile")
        }

    @api.model
    def tijara_settlement_parser_profile(self, provider):
        return self.tijara_provider_contract(provider).get("settlement_parser_profile") or "auto"

    @api.model
    def tijara_provider_secret_status(self, provider):
        contract = self.tijara_provider_contract(provider)
        configured = self._config_or_env_present(
            contract["secret_param"],
            contract["secret_env"],
        )
        return {
            "provider": contract["provider"],
            "required": bool(contract["signature_required"]),
            "configured": configured,
            "param": contract["secret_param"],
            "env": contract["secret_env"],
        }

    @api.model
    def _certification_status(self, provider):
        provider_key = self._provider_key(provider)
        env_prefix = "TIJARA_%s" % provider_key.upper()
        config = self.env["ir.config_parameter"].sudo()
        reference = (
            config.get_param("tijara.saas.%s_certification_reference" % provider_key)
            or os.environ.get("%s_CERTIFICATION_REFERENCE" % env_prefix)
            or ""
        )
        status = (
            config.get_param("tijara.saas.%s_certification_status" % provider_key)
            or os.environ.get("%s_CERTIFICATION_STATUS" % env_prefix)
            or ""
        )
        return {
            "reference_present": bool(str(reference).strip()),
            "status": str(status or "").strip().lower(),
        }

    @api.model
    def tijara_provider_readiness(self, provider):
        contract = self.tijara_provider_contract(provider)
        require_native = self._require_native_signature()
        secret = self.tijara_provider_secret_status(provider)
        certification = self._certification_status(provider)
        rows = []
        blockers = []
        warnings = []

        def add(name, status, message):
            rows.append({"name": name, "status": status, "message": message})
            if status == "failed":
                blockers.append(message)
            elif status == "warning":
                warnings.append(message)

        add(
            "webhook-route",
            "passed",
            _("Provider webhook route is %s.") % contract["webhook_route"],
        )
        add(
            "settlement-parser",
            "passed" if contract["settlement_parser_profile"] else "warning",
            _("Settlement parser profile is %s.") % (contract["settlement_parser_profile"] or "not configured"),
        )
        if contract["signature_required"]:
            if secret["configured"]:
                add(
                    "native-signature-secret",
                    "passed",
                    _("Native signature secret is configured without exposing the secret value."),
                )
            elif require_native:
                add(
                    "native-signature-secret",
                    "failed",
                    _("Native signatures are required, but the provider secret is not configured."),
                )
            else:
                add(
                    "native-signature-secret",
                    "warning",
                    _("Native signature secret is missing; production should enable it after PSP certification."),
                )
        else:
            add(
                "native-signature-secret",
                "passed",
                _("Native provider signature secret is not required for this adapter."),
            )
        if {"refund", "chargeback", "settlement"}.issubset(set(contract["event_types"])):
            add(
                "refund-chargeback-settlement-events",
                "passed",
                _("Adapter maps refund, chargeback, and settlement events."),
            )
        else:
            add(
                "refund-chargeback-settlement-events",
                "failed",
                _("Adapter does not cover refund, chargeback, and settlement events."),
            )
        if contract["certification_required"]:
            if certification["reference_present"] and certification["status"] in {"approved", "passed", "certified"}:
                add(
                    "psp-certification",
                    "passed",
                    _("Provider certification reference is recorded and approved."),
                )
            else:
                add(
                    "psp-certification",
                    "warning",
                    _("Provider certification evidence is not approved yet."),
                )
        else:
            add(
                "psp-certification",
                "passed",
                _("External PSP certification is not required for this adapter."),
            )

        decision = "failed" if blockers else "warning" if warnings else "passed"
        return {
            "provider": contract["provider"],
            "decision": decision,
            "ci_status": "fail" if blockers else "pass_with_warnings" if warnings else "pass",
            "require_native_signatures": require_native,
            "signature": secret,
            "contract": contract,
            "checks": rows,
            "blockers": blockers,
            "warnings": warnings,
        }

    @api.model
    def tijara_all_provider_readiness(self):
        return {
            provider: self.tijara_provider_readiness(provider)
            for provider in sorted(PROVIDER_CONTRACTS)
        }

    @api.model
    def tijara_validate_webhook_payload(self, provider, payload, raw_body="", headers=None):
        event_model = self.env["tijara.saas.payment.webhook.event"].sudo()
        payload = payload or {}
        if not raw_body:
            raw_body = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        verification = event_model.tijara_verify_provider_signature(
            provider,
            payload,
            raw_body=raw_body,
            headers=headers or {},
        )
        return {
            "provider": self._provider_key(provider),
            "signature": verification,
            "provider_values": event_model._provider_payload(provider, payload),
            "readiness": self.tijara_provider_readiness(provider),
        }
