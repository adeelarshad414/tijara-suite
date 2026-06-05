import hashlib
import hmac
import json
import time

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraSaasEnforcement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Tijara Test Tenant"})
        cls.customer = cls.env["res.partner"].create({"name": "Tijara SaaS Test Customer"})
        cls.starter_plan = cls.env.ref("tijara_saas_control.plan_starter")
        cls.enterprise_plan = cls.env.ref("tijara_saas_control.plan_enterprise")

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "tijara.saas.enforcement_enabled",
            "1",
        )

    def _subscription(self, plan, state="active"):
        return self.env["tijara.saas.subscription"].create(
            {
                "name": "Test Subscription",
                "tenant_name": self.company.name,
                "database_name": "tijara_test_tenant",
                "customer_id": self.customer.id,
                "company_id": self.company.id,
                "plan_id": plan.id,
                "state": state,
                "start_date": fields.Date.context_today(self.env.user),
            }
        )

    def test_saas_feature_enforcement_blocks_starter_and_allows_enterprise(self):
        subscription = self._subscription(self.starter_plan)

        self.assertFalse(self.company.tijara_has_saas_feature("b2b_sales"))
        self.assertFalse(self.company.tijara_has_saas_feature("queue_system"))

        subscription.plan_id = self.enterprise_plan

        self.assertTrue(self.company.tijara_has_saas_feature("b2b_sales"))
        self.assertTrue(self.company.tijara_has_saas_feature("queue_system"))
        self.assertTrue(self.company.tijara_has_saas_feature("customer_display"))

    def test_enforcement_disabled_keeps_community_dev_mode_unblocked(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "tijara.saas.enforcement_enabled",
            "0",
        )

        self.assertTrue(self.company.tijara_has_saas_feature("b2b_sales"))
        self.assertTrue(self.company.tijara_has_saas_feature("promotion_display"))

    def test_tenant_provisioning_request_moves_subscription_to_active(self):
        subscription = self._subscription(self.starter_plan, state="draft")
        request = self.env["tijara.tenant.provision.request"].create(
            {
                "tenant_name": "Provisioned Test Tenant",
                "database_name": "tijara_provisioned_test",
                "subscription_id": subscription.id,
                "company_id": self.company.id,
            }
        )

        request.action_approve()
        request.write(
            {
                "primary_domain": "tenant.example.test",
                "admin_email": "admin@example.test",
            }
        )
        request.action_generate_operations_manifest()
        request.action_start_provisioning()
        request.action_mark_provisioned()

        self.assertEqual(request.state, "provisioned")
        self.assertEqual(subscription.state, "active")
        self.assertEqual(subscription.database_name, "tijara_provisioned_test")
        self.assertIn("tenant.example.test", request.operations_manifest)
        self.assertIn("restore_drill_required", request.operations_manifest)

    def test_payment_webhook_event_marks_subscription_paid(self):
        subscription = self._subscription(self.enterprise_plan, state="past_due")
        subscription.write({"payment_status": "past_due", "dunning_level": 2})

        event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "jazzcash",
            {
                "event_reference": "JC-TXN-001",
                "database_name": subscription.database_name,
                "status": "succeeded",
                "amount": 15000,
            },
            signature="signed",
        )

        self.assertEqual(event.status, "applied")
        self.assertEqual(subscription.payment_status, "paid")
        self.assertEqual(subscription.state, "active")
        self.assertEqual(subscription.dunning_level, 0)
        self.assertEqual(event.signature_status, "unchecked")
        self.assertEqual(event.reconciliation_status, "matched")

    def test_provider_payload_adapters_normalize_stripe_and_easypaisa(self):
        subscription = self._subscription(self.enterprise_plan, state="past_due")

        stripe_event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "stripe",
            {
                "id": "evt_test_001",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_001",
                        "payment_intent": "pi_test_001",
                        "amount_total": 250000,
                        "metadata": {"database_name": subscription.database_name},
                    }
                },
            },
            signature="stripe-signed",
            signature_status="valid",
        )

        self.assertEqual(stripe_event.status, "applied")
        self.assertEqual(stripe_event.provider_reference, "cs_test_001")
        self.assertEqual(stripe_event.transaction_id, "pi_test_001")
        self.assertEqual(stripe_event.amount, 2500)
        self.assertEqual(stripe_event.signature_status, "valid")

        easypaisa_event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "easypaisa",
            {
                "transactionId": "EP-TXN-001",
                "orderId": subscription.external_payment_reference or subscription.database_name,
                "database_name": subscription.database_name,
                "transactionStatus": "completed",
                "amount": 5000,
            },
        )

        self.assertEqual(easypaisa_event.transaction_id, "EP-TXN-001")
        self.assertEqual(easypaisa_event.payment_status, "paid")

    def test_native_payment_signature_verification(self):
        event_model = self.env["tijara.saas.payment.webhook.event"]
        self.env["ir.config_parameter"].sudo().set_param(
            "tijara.saas.stripe_webhook_secret",
            "whsec_tijara_test",
        )
        stripe_payload = {
            "id": "evt_sig_001",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_sig_001", "amount_total": 100000}},
        }
        raw_body = json.dumps(stripe_payload, separators=(",", ":"))
        timestamp = str(int(time.time()))
        stripe_signature = hmac.new(
            b"whsec_tijara_test",
            ("%s.%s" % (timestamp, raw_body)).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        verification = event_model.tijara_verify_provider_signature(
            "stripe",
            stripe_payload,
            raw_body=raw_body,
            headers={"Stripe-Signature": "t=%s,v1=%s" % (timestamp, stripe_signature)},
        )

        self.assertEqual(verification["signature_status"], "valid")

        invalid = event_model.tijara_verify_provider_signature(
            "stripe",
            stripe_payload,
            raw_body=raw_body,
            headers={"Stripe-Signature": "t=%s,v1=bad" % timestamp},
        )

        self.assertEqual(invalid["signature_status"], "invalid")

        self.env["ir.config_parameter"].sudo().set_param(
            "tijara.saas.jazzcash_integrity_salt",
            "jazzcash-test-salt",
        )
        jazzcash_payload = {
            "pp_Amount": "15000",
            "pp_BillReference": "tijara_test_tenant",
            "pp_ResponseCode": "000",
            "pp_TxnRefNo": "JC-SIG-001",
        }
        signature = next(
            iter(event_model._jazzcash_signature_candidates(jazzcash_payload, "jazzcash-test-salt"))
        )
        jazzcash_payload["pp_SecureHash"] = signature

        jazzcash_verification = event_model.tijara_verify_provider_signature(
            "jazzcash",
            jazzcash_payload,
            raw_body=json.dumps(jazzcash_payload, separators=(",", ":")),
        )

        self.assertEqual(jazzcash_verification["signature_status"], "valid")

    def test_refund_chargeback_and_settlement_events_are_auditable(self):
        subscription = self._subscription(self.enterprise_plan, state="active")
        subscription.write({"payment_status": "paid"})

        refund_event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "stripe",
            {
                "id": "evt_refund_001",
                "type": "refund.created",
                "data": {
                    "object": {
                        "id": "re_test_001",
                        "amount": 150000,
                        "metadata": {"database_name": subscription.database_name},
                    }
                },
            },
            signature_status="valid",
            signature_algorithm="stripe-hmac-sha256",
        )

        self.assertEqual(refund_event.payment_event_type, "refund")
        self.assertEqual(refund_event.status, "applied")
        self.assertEqual(subscription.payment_status, "failed")
        self.assertEqual(subscription.state, "past_due")
        self.assertTrue(refund_event.provider_audit_hash)
        self.assertTrue(refund_event.dispute_case_id)
        self.assertEqual(refund_event.dispute_case_id.case_type, "refund")

        chargeback_event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "stripe",
            {
                "id": "evt_dispute_001",
                "type": "charge.dispute.created",
                "data": {
                    "object": {
                        "id": "dp_test_001",
                        "reason": "fraudulent",
                        "amount": 150000,
                        "metadata": {"database_name": subscription.database_name},
                    }
                },
            },
            signature_status="valid",
            signature_algorithm="stripe-hmac-sha256",
        )

        self.assertEqual(chargeback_event.payment_event_type, "chargeback")
        self.assertEqual(chargeback_event.chargeback_reference, "dp_test_001")
        self.assertTrue(chargeback_event.dispute_case_id)
        self.assertEqual(chargeback_event.dispute_case_id.case_type, "chargeback")
        self.assertIn("fraudulent", subscription.suspension_reason)

        settlement_event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "stripe",
            {
                "id": "evt_payout_001",
                "type": "payout.paid",
                "data": {"object": {"id": "po_test_001", "amount": 150000}},
            },
            signature_status="valid",
            signature_algorithm="stripe-hmac-sha256",
        )

        self.assertEqual(settlement_event.payment_event_type, "settlement")
        self.assertEqual(settlement_event.status, "applied")
        self.assertEqual(settlement_event.reconciliation_status, "pending")

    def test_settlement_batch_import_matches_and_reconciles_provider_lines(self):
        subscription = self._subscription(self.enterprise_plan, state="past_due")
        event = self.env["tijara.saas.payment.webhook.event"].tijara_from_payload(
            "jazzcash",
            {
                "event_reference": "JC-SETTLE-001",
                "pp_TxnRefNo": "JC-SETTLE-001",
                "database_name": subscription.database_name,
                "status": "succeeded",
                "amount": 15000,
            },
        )
        batch = self.env["tijara.saas.payment.settlement.batch"].create(
            {
                "provider": "jazzcash",
                "provider_batch_reference": "JC-BATCH-001",
                "company_id": self.company.id,
                "expected_gross_amount": 15000,
                "expected_fee_amount": 150,
                "expected_net_amount": 14850,
                "raw_statement_json": json.dumps(
                    {
                        "lines": [
                            {
                                "event_reference": "JC-SETTLE-001",
                                "pp_TxnRefNo": "JC-SETTLE-001",
                                "pp_Amount": "15000",
                                "pp_FeeAmount": "150",
                                "event_type": "payment",
                                "database_name": subscription.database_name,
                            }
                        ]
                    }
                ),
            }
        )

        batch.action_import_statement_payload()
        line = batch.line_ids

        self.assertEqual(batch.reconciliation_status, "matched")
        self.assertEqual(batch.line_count, 1)
        self.assertEqual(batch.actual_gross_amount, 15000)
        self.assertEqual(batch.actual_fee_amount, 150)
        self.assertEqual(batch.actual_net_amount, 14850)
        self.assertEqual(line.webhook_event_id, event)
        self.assertEqual(line.subscription_id, subscription)
        self.assertEqual(line.reconciliation_status, "matched")
        self.assertTrue(batch.statement_hash)
        self.assertTrue(line.line_hash)

        batch.action_mark_reconciled()

        self.assertEqual(batch.reconciliation_status, "reconciled")
        self.assertEqual(line.reconciliation_status, "reconciled")

    def test_settlement_refund_line_creates_dispute_case_with_evidence_flow(self):
        subscription = self._subscription(self.enterprise_plan, state="active")
        subscription.write({"payment_status": "paid"})
        batch = self.env["tijara.saas.payment.settlement.batch"].create(
            {
                "provider": "stripe",
                "provider_batch_reference": "STRIPE-BATCH-REFUND-001",
                "company_id": self.company.id,
                "raw_statement_json": json.dumps(
                    [
                        {
                            "id": "re_settlement_001",
                            "type": "refund",
                            "amount": 150000,
                            "fee": 0,
                            "database_name": subscription.database_name,
                            "status": "refunded",
                        }
                    ]
                ),
            }
        )

        batch.action_import_statement_payload()
        line = batch.line_ids
        line.action_create_dispute_case()
        case = line.dispute_case_id

        self.assertEqual(line.payment_event_type, "refund")
        self.assertEqual(line.gross_amount, 1500)
        self.assertEqual(line.subscription_id, subscription)
        self.assertEqual(case.case_type, "refund")
        self.assertEqual(case.amount, 1500)
        self.assertEqual(case.state, "open")
        self.assertEqual(subscription.payment_status, "failed")
        self.assertEqual(subscription.state, "past_due")

        case.write(
            {
                "evidence_summary": "Refund reviewed with provider statement.",
                "evidence_json": '{"settlement":"STRIPE-BATCH-REFUND-001"}',
            }
        )
        case.action_submit_evidence()

        self.assertEqual(case.state, "evidence")
        self.assertTrue(case.evidence_hash)

        case.action_mark_won()

        self.assertEqual(case.state, "won")
        self.assertEqual(subscription.payment_status, "paid")
        self.assertEqual(subscription.state, "active")

    def test_dunning_suspends_after_grace_period(self):
        subscription = self._subscription(self.enterprise_plan, state="active")
        yesterday = fields.Date.subtract(fields.Date.context_today(self.env.user), days=1)
        subscription.write(
            {
                "payment_status": "past_due",
                "next_invoice_date": yesterday,
                "grace_until": yesterday,
            }
        )

        subscription.action_run_dunning()

        self.assertEqual(subscription.state, "suspended")
        self.assertGreaterEqual(subscription.dunning_level, 3)
