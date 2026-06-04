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
