import json
from types import SimpleNamespace

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.tijara_pos_experience.controllers import display_routes


@tagged("post_install", "-at_install")
class TestTijaraDisplayRoutes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Tijara Display Tenant"})
        cls.customer = cls.env["res.partner"].create({"name": "Tijara Display Customer"})
        cls.enterprise_plan = cls.env.ref("tijara_saas_control.plan_enterprise")

    def setUp(self):
        super().setUp()
        self._original_request = display_routes.request
        display_routes.request = SimpleNamespace(env=self.env)
        self.env["ir.config_parameter"].sudo().set_param(
            "tijara.saas.enforcement_enabled",
            "1",
        )

    def tearDown(self):
        display_routes.request = self._original_request
        super().tearDown()

    def _create_menu_screen(self, slug):
        screen = self.env["tijara.display.screen"].create(
            {
                "name": "Test Menu Screen",
                "code": slug,
                "url_slug": slug,
                "display_type": "menu_board",
                "company_id": self.company.id,
                "price_mode": "b2c",
            }
        )
        promotion = self.env["tijara.promotion"].create(
            {
                "name": "Route Smoke Deal",
                "code": "ROUTE-SMOKE",
                "company_id": self.company.id,
                "show_on_menu_board": True,
            }
        )
        self.env["tijara.display.content"].create(
            {
                "name": "Route Smoke Item",
                "content_type": "deal",
                "title_english": "Route Smoke Item",
                "subtitle_english": "Visible from public display data",
                "b2c_price": 350,
                "promotion_id": promotion.id,
                "company_id": self.company.id,
                "screen_ids": [(6, 0, [screen.id])],
            }
        )
        return screen

    def _activate_enterprise_subscription(self, database_name, company=None):
        company = company or self.company
        return self.env["tijara.saas.subscription"].create(
            {
                "name": "Display Route Subscription",
                "tenant_name": company.name,
                "database_name": database_name,
                "customer_id": self.customer.id,
                "company_id": company.id,
                "plan_id": self.enterprise_plan.id,
                "state": "active",
            }
        )

    def _pos_config_with_payment_method(self, company):
        config = self.env["pos.config"].sudo().search(
            [("company_id", "=", company.id)],
            limit=1,
        )
        if not config:
            config = self.env["pos.config"].sudo().create(
                {"name": "Tijara Kiosk Sync POS", "company_id": company.id}
            )
        payment_method = config.payment_method_ids[:1] or self.env["pos.payment.method"].sudo().search(
            [("company_id", "=", company.id)],
            limit=1,
        )
        if not payment_method:
            self.skipTest("No POS payment method is available in this Odoo test database.")
        if payment_method not in config.payment_method_ids:
            config.write({"payment_method_ids": [(4, payment_method.id)]})
        return config, payment_method

    def test_display_controller_blocks_screen_without_plan_feature(self):
        screen = self._create_menu_screen("route-forbidden")
        controller = display_routes.TijaraDisplayController()

        self.assertFalse(controller._screen_allowed(screen))

    def test_display_controller_payload_after_enterprise_entitlement(self):
        screen = self._create_menu_screen("route-allowed")
        self._activate_enterprise_subscription("tijara_display_route_test")
        controller = display_routes.TijaraDisplayController()

        self.assertTrue(controller._screen_allowed(screen))
        payload = controller._screen_payload(screen)

        self.assertEqual(payload["screen"]["display_type"], "menu_board")
        self.assertEqual(payload["content"][0]["title_english"], "Route Smoke Item")
        self.assertEqual(payload["content"][0]["b2c_price"], 350)

    def test_kiosk_checkout_creates_submitted_order_and_queue_ticket(self):
        self._activate_enterprise_subscription("tijara_kiosk_checkout_test")
        screen = self.env["tijara.display.screen"].create(
            {
                "name": "Test Kiosk",
                "code": "kiosk-checkout",
                "url_slug": "kiosk-checkout",
                "display_type": "kiosk",
                "company_id": self.company.id,
                "price_mode": "b2c",
            }
        )
        self.env["tijara.kiosk.profile"].create(
            {
                "name": "Test Kiosk Profile",
                "screen_id": screen.id,
                "company_id": self.company.id,
                "allow_dine_in": True,
                "allow_takeaway": True,
                "allow_pickup": True,
                "allow_b2c": True,
                "allow_b2b": True,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Kiosk Test Bun",
                "lst_price": 120,
                "available_in_pos": True,
                "tijara_b2c_price": 120,
                "tijara_b2b_price": 100,
            }
        )
        content = self.env["tijara.display.content"].create(
            {
                "name": "Kiosk Test Bun",
                "content_type": "menu_item",
                "title_english": "Kiosk Test Bun",
                "product_id": product.id,
                "company_id": self.company.id,
                "screen_ids": [(6, 0, [screen.id])],
            }
        )
        controller = display_routes.TijaraDisplayController()

        payload = controller._screen_payload(screen)
        self.assertIn("kiosk", payload)
        self.assertEqual(payload["kiosk"]["items"][0]["title_english"], "Kiosk Test Bun")

        order = controller._create_kiosk_order_from_payload(
            screen,
            {
                "order_type": "takeaway",
                "audience": "b2c",
                "payment_method": "cash",
                "customer_name": "Walk In",
                "lines": [{"content_id": content.id, "qty": 2}],
            },
        )

        self.assertEqual(order.state, "submitted")
        self.assertAlmostEqual(order.amount_tax, 43.2)
        self.assertAlmostEqual(order.amount_total, 283.2)
        self.assertEqual(order.queue_ticket_id.source, "kiosk")
        self.assertEqual(order.queue_ticket_id.state, "waiting")

    def test_kiosk_checkout_syncs_to_pos_order_and_payment(self):
        company = self.env.company
        self._activate_enterprise_subscription("tijara_kiosk_pos_sync_test", company=company)
        config, payment_method = self._pos_config_with_payment_method(company)
        screen = self.env["tijara.display.screen"].create(
            {
                "name": "Test Kiosk POS Sync",
                "code": "kiosk-pos-sync",
                "url_slug": "kiosk-pos-sync",
                "display_type": "kiosk",
                "company_id": company.id,
                "price_mode": "b2c",
            }
        )
        self.env["tijara.kiosk.profile"].create(
            {
                "name": "Test Kiosk POS Profile",
                "screen_id": screen.id,
                "company_id": company.id,
                "allow_dine_in": True,
                "allow_takeaway": True,
                "allow_pickup": True,
                "allow_b2c": True,
                "auto_create_pos_order": True,
                "pos_config_id": config.id,
                "payment_capture_mode": "record_paid",
                "cash_payment_method_id": payment_method.id,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Kiosk POS Sync Tea",
                "lst_price": 180,
                "available_in_pos": True,
                "tijara_b2c_price": 180,
                "taxes_id": [(6, 0, [])],
            }
        )
        content = self.env["tijara.display.content"].create(
            {
                "name": "Kiosk POS Sync Tea",
                "content_type": "menu_item",
                "title_english": "Kiosk POS Sync Tea",
                "product_id": product.id,
                "company_id": company.id,
                "screen_ids": [(6, 0, [screen.id])],
            }
        )
        controller = display_routes.TijaraDisplayController()

        order = controller._create_kiosk_order_from_payload(
            screen,
            {
                "order_type": "takeaway",
                "audience": "b2c",
                "payment_method": "cash",
                "payment_status": "paid",
                "payment_reference": "KIOSK-CASH-001",
                "customer_name": "Kiosk POS Customer",
                "lines": [{"content_id": content.id, "qty": 1}],
            },
        )

        self.assertTrue(order.pos_order_id, order.pos_sync_error)
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.pos_order_id.state, "paid")
        self.assertEqual(order.pos_order_id.amount_total, 180)
        self.assertEqual(order.pos_payment_id.payment_method_id, payment_method)
        self.assertEqual(order.pos_payment_id.payment_ref_no, "KIOSK-CASH-001")

    def test_customer_display_payload_returns_live_order_state(self):
        self._activate_enterprise_subscription("tijara_customer_display_state_test")
        screen = self.env["tijara.display.screen"].create(
            {
                "name": "Test Customer Display",
                "code": "customer-display-live",
                "url_slug": "customer-display-live",
                "display_type": "customer_display",
                "company_id": self.company.id,
                "price_mode": "b2c",
            }
        )
        self.env["tijara.customer.display.state"].create(
            {
                "name": "Live Test State",
                "screen_id": screen.id,
                "status": "payment",
                "order_reference": "POS/TEST/001",
                "customer_name": "Walk In",
                "amount_subtotal": 500,
                "discount_amount": 25,
                "tax_amount": 0,
                "amount_total": 475,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Display Test Item",
                            "quantity": 1,
                            "price_unit": 500,
                            "price_subtotal": 500,
                        },
                    )
                ],
            }
        )
        controller = display_routes.TijaraDisplayController()

        payload = controller._screen_payload(screen)

        self.assertEqual(payload["customer_display"]["order_reference"], "POS/TEST/001")
        self.assertEqual(payload["customer_display"]["totals"]["total"], 475)
        self.assertEqual(payload["customer_display"]["lines"][0]["name"], "Display Test Item")

    def test_customer_display_frontend_publish_payload(self):
        self._activate_enterprise_subscription("tijara_customer_display_frontend_test")
        screen = self.env["tijara.display.screen"].create(
            {
                "name": "Frontend Customer Display",
                "code": "customer-display-frontend",
                "url_slug": "customer-display-frontend",
                "display_type": "customer_display",
                "company_id": self.company.id,
                "price_mode": "b2c",
            }
        )

        state = self.env["tijara.customer.display.state"].tijara_publish_frontend_order(
            screen,
            {
                "order_reference": "POS-FRONT-001",
                "cashier_name": "Cashier",
                "customer_name": "Walk In",
                "audience": "b2c",
                "order_type": "takeaway",
                "lines": [
                    {
                        "name": "Frontend Item",
                        "quantity": 2,
                        "price_unit": 150,
                        "subtotal": 300,
                    }
                ],
                "totals": {"subtotal": 300, "discount": 0, "tax": 0, "total": 300},
            },
            status="building",
        )

        self.assertEqual(state.order_reference, "POS-FRONT-001")
        self.assertEqual(state.amount_total, 300)
        self.assertEqual(state.line_ids.name, "Frontend Item")

    def test_offline_pos_queue_validates_payload_and_detects_duplicate(self):
        payload = '{"lines":[{"product_id":1,"qty":1}],"amount_total":100}'
        first = self.env["tijara.offline.pos.queue"].create(
            {
                "source_device_id": "tablet-1",
                "source_order_uid": "offline-001",
                "payload_json": payload,
                "company_id": self.env.company.id,
            }
        )
        second = self.env["tijara.offline.pos.queue"].create(
            {
                "source_device_id": "tablet-1",
                "source_order_uid": "offline-001-copy",
                "payload_json": payload,
                "company_id": self.env.company.id,
            }
        )

        first.action_validate_payload()
        second.action_validate_payload()

        self.assertEqual(first.state, "validated")
        self.assertEqual(second.state, "conflict")
        self.assertEqual(first.payload_hash, second.payload_hash)

    def test_offline_pos_review_actions_resolve_conflicts_and_cancellations(self):
        payload = json.dumps({"lines": [{"product_id": 1, "qty": 1, "price_unit": 100}], "amount_total": 100})
        queue_model = self.env["tijara.offline.pos.queue"]
        first = queue_model.create(
            {
                "source_device_id": "review-tablet",
                "source_order_uid": "review-offline-001",
                "payload_json": payload,
                "amount_total": 100,
                "company_id": self.env.company.id,
            }
        )
        second = queue_model.create(
            {
                "source_device_id": "review-tablet",
                "source_order_uid": "review-offline-002",
                "payload_json": payload,
                "amount_total": 100,
                "company_id": self.env.company.id,
            }
        )
        third = queue_model.create(
            {
                "source_device_id": "review-tablet",
                "source_order_uid": "review-offline-003",
                "payload_json": payload,
                "amount_total": 100,
                "company_id": self.env.company.id,
            }
        )

        first.action_validate_payload()
        second.action_validate_payload()
        third.action_validate_payload()

        self.assertEqual(second.state, "conflict")
        self.assertEqual(second.duplicate_of_queue_id, first)
        second.action_mark_duplicate()
        self.assertEqual(second.state, "duplicate")
        self.assertEqual(second.review_action, "duplicate")
        self.assertEqual(second.reviewed_by_id, self.env.user)

        third.action_merge_duplicate()
        self.assertEqual(third.state, "merged")
        self.assertTrue(third.merged_into_queue_id)
        self.assertEqual(third.review_action, "merge")

        failed = queue_model.create(
            {
                "source_device_id": "review-tablet",
                "source_order_uid": "review-offline-invalid",
                "payload_json": json.dumps({"lines": [], "amount_total": 0}),
                "company_id": self.env.company.id,
            }
        )
        failed.action_validate_payload()
        self.assertEqual(failed.state, "failed")
        failed.review_note = "Cashier cancelled duplicate paper trail"
        failed.action_cancel()
        self.assertEqual(failed.state, "cancelled")
        self.assertEqual(failed.review_action, "cancel")
        self.assertEqual(failed.reviewed_by_id, self.env.user)
        self.assertEqual(failed.pilot_attention_state, "resolved")

    def test_offline_pos_pilot_metrics_bucket_failed_payloads(self):
        queue = self.env["tijara.offline.pos.queue"].create(
            {
                "source_device_id": "pilot-tablet",
                "source_order_uid": "pilot-invalid-payload",
                "payload_json": json.dumps({"lines": [], "amount_total": 0}),
                "company_id": self.env.company.id,
            }
        )

        queue.action_validate_payload()

        self.assertEqual(queue.state, "failed")
        self.assertEqual(queue.pilot_attention_state, "blocked")
        self.assertEqual(queue.pilot_failure_bucket, "validation")
        self.assertGreaterEqual(queue.pilot_queue_age_minutes, 0)
        self.assertTrue(queue.pilot_metric_refreshed_at)

    def test_offline_pos_retry_replays_failed_valid_order(self):
        company = self.env.company
        config, payment_method = self._pos_config_with_payment_method(company)
        product = self.env["product.product"].create(
            {
                "name": "Offline Retry Review Item",
                "lst_price": 110,
                "available_in_pos": True,
                "taxes_id": [(6, 0, [])],
            }
        )

        result = self.env["tijara.offline.pos.queue"].tijara_capture_from_browser(
            {
                "source_app": "pos_frontend",
                "source_device_id": "offline-retry-tablet",
                "source_order_uid": "offline-retry-order-001",
                "pos_config_id": config.id,
                "payment_status": "paid",
                "payment_method_id": payment_method.id,
                "amount_total": 110,
                "amount_paid": 110,
                "payments": [{"amount": 110, "payment_method_id": payment_method.id}],
                "lines": [{"product_id": product.id, "qty": 1, "price_unit": 110}],
            },
            replay=False,
        )
        queue = self.env["tijara.offline.pos.queue"].browse(result["queue_id"])
        self.assertEqual(queue.state, "validated")

        queue.write({"state": "failed", "error_message": "Simulated staging retry failure"})
        queue.action_retry_replay()

        self.assertEqual(queue.state, "replayed", queue.error_message)
        self.assertEqual(queue.review_action, "retry")
        self.assertEqual(queue.replayed_pos_order_id.amount_total, 110)

    def test_offline_pos_capture_replays_to_paid_pos_order(self):
        company = self.env.company
        config, payment_method = self._pos_config_with_payment_method(company)
        product = self.env["product.product"].create(
            {
                "name": "Offline Replay Test Item",
                "lst_price": 95,
                "available_in_pos": True,
                "taxes_id": [(6, 0, [])],
            }
        )

        result = self.env["tijara.offline.pos.queue"].tijara_capture_from_browser(
            {
                "source_app": "pos_frontend",
                "source_device_id": "offline-tablet-1",
                "source_order_uid": "offline-order-001",
                "pos_config_id": config.id,
                "order_reference": "Offline Browser Order 001",
                "audience": "b2c",
                "order_type": "takeaway",
                "payment_status": "paid",
                "payment_method_id": payment_method.id,
                "amount_total": 190,
                "amount_paid": 190,
                "payments": [
                    {
                        "amount": 190,
                        "payment_method_id": payment_method.id,
                        "payment_reference": "OFFLINE-CASH-001",
                        "payment_status": "paid",
                    }
                ],
                "lines": [
                    {
                        "product_id": product.id,
                        "name": "Offline Replay Test Item",
                        "qty": 2,
                        "price_unit": 95,
                    }
                ],
            },
            replay=True,
        )

        queue = self.env["tijara.offline.pos.queue"].browse(result["queue_id"])
        self.assertEqual(queue.state, "replayed", queue.error_message)
        self.assertEqual(queue.replayed_pos_order_id.state, "paid")
        self.assertEqual(queue.replayed_pos_order_id.amount_total, 190)
        self.assertEqual(queue.replayed_pos_order_id.payment_ids.payment_ref_no, "OFFLINE-CASH-001")

    def test_offline_pos_capture_deduplicates_replayed_source_order(self):
        company = self.env.company
        config, payment_method = self._pos_config_with_payment_method(company)
        product = self.env["product.product"].create(
            {
                "name": "Offline Replay Duplicate Item",
                "lst_price": 80,
                "available_in_pos": True,
                "taxes_id": [(6, 0, [])],
            }
        )
        payload = {
            "source_device_id": "offline-tablet-duplicate",
            "source_order_uid": "offline-order-duplicate",
            "pos_config_id": config.id,
            "payment_status": "paid",
            "payment_method_id": payment_method.id,
            "payments": [{"amount": 80, "payment_method_id": payment_method.id}],
            "lines": [{"product_id": product.id, "qty": 1, "price_unit": 80}],
        }

        first = self.env["tijara.offline.pos.queue"].tijara_capture_from_browser(payload, replay=True)
        second = self.env["tijara.offline.pos.queue"].tijara_capture_from_browser(payload, replay=True)

        self.assertEqual(first["queue_state"], "replayed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(first["pos_order_id"], second["pos_order_id"])
