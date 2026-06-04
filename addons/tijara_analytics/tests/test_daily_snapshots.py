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

