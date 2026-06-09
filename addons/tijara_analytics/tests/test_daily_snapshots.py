from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraAnalyticsSnapshots(TransactionCase):
    def test_daily_collector_creates_core_kpi_snapshots(self):
        snapshot_date = fields.Date.context_today(self.env.user)
        self.env["tijara.promotion"].create(
            {
                "name": "Collector Smoke Promotion",
                "code": "COLLECTOR-SMOKE",
                "company_id": self.env.company.id,
                "show_on_deals_board": True,
            }
        )

        self.env["tijara.analytics.snapshot"].action_collect_daily_snapshots()

        snapshots = self.env["tijara.analytics.snapshot"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("snapshot_date", "=", snapshot_date),
                ("period_type", "=", "day"),
            ]
        )
        metric_types = set(snapshots.mapped("metric_type"))

        self.assertIn("revenue", metric_types)
        self.assertIn("orders", metric_types)
        self.assertIn("basket_size", metric_types)
        self.assertIn("promotion_uplift", metric_types)

        promotion_snapshot = snapshots.filtered(
            lambda snapshot: snapshot.metric_type == "promotion_uplift"
        )[:1]
        self.assertGreaterEqual(promotion_snapshot.count, 1)

    def test_daily_collector_creates_enterprise_kpi_snapshots(self):
        required_models = {
            "tijara.expense.request",
            "tijara.salary.batch",
            "tijara.kiosk.order",
        }
        missing_models = required_models - set(self.env.registry)
        if missing_models:
            self.skipTest("Optional enterprise models are not installed: %s" % missing_models)

        snapshot_date = fields.Date.context_today(self.env.user)
        company = self.env.company
        company.write(
            {
                "tijara_business_type": "cafe",
                "tijara_gst_enabled": True,
                "tijara_service_charge_enabled": True,
                "tijara_service_charge_percent": 10.0,
                "tijara_delivery_charge_enabled": True,
                "tijara_delivery_charge_amount": 50.0,
                "tijara_food_payment_tax_enabled": True,
                "tijara_food_card_tax_percent": 5.0,
                "tijara_food_cash_tax_percent": 16.0,
                "tijara_loyalty_enabled": True,
            }
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Enterprise KPI Loyalty Customer",
                "company_id": company.id,
                "tijara_loyalty_opt_in": True,
                "tijara_loyalty_tier": "gold",
                "tijara_loyalty_points": 250.0,
            }
        )
        self.env["tijara.expense.request"].create(
            {
                "name": "Collector Expense",
                "company_id": company.id,
                "expense_date": snapshot_date,
                "requested_by_id": self.env.user.id,
                "category": "delivery",
                "payment_method": "cash",
                "amount": 1000.0,
                "tax_amount": 180.0,
                "state": "approved",
            }
        )
        self.env["tijara.salary.batch"].create(
            {
                "name": "Collector Salary",
                "company_id": company.id,
                "period_start": snapshot_date,
                "period_end": snapshot_date,
                "state": "approved",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "employee_id": partner.id,
                            "role": "Cashier",
                            "gross_amount": 50000.0,
                            "deduction_amount": 2500.0,
                            "bonus_amount": 1000.0,
                        },
                    )
                ],
            }
        )
        product = self.env["product.template"].create(
            {
                "name": "Enterprise KPI Cafe Item",
                "type": "consu",
                "sale_ok": True,
                "available_in_pos": True,
                "list_price": 200.0,
                "tijara_vertical_tag": "cafe",
                "tijara_b2c_price": 220.0,
                "tijara_b2b_price": 180.0,
                "taxes_id": [(6, 0, [])],
            }
        )
        screen = self.env["tijara.display.screen"].create(
            {
                "name": "Collector Kiosk Screen",
                "code": "collector-kiosk",
                "company_id": company.id,
                "display_type": "kiosk",
                "url_slug": "collector-kiosk",
            }
        )
        profile = self.env["tijara.kiosk.profile"].create(
            {
                "name": "Collector Kiosk Profile",
                "company_id": company.id,
                "screen_id": screen.id,
                "allow_delivery": True,
                "allow_card": True,
                "auto_create_queue_ticket": False,
            }
        )
        self.env["tijara.kiosk.order"].create(
            {
                "profile_id": profile.id,
                "screen_id": screen.id,
                "company_id": company.id,
                "partner_id": partner.id,
                "customer_name": partner.name,
                "order_type": "delivery",
                "payment_method": "card",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.product_variant_id.id,
                            "name": product.name,
                            "quantity": 2.0,
                            "price_unit": 200.0,
                        },
                    )
                ],
            }
        ).action_submit()

        self.env["tijara.analytics.snapshot"].action_collect_daily_snapshots()
        snapshots = self.env["tijara.analytics.snapshot"].search(
            [
                ("company_id", "=", company.id),
                ("snapshot_date", "=", snapshot_date),
                ("period_type", "=", "day"),
            ]
        )
        metrics = set(snapshots.mapped("metric_type"))

        for metric in {
            "expense_state_totals",
            "salary_net_payable",
            "loyalty_points_liability",
            "vertical_catalog_coverage",
            "vertical_b2b_b2c_margin",
            "restaurant_order_type_mix",
            "food_service_charge_tax_audit",
            "customer_repeat_visit_history",
        }:
            self.assertIn(metric, metrics)

        expense_snapshot = snapshots.filtered(
            lambda snapshot: snapshot.metric_type == "expense_state_totals"
        )[:1]
        salary_snapshot = snapshots.filtered(
            lambda snapshot: snapshot.metric_type == "salary_net_payable"
        )[:1]
        charge_snapshot = snapshots.filtered(
            lambda snapshot: snapshot.metric_type == "food_service_charge_tax_audit"
        )[:1]

        self.assertGreaterEqual(expense_snapshot.amount, 1180.0)
        self.assertAlmostEqual(salary_snapshot.amount, 48500.0)
        self.assertGreater(charge_snapshot.amount, 0.0)
