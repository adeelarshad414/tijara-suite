import hashlib
import hmac
import json
import time

from odoo import fields
from odoo.exceptions import UserError
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

    def _create_account(self, name, code, account_type):
        account_model = self.env["account.account"].with_company(self.company)
        values = {
            "name": name,
            "code": code,
            "account_type": account_type,
        }
        if "company_ids" in account_model._fields:
            values["company_ids"] = [(6, 0, [self.company.id])]
        elif "company_id" in account_model._fields:
            values["company_id"] = self.company.id
        return account_model.create(values)

    def _create_journal(self, name, code, journal_type, default_account=False):
        journal_model = self.env["account.journal"].with_company(self.company)
        values = {
            "name": name,
            "code": code,
            "type": journal_type,
            "company_id": self.company.id,
        }
        if default_account and "default_account_id" in journal_model._fields:
            values["default_account_id"] = default_account.id
        return journal_model.create(values)

    def _configure_payment_accounting(self):
        clearing = self._create_account("Tijara PSP Clearing", "TJP001", "asset_current")
        counterpart = self._create_account("Tijara PSP Counterpart", "TJP002", "asset_current")
        provider_fee = self._create_account("Tijara PSP Fees", "TJP003", "expense")
        refund = self._create_account("Tijara Refunds", "TJP004", "expense")
        chargeback_receivable = self._create_account(
            "Tijara Chargeback Receivable",
            "TJP005",
            "asset_current",
        )
        chargeback_fee = self._create_account("Tijara Chargeback Fees", "TJP006", "expense")
        writeoff = self._create_account("Tijara Write-Offs", "TJP007", "expense")
        refund_payment_account = self._create_account("Tijara Refund Payment Bank", "TJP008", "asset_cash")
        refund_payment_outstanding = self._create_account(
            "Tijara Refund Payment Outstanding",
            "TJP009",
            "asset_current",
        )
        customer_receivable = self._create_account("Tijara Refund Customer Receivable", "TJP010", "asset_receivable")
        self.customer.with_company(self.company).property_account_receivable_id = customer_receivable
        journal = self._create_journal("Tijara PSP Accounting", "TJPA", "general", clearing)
        refund_payment_journal = self._create_journal(
            "Tijara Refund Payments",
            "TJRP",
            "bank",
            refund_payment_account,
        )
        if (
            "outbound_payment_method_line_ids" in refund_payment_journal._fields
            and refund_payment_journal.outbound_payment_method_line_ids
            and "payment_account_id" in refund_payment_journal.outbound_payment_method_line_ids._fields
        ):
            refund_payment_journal.outbound_payment_method_line_ids.write(
                {"payment_account_id": refund_payment_outstanding.id}
            )
        self.company.write(
            {
                "tijara_payment_accounting_journal_id": journal.id,
                "tijara_payment_clearing_account_id": clearing.id,
                "tijara_payment_counterpart_account_id": counterpart.id,
                "tijara_provider_fee_account_id": provider_fee.id,
                "tijara_refund_account_id": refund.id,
                "tijara_refund_payment_journal_id": refund_payment_journal.id,
                "tijara_chargeback_receivable_account_id": chargeback_receivable.id,
                "tijara_chargeback_fee_account_id": chargeback_fee.id,
                "tijara_writeoff_account_id": writeoff.id,
            }
        )
        return {
            "journal": journal,
            "clearing": clearing,
            "counterpart": counterpart,
            "provider_fee": provider_fee,
            "refund": refund,
            "refund_payment_journal": refund_payment_journal,
            "refund_payment_account": refund_payment_account,
            "refund_payment_outstanding": refund_payment_outstanding,
            "customer_receivable": customer_receivable,
            "chargeback_receivable": chargeback_receivable,
            "chargeback_fee": chargeback_fee,
            "writeoff": writeoff,
        }

    def _create_subscription_invoice(self, subscription, amount=1000):
        receivable = self._create_account("Tijara Customer Receivable", "TJP100", "asset_receivable")
        income = self._create_account("Tijara SaaS Income", "TJP101", "income")
        sale_journal = self._create_journal("Tijara SaaS Sales", "TJSA", "sale", income)
        self.customer.with_company(self.company).property_account_receivable_id = receivable
        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.customer.id,
                    "company_id": self.company.id,
                    "journal_id": sale_journal.id,
                    "invoice_date": fields.Date.context_today(self.env.user),
                    "invoice_date_due": fields.Date.context_today(self.env.user),
                    "invoice_origin": subscription.name,
                    "ref": subscription.database_name,
                    "tijara_saas_subscription_id": subscription.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Tijara SaaS Subscription",
                                "quantity": 1,
                                "price_unit": amount,
                                "account_id": income.id,
                            },
                        )
                    ],
                }
            )
        )
        subscription.last_invoice_id = invoice.id
        return invoice

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

    def test_provider_adapter_readiness_matrix_and_payload_validation(self):
        adapter = self.env["tijara.saas.payment.provider.adapter"]
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("tijara.saas.payment_require_native_signatures", "1")
        config.set_param("tijara.saas.stripe_webhook_secret", "whsec_adapter_test")
        config.set_param("tijara.saas.stripe_certification_reference", "STRIPE-UAT-001")
        config.set_param("tijara.saas.stripe_certification_status", "approved")

        stripe_readiness = adapter.tijara_provider_readiness("stripe")

        self.assertEqual(stripe_readiness["decision"], "passed")
        self.assertEqual(stripe_readiness["signature"]["configured"], True)
        self.assertNotIn("whsec_adapter_test", json.dumps(stripe_readiness))
        self.assertIn("refund", stripe_readiness["contract"]["event_types"])
        self.assertIn("chargeback", stripe_readiness["contract"]["event_types"])
        self.assertEqual(adapter.tijara_settlement_parser_profile("easypaisa"), "easypaisa_merchant_v1")

        stripe_payload = {
            "id": "evt_adapter_refund_001",
            "type": "refund.created",
            "data": {
                "object": {
                    "id": "re_adapter_001",
                    "amount": 125000,
                    "metadata": {"database_name": "tijara_test_tenant"},
                }
            },
        }
        raw_body = json.dumps(stripe_payload, separators=(",", ":"))
        timestamp = str(int(time.time()))
        stripe_signature = hmac.new(
            b"whsec_adapter_test",
            ("%s.%s" % (timestamp, raw_body)).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        normalized = adapter.tijara_validate_webhook_payload(
            "stripe",
            stripe_payload,
            raw_body=raw_body,
            headers={"Stripe-Signature": "t=%s,v1=%s" % (timestamp, stripe_signature)},
        )

        self.assertEqual(normalized["signature"]["signature_status"], "valid")
        self.assertEqual(normalized["provider_values"]["payment_event_type"], "refund")
        self.assertEqual(normalized["provider_values"]["refund_reference"], "re_adapter_001")
        self.assertEqual(normalized["provider_values"]["amount"], 1250)

        jazzcash_readiness = adapter.tijara_provider_readiness("jazzcash")

        self.assertEqual(jazzcash_readiness["decision"], "failed")
        self.assertIn("provider secret is not configured", " ".join(jazzcash_readiness["blockers"]))

    def test_provider_adapter_sets_default_settlement_parser_profile(self):
        batch = self.env["tijara.saas.payment.settlement.batch"].create(
            {
                "provider": "easypaisa",
                "provider_batch_reference": "EP-BATCH-DEFAULT-PARSER",
                "company_id": self.company.id,
            }
        )

        self.assertEqual(batch.parser_profile, "easypaisa_merchant_v1")

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

        batch.action_generate_accounting_actions()

        self.assertEqual(batch.finance_approval_status, "pending")
        self.assertEqual(batch.accounting_action_count, 2)
        self.assertIn("provider_fee", batch.accounting_action_ids.mapped("action_type"))
        self.assertIn("payout_clearing", batch.accounting_action_ids.mapped("action_type"))

        with self.assertRaises(UserError):
            batch.action_mark_reconciled()

        batch.action_approve_finance_actions()

        self.assertEqual(batch.finance_approval_status, "approved")
        self.assertTrue(all(action.audit_hash for action in batch.accounting_action_ids))

        self._configure_payment_accounting()
        batch.action_create_draft_accounting_moves()
        draft_moves = batch.accounting_action_ids.mapped("accounting_move_id")

        self.assertEqual(len(draft_moves), 2)
        self.assertTrue(all(move.state == "draft" for move in draft_moves))

        batch.action_mark_reconciled()

        self.assertEqual(batch.reconciliation_status, "reconciled")
        self.assertEqual(line.reconciliation_status, "reconciled")

    def test_settlement_parser_profile_normalizes_stripe_csv_fixture(self):
        subscription = self._subscription(self.enterprise_plan, state="active")
        batch = self.env["tijara.saas.payment.settlement.batch"].create(
            {
                "provider": "stripe",
                "parser_profile": "stripe_balance_v1",
                "statement_format": "csv",
                "provider_batch_reference": "STRIPE-BALANCE-001",
                "company_id": self.company.id,
                "raw_statement_json": (
                    "id,type,amount,fee,net,source,status,metadata_database_name,available_on\n"
                    "txn_001,charge,250000,7500,242500,ch_001,available,tijara_test_tenant,1780617600\n"
                ),
            }
        )

        batch.action_import_statement_payload()
        line = batch.line_ids

        self.assertEqual(line.provider_event_reference, "txn_001")
        self.assertEqual(line.provider_transaction_id, "ch_001")
        self.assertEqual(line.payment_event_type, "payment")
        self.assertEqual(line.gross_amount, 2500)
        self.assertEqual(line.fee_amount, 75)
        self.assertEqual(line.net_amount, 2425)
        self.assertEqual(line.database_name, subscription.database_name)
        self.assertEqual(line.subscription_id, subscription)
        self.assertEqual(line.reconciliation_status, "matched")

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

        line.action_generate_accounting_actions()
        self.assertIn("refund_credit_note", line.accounting_action_ids.mapped("action_type"))
        self.assertEqual(batch.finance_approval_status, "pending")
        batch.action_approve_finance_actions()
        self.assertEqual(batch.finance_approval_status, "approved")

    def test_dispute_case_generates_and_approves_chargeback_accounting_actions(self):
        subscription = self._subscription(self.enterprise_plan, state="active")
        subscription.write({"payment_status": "paid"})
        case = self.env["tijara.saas.payment.dispute"].create(
            {
                "case_type": "chargeback",
                "provider": "stripe",
                "company_id": self.company.id,
                "subscription_id": subscription.id,
                "provider_reference": "dp_accounting_001",
                "transaction_id": "ch_accounting_001",
                "amount": 1500,
                "provider_fee_amount": 50,
                "reason": "fraudulent",
            }
        )

        case.action_open()
        case.action_mark_lost()

        action_types = set(case.accounting_action_ids.mapped("action_type"))

        self.assertIn("chargeback_receivable", action_types)
        self.assertIn("chargeback_fee", action_types)
        self.assertIn("write_off", action_types)
        self.assertEqual(case.finance_approval_status, "pending")

        case.action_approve_finance_actions()

        self.assertEqual(case.finance_approval_status, "approved")
        self.assertTrue(all(action.audit_hash for action in case.accounting_action_ids))

        self._configure_payment_accounting()
        case.action_create_draft_accounting_moves()
        draft_moves = case.accounting_action_ids.mapped("accounting_move_id")

        self.assertEqual(len(draft_moves), 3)
        self.assertTrue(all(move.state == "draft" for move in draft_moves))

    def test_accounting_action_requires_finance_config_before_draft_move(self):
        action = self.env["tijara.saas.payment.accounting.action"].create(
            {
                "action_type": "provider_fee",
                "provider": "stripe",
                "company_id": self.company.id,
                "amount": 75,
            }
        )
        action.action_approve()

        with self.assertRaises(UserError):
            action.action_create_draft_accounting_move()

        self.assertFalse(action.accounting_move_id)
        self.assertEqual(action.status, "approved")

    def test_approved_accounting_action_creates_balanced_draft_move(self):
        config = self._configure_payment_accounting()
        action = self.env["tijara.saas.payment.accounting.action"].create(
            {
                "action_type": "provider_fee",
                "provider": "stripe",
                "company_id": self.company.id,
                "amount": 75,
            }
        )
        action.action_approve()

        action.action_create_draft_accounting_move()
        move = action.accounting_move_id

        self.assertTrue(move)
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.journal_id, config["journal"])
        self.assertEqual(move.company_id, self.company)
        self.assertEqual(sum(move.line_ids.mapped("debit")), 75)
        self.assertEqual(sum(move.line_ids.mapped("credit")), 75)
        self.assertIn(config["provider_fee"], move.line_ids.mapped("account_id"))
        self.assertIn(config["clearing"], move.line_ids.mapped("account_id"))
        self.assertEqual(action.status, "approved")
        self.assertTrue(action.audit_hash)

        action.action_create_draft_accounting_move()
        self.assertEqual(action.accounting_move_id, move)

    def test_refund_credit_note_action_creates_customer_credit_note(self):
        self._configure_payment_accounting()
        subscription = self._subscription(self.enterprise_plan, state="active")
        invoice = self._create_subscription_invoice(subscription, amount=1000)
        action = self.env["tijara.saas.payment.accounting.action"].create(
            {
                "action_type": "refund_credit_note",
                "provider": "stripe",
                "company_id": self.company.id,
                "subscription_id": subscription.id,
                "invoice_id": invoice.id,
                "amount": 250,
            }
        )
        action.action_approve()

        action.action_create_draft_accounting_move()
        credit_note = action.accounting_move_id

        self.assertTrue(credit_note)
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertEqual(credit_note.state, "draft")
        self.assertEqual(credit_note.partner_id, self.customer)
        self.assertEqual(credit_note.tijara_saas_subscription_id, subscription)
        self.assertEqual(credit_note.invoice_line_ids[:1].price_unit, 250)
        self.assertFalse(action.refund_payment_id)

    def test_refund_payment_action_creates_draft_outbound_payment(self):
        config = self._configure_payment_accounting()
        subscription = self._subscription(self.enterprise_plan, state="active")
        action = self.env["tijara.saas.payment.accounting.action"].create(
            {
                "action_type": "refund_payment",
                "provider": "stripe",
                "company_id": self.company.id,
                "subscription_id": subscription.id,
                "amount": 250,
            }
        )
        action.action_approve()

        action.action_create_draft_accounting_move()
        payment = action.refund_payment_id

        self.assertTrue(payment)
        self.assertEqual(payment.payment_type, "outbound")
        self.assertEqual(payment.partner_type, "customer")
        self.assertEqual(payment.partner_id, self.customer)
        self.assertEqual(payment.journal_id, config["refund_payment_journal"])
        self.assertEqual(payment.amount, 250)
        self.assertEqual(payment.state, "draft")
        self.assertFalse(action.accounting_move_id)

        action.action_post_accounting_move()

        self.assertNotEqual(payment.state, "draft")
        self.assertEqual(action.status, "posted")
        self.assertTrue(action.accounting_move_id)
        if "move_id" in payment._fields:
            self.assertEqual(action.accounting_move_id, payment.move_id)
            self.assertEqual(payment.move_id.state, "posted")

    def test_manual_review_action_does_not_create_automatic_move(self):
        self._configure_payment_accounting()
        action = self.env["tijara.saas.payment.accounting.action"].create(
            {
                "action_type": "manual_review",
                "provider": "manual",
                "company_id": self.company.id,
                "amount": 100,
            }
        )
        action.action_approve()

        with self.assertRaises(UserError):
            action.action_create_draft_accounting_move()

        self.assertFalse(action.accounting_move_id)

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
