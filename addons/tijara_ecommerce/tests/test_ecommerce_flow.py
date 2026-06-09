import json
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraEcommerceFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "tijara_business_type": "cafe",
                "tijara_gst_enabled": True,
                "tijara_service_charge_enabled": True,
                "tijara_service_charge_percent": 10.0,
                "tijara_delivery_charge_enabled": True,
                "tijara_delivery_charge_amount": 150.0,
                "tijara_food_payment_tax_enabled": True,
                "tijara_food_card_tax_percent": 5.0,
                "tijara_food_cash_tax_percent": 16.0,
                "tijara_loyalty_enabled": True,
                "tijara_loyalty_points_per_currency": 0.01,
            }
        )
        cls.env["tijara.localization.setup"].sudo().ensure_pakistan_defaults()
        cls.tax = cls.env["tijara.localization.setup"].sudo().get_standard_sale_tax(cls.company)
        product_values = {
            "name": "Tijara Ecommerce Test Product",
            "default_code": "TIJARA-ECOM-TEST",
            "barcode": "6299000000001",
            "type": "consu",
            "is_storable": True,
            "sale_ok": True,
            "purchase_ok": True,
            "list_price": 100.0,
            "standard_price": 70.0,
            "tijara_urdu_name": "ای کامرس ٹیسٹ پروڈکٹ",
            "tijara_tax_category": "standard",
            "tijara_vertical_tag": "grocery",
            "tijara_b2c_price": 120.0,
            "tijara_b2b_price": 95.0,
            "tijara_ecommerce_published": True,
            "tijara_ecommerce_featured": True,
        }
        if cls.tax:
            product_values["taxes_id"] = [Command.set([cls.tax.id])]
        cls.product_template = cls.env["product.template"].sudo().create(product_values)
        cls.product = cls.product_template.product_variant_id
        cls.channel = cls.env["tijara.ecommerce.channel"].sudo().create(
            {
                "name": "Tijara Test Web Store",
                "code": "TIJARA-TEST-WEB",
                "url_slug": "tijara-test-web",
                "company_id": cls.company.id,
                "default_audience": "b2c",
                "allow_b2c": True,
                "allow_b2b": True,
                "allow_delivery": True,
                "allow_pickup": True,
                "allow_store_pickup": True,
                "allow_cash": True,
                "allow_card": True,
                "allow_cod": True,
                "auto_queue_pickup_delivery": True,
            }
        )
        cls.provider = cls.env["tijara.ecommerce.delivery.provider"].sudo().create(
            {
                "name": "Tijara Test Delivery",
                "code": "TIJARA-TEST-DELIVERY",
                "company_id": cls.company.id,
                "provider_type": "dummy",
                "service_level": "same_day",
                "dry_run": True,
                "adapter_mode": "dry_run",
                "auto_assign": True,
                "supports_cancel": True,
                "supports_labels": True,
                "supports_manifests": True,
                "supports_webhooks": True,
                "label_format": "pdf",
                "webhook_signature_mode": "dry_run",
                "tracking_url_template": "https://tracking.example.test/{tracking_number}",
            }
        )
        cls.channel.write(
            {
                "delivery_provider_ids": [Command.set(cls.provider.ids)],
                "default_delivery_provider_id": cls.provider.id,
            }
        )

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("tijara.saas.enforcement_enabled", "0")

    def test_catalog_returns_b2b_b2c_prices_and_urdu_product_name(self):
        payload = self.channel.tijara_catalog_payload(audience="b2b")
        product = next(row for row in payload["products"] if row["product_id"] == self.product.id)
        self.assertEqual(product["price"], 95.0)
        self.assertEqual(product["b2c_price"], 120.0)
        self.assertEqual(product["b2b_price"], 95.0)
        self.assertEqual(product["name_urdu"], "ای کامرس ٹیسٹ پروڈکٹ")
        self.assertIn("delivery", payload["fulfillment"]["methods"])
        self.assertIn("card", payload["payment"]["methods"])

    def test_checkout_creates_sale_order_with_charges_queue_and_loyalty(self):
        order = self.channel.tijara_create_order(
            {
                "audience": "b2b",
                "fulfillment_method": "delivery",
                "payment_method": "card",
                "customer": {
                    "name": "Online Wholesale Customer",
                    "mobile": "03001234567",
                    "email": "online-wholesale@example.com",
                    "delivery_address": "Test delivery address",
                    "loyalty_opt_in": True,
                },
                "lines": [{"product_id": self.product.id, "quantity": 2}],
            }
        )
        product_line = order.order_line.filtered(lambda line: line.product_id == self.product)
        self.assertEqual(order.tijara_ecommerce_channel_id, self.channel)
        self.assertEqual(order.tijara_ecommerce_audience, "b2b")
        self.assertEqual(product_line.price_unit, 95.0)
        self.assertAlmostEqual(order.tijara_amount_service_charge, 19.0)
        self.assertAlmostEqual(order.tijara_amount_delivery_charge, 150.0)
        self.assertAlmostEqual(order.tijara_amount_payment_tax, 17.95)
        self.assertTrue(order.tijara_pickup_code)
        self.assertTrue(order.tijara_queue_ticket_id)
        self.assertEqual(order.tijara_queue_ticket_id.source, "ecommerce")
        self.assertTrue(order.tijara_tracking_token)
        self.assertTrue(order.tijara_tracking_url)
        self.assertEqual(order.tijara_delivery_provider_id, self.provider)
        self.assertEqual(order.tijara_delivery_status, "assigned")
        self.assertEqual(order.tijara_delivery_adapter_state, "created")
        self.assertTrue(order.tijara_delivery_provider_reference)
        self.assertTrue(order.tijara_delivery_tracking_number)
        self.assertTrue(order.tijara_delivery_tracking_url)
        self.assertTrue(order.tijara_delivery_last_event_id)
        tracking = self.channel.tijara_tracking_payload({"tracking_token": order.tijara_tracking_token})
        self.assertEqual(tracking["status"], "ok")
        self.assertEqual(tracking["order"]["pickup_code"], order.tijara_pickup_code)
        self.assertEqual(tracking["queue"]["number"], order.tijara_queue_ticket_id.queue_number)
        self.assertEqual(tracking["delivery"]["provider"], self.provider.name)
        self.assertEqual(tracking["delivery"]["adapter_state"], "created")
        self.assertEqual(tracking["delivery"]["provider_reference"], order.tijara_delivery_provider_reference)
        self.assertEqual(tracking["delivery"]["sla_state"], "on_track")
        self.assertTrue(tracking["delivery"]["sla_deadline"])
        order.action_tijara_mark_ecommerce_paid()
        self.assertEqual(order.tijara_payment_status, "paid")
        self.assertGreater(order.partner_id.tijara_loyalty_points, 0)

    def test_delivery_adapter_label_manifest_cancel_and_webhook_flow(self):
        order = self.channel.tijara_create_order(
            {
                "audience": "b2c",
                "fulfillment_method": "delivery",
                "payment_method": "cod",
                "customer": {
                    "name": "Online Delivery Adapter Customer",
                    "mobile": "03001234568",
                    "email": "online-delivery-adapter@example.com",
                    "delivery_address": "Adapter test address",
                },
                "lines": [{"product_id": self.product.id, "quantity": 1}],
            }
        )
        label = self.provider.tijara_generate_label(order)
        self.assertEqual(label["format"], "pdf")
        self.assertEqual(order.tijara_delivery_adapter_state, "label_ready")
        self.assertTrue(order.tijara_delivery_label_payload)

        manifest = self.provider.tijara_create_manifest(order)
        self.assertEqual(order.tijara_delivery_manifest_reference, manifest["manifest_reference"])
        self.assertEqual(order.tijara_delivery_adapter_state, "manifested")

        result = self.provider.tijara_process_webhook(
            {
                "tracking_number": order.tijara_delivery_tracking_number,
                "status": "out_for_delivery",
            },
            headers={"X-Tijara-Delivery-Signature": "tijara-dry-run"},
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["signature_status"], "valid")
        self.assertEqual(order.tijara_delivery_status, "out_for_delivery")
        self.assertEqual(order.tijara_delivery_adapter_state, "webhook_synced")

        self.provider.tijara_cancel_shipment(order, reason="Customer cancelled")
        self.assertEqual(order.tijara_delivery_status, "cancelled")
        self.assertEqual(order.tijara_delivery_adapter_state, "cancelled")
        self.assertIn("Customer cancelled", order.tijara_delivery_exception_reason)
        events = self.env["tijara.ecommerce.delivery.event"].sudo().search([("sale_order_id", "=", order.id)])
        self.assertGreaterEqual(len(events), 4)

    def test_saas_enforcement_blocks_without_ecommerce_feature(self):
        self.env["ir.config_parameter"].sudo().set_param("tijara.saas.enforcement_enabled", "1")
        self.env["tijara.saas.subscription"].sudo().search([("company_id", "=", self.company.id)]).unlink()
        with self.assertRaises(UserError):
            self.channel.tijara_catalog_payload(audience="b2c")
        self.env["tijara.saas.subscription"].sudo().create(
            {
                "name": "Tijara Ecommerce Test Subscription",
                "tenant_name": self.company.name,
                "database_name": "tijara_test_ecommerce",
                "company_id": self.company.id,
                "customer_id": self.env["res.partner"].create({"name": "Tijara Ecommerce Billing"}).id,
                "plan_id": self.env.ref("tijara_saas_control.plan_enterprise").id,
                "state": "active",
                "start_date": fields.Date.context_today(self.env.user),
            }
        )
        payload = self.channel.tijara_catalog_payload(audience="b2c")
        self.assertEqual(payload["status"], "ok")

    def test_delivery_retry_sla_reconciliation_and_order_history(self):
        live_provider = self.env["tijara.ecommerce.delivery.provider"].sudo().create(
            {
                "name": "Tijara Test PostEx Live Assumption",
                "code": "TIJARA-TEST-POSTEX",
                "company_id": self.company.id,
                "adapter_profile": "postex",
                "provider_type": "aggregator",
                "service_level": "standard",
                "dry_run": False,
                "adapter_mode": "http_json",
                "auto_assign": True,
                "supports_cancel": True,
                "supports_labels": True,
                "supports_manifests": True,
                "supports_webhooks": True,
                "create_endpoint": "/shipments",
                "cancel_endpoint": "/shipments/{provider_reference}/cancel",
                "status_endpoint": "/shipments/{tracking_number}",
                "label_endpoint": "/shipments/{tracking_number}/label",
                "manifest_endpoint": "/manifests",
                "tracking_url_template": "https://tracking.example.test/postex/{tracking_number}",
                "retry_initial_delay_minutes": 1,
                "retry_max_attempts": 3,
                "provider_fee_flat": 100.0,
                "cod_fee_percent": 2.0,
            }
        )
        self.channel.write(
            {
                "delivery_provider_ids": [Command.set((self.provider | live_provider).ids)],
                "default_delivery_provider_id": live_provider.id,
            }
        )
        mobile = "03001234569"
        order = self.channel.tijara_create_order(
            {
                "audience": "b2c",
                "fulfillment_method": "delivery",
                "payment_method": "cod",
                "customer": {
                    "name": "Online Delivery Ops Customer",
                    "mobile": mobile,
                    "email": "online-delivery-ops@example.com",
                    "delivery_address": "Delivery ops address",
                },
                "lines": [{"product_id": self.product.id, "quantity": 1}],
            }
        )
        self.assertEqual(order.tijara_delivery_provider_id, live_provider)
        self.assertEqual(order.tijara_delivery_sla_state, "on_track")
        provider_payload = json.loads(order.tijara_delivery_provider_payload or "{}")
        self.assertEqual(provider_payload["adapter"]["profile"], "postex")
        self.assertEqual(provider_payload["adapter"]["credential_refs"]["api_token_ref"], "secret://tijara/delivery/TIJARA-TEST-POSTEX/api-token")
        self.assertEqual(provider_payload["provider_payload"]["orderReferenceNumber"], order.name)
        self.assertEqual(provider_payload["provider_payload"]["invoicePayment"], order.amount_total)
        retry = self.env["tijara.ecommerce.delivery.retry"].sudo().search(
            [("sale_order_id", "=", order.id), ("operation", "=", "shipment_create")],
            limit=1,
        )
        self.assertTrue(retry)
        self.assertEqual(retry.state, "pending")
        retry.action_run_now()
        self.assertEqual(retry.state, "done")
        self.assertEqual(retry.attempt_count, 1)
        self.assertTrue(retry.last_response_json)

        order.write({"tijara_delivery_sla_deadline": fields.Datetime.now() - timedelta(hours=1)})
        self.env["tijara.ecommerce.delivery.exception"].sudo().run_sla_monitor()
        exception = self.env["tijara.ecommerce.delivery.exception"].sudo().search(
            [
                ("sale_order_id", "=", order.id),
                ("category", "=", "sla_breach"),
                ("state", "in", ["open", "acknowledged"]),
            ],
            limit=1,
        )
        self.assertTrue(exception)
        self.assertEqual(exception.severity, "critical")
        self.assertEqual(order.tijara_delivery_sla_state, "breached")

        today = fields.Date.context_today(self.env.user)
        reconciliation = self.env["tijara.ecommerce.delivery.reconciliation"].sudo().create(
            {
                "provider_id": live_provider.id,
                "company_id": self.company.id,
                "date_from": today,
                "date_to": today,
            }
        )
        reconciliation.action_generate_lines()
        self.assertEqual(reconciliation.order_count, 1)
        self.assertEqual(reconciliation.cod_order_count, 1)
        self.assertGreater(reconciliation.cod_amount_total, 0.0)
        self.assertGreater(reconciliation.provider_fee_total, 0.0)
        self.assertTrue(reconciliation.report_json)
        reconciliation.action_mark_reviewed()
        self.assertEqual(reconciliation.state, "reviewed")
        reconciliation.action_approve()
        self.assertEqual(reconciliation.state, "approved")

        history = self.channel.tijara_order_history_payload({"mobile": mobile})
        self.assertEqual(history["status"], "ok")
        self.assertEqual(history["count"], 1)
        self.assertEqual(history["orders"][0]["name"], order.name)
        self.assertEqual(history["orders"][0]["delivery_profile"], "postex")
        self.assertEqual(history["orders"][0]["delivery_retry_count"], 1)
        self.assertEqual(history["orders"][0]["delivery_exception_count"], 1)

    def test_customer_account_saved_address_return_and_ecommerce_snapshots(self):
        mobile = "03001234570"
        order = self.channel.tijara_create_order(
            {
                "audience": "b2c",
                "fulfillment_method": "delivery",
                "payment_method": "cod",
                "customer": {
                    "name": "Online Portal Customer",
                    "mobile": mobile,
                    "email": "online-portal-customer@example.com",
                    "delivery_address": "Portal customer delivery address",
                    "loyalty_opt_in": True,
                },
                "lines": [{"product_id": self.product.id, "quantity": 2}],
            }
        )
        address_result = self.channel.tijara_save_customer_address(
            order.partner_id,
            {
                "name": "Home",
                "mobile": mobile,
                "street": "House 10, Test Block",
                "area": "Gulshan",
                "city": "Karachi",
                "default_delivery": True,
            },
        )
        self.assertEqual(address_result["status"], "ok")
        self.assertTrue(address_result["address"]["default_delivery"])

        account = self.channel.tijara_customer_account_payload(order.partner_id, limit=5)
        self.assertEqual(account["status"], "ok")
        self.assertEqual(account["addresses"][0]["name"], "Home")
        self.assertIn(order.name, [row["name"] for row in account["orders"]])

        return_result = self.channel.tijara_create_customer_return_request(
            order.partner_id,
            {
                "order_id": order.id,
                "reason": "Portal exchange size issue",
                "note": "Customer submitted from authenticated account portal.",
                "lines": [{"product_id": self.product.id, "quantity": 1}],
            },
        )
        self.assertEqual(return_result["status"], "ok")
        self.assertEqual(return_result["return_request"]["state"], "pending_approval")
        exchange_request = self.env["tijara.exchange.request"].sudo().browse(return_result["return_request"]["id"])
        self.assertEqual(exchange_request.original_order_ref, order.name)
        self.assertEqual(len(exchange_request.line_ids), 1)
        self.assertEqual(exchange_request.line_ids.product_id, self.product)

        self.env["tijara.analytics.snapshot"].sudo().action_collect_daily_snapshots()
        snapshots = self.env["tijara.analytics.snapshot"].sudo().search(
            [
                ("company_id", "=", self.company.id),
                ("snapshot_date", "=", fields.Date.context_today(self.env.user)),
                ("business_area", "=", "ecommerce"),
            ]
        )
        metric_types = set(snapshots.mapped("metric_type"))
        self.assertIn("ecommerce_order_pipeline", metric_types)
        self.assertIn("delivery_sla_breach_rate", metric_types)
        self.assertIn("delivery_retry_aging", metric_types)
        self.assertIn("courier_success_rate", metric_types)
        self.assertIn("cod_receivable_aging", metric_types)
        self.assertIn("delivery_reconciliation_variance", metric_types)
