from datetime import datetime, time, timedelta

from odoo import api, fields, models


class TijaraAnalyticsSnapshot(models.Model):
    _name = "tijara.analytics.snapshot"
    _description = "Tijara Analytics KPI Snapshot"
    _order = "snapshot_date desc, business_area, metric_type"

    name = fields.Char(required=True)
    snapshot_date = fields.Date(default=fields.Date.context_today, required=True)
    period_type = fields.Selection(
        [
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
        ],
        default="day",
        required=True,
    )
    business_area = fields.Selection(
        [
            ("sales", "Sales"),
            ("pos", "POS"),
            ("purchase", "Purchase"),
            ("inventory", "Inventory"),
            ("customers", "Customers"),
            ("promotions", "Promotions"),
            ("finance", "Finance"),
            ("operations", "Operations"),
        ],
        required=True,
        index=True,
    )
    metric_type = fields.Selection(
        [
            ("revenue", "Revenue"),
            ("gross_margin", "Gross Margin"),
            ("orders", "Orders"),
            ("basket_size", "Basket Size"),
            ("refunds", "Refunds"),
            ("stock_value", "Stock Value"),
            ("stock_turnover", "Stock Turnover"),
            ("low_stock", "Low Stock"),
            ("expiry", "Expiry"),
            ("purchase_value", "Purchase Value"),
            ("supplier_lead_time", "Supplier Lead Time"),
            ("new_customers", "New Customers"),
            ("promotion_uplift", "Promotion Uplift"),
            ("queue_wait_time", "Queue Wait Time"),
            ("cash_variance", "Cash Variance"),
        ],
        required=True,
        index=True,
    )
    amount = fields.Monetary(currency_field="currency_id")
    quantity = fields.Float()
    count = fields.Integer()
    rate = fields.Float(string="Rate / Percentage")
    target_amount = fields.Monetary(currency_field="currency_id")
    target_quantity = fields.Float()
    target_count = fields.Integer()
    variance_amount = fields.Monetary(currency_field="currency_id")
    variance_rate = fields.Float()
    warehouse_id = fields.Many2one("stock.warehouse")
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
    notes = fields.Text()

    @api.model
    def action_collect_daily_snapshots(self):
        return self._collect_daily_snapshots()

    @api.model
    def _collect_daily_snapshots(self, snapshot_date=False):
        snapshot_date = snapshot_date or fields.Date.context_today(self)
        start = datetime.combine(fields.Date.to_date(snapshot_date), time.min)
        stop = start + timedelta(days=1)
        start_value = fields.Datetime.to_string(start)
        stop_value = fields.Datetime.to_string(stop)

        companies = self.env["res.company"].search([])
        for company in companies:
            self._collect_company_daily_snapshots(company, snapshot_date, start_value, stop_value)
        return True

    @api.model
    def _collect_company_daily_snapshots(self, company, snapshot_date, start_value, stop_value):
        PosOrder = self.env["pos.order"].sudo()
        order_domain = [
            ("company_id", "=", company.id),
            ("date_order", ">=", start_value),
            ("date_order", "<", stop_value),
            ("state", "in", ("paid", "done", "invoiced")),
        ]
        orders = PosOrder.search(order_domain)
        revenue = sum(orders.mapped("amount_total"))
        order_count = len(orders)
        refund_orders = orders.filtered(lambda order: order.amount_total < 0)
        basket_size = revenue / order_count if order_count else 0.0

        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Revenue",
            "pos",
            "revenue",
            amount=revenue,
            count=order_count,
            notes="Collected from paid/done/invoiced POS orders.",
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Orders",
            "pos",
            "orders",
            count=order_count,
            notes="Collected from paid/done/invoiced POS orders.",
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Basket Size",
            "pos",
            "basket_size",
            amount=basket_size,
            notes="Average POS order value.",
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Refunds",
            "pos",
            "refunds",
            amount=sum(refund_orders.mapped("amount_total")),
            count=len(refund_orders),
            notes="Negative-total POS orders.",
        )

        if "tijara.inventory.alert" in self.env.registry:
            Alert = self.env["tijara.inventory.alert"].sudo()
            low_count = Alert.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("new", "acknowledged")),
                    ("alert_type", "in", ("low_stock", "critical_stock")),
                ]
            )
            expiry_count = Alert.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("new", "acknowledged")),
                    ("alert_type", "=", "expiry"),
                ]
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Open Low Stock Alerts",
                "inventory",
                "low_stock",
                count=low_count,
                notes="Open low and critical stock alerts.",
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Open Expiry Alerts",
                "inventory",
                "expiry",
                count=expiry_count,
                notes="Open expiry alerts.",
            )

        if "tijara.queue.ticket" in self.env.registry:
            tickets = self.env["tijara.queue.ticket"].sudo().search(
                [
                    ("company_id", "=", company.id),
                    ("called_at", ">=", start_value),
                    ("called_at", "<", stop_value),
                ]
            )
            wait_minutes = []
            for ticket in tickets:
                if ticket.create_date and ticket.called_at:
                    wait_minutes.append(
                        (ticket.called_at - ticket.create_date).total_seconds() / 60.0
                    )
            average_wait = sum(wait_minutes) / len(wait_minutes) if wait_minutes else 0.0
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Average Queue Wait",
                "operations",
                "queue_wait_time",
                quantity=average_wait,
                count=len(wait_minutes),
                notes="Average minutes from ticket creation to call.",
            )

        if "tijara.promotion" in self.env.registry:
            promo_count = self.env["tijara.promotion"].sudo().search_count(
                [
                    ("company_id", "=", company.id),
                    ("active", "=", True),
                    "|",
                    ("start_at", "=", False),
                    ("start_at", "<=", stop_value),
                    "|",
                    ("end_at", "=", False),
                    ("end_at", ">=", start_value),
                ]
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Active Promotions",
                "promotions",
                "promotion_uplift",
                count=promo_count,
                notes="Active promotions/deals available during the period.",
            )

    @api.model
    def _upsert_snapshot(
        self,
        company,
        snapshot_date,
        name,
        business_area,
        metric_type,
        amount=0.0,
        quantity=0.0,
        count=0,
        rate=0.0,
        notes="",
    ):
        domain = [
            ("company_id", "=", company.id),
            ("snapshot_date", "=", snapshot_date),
            ("period_type", "=", "day"),
            ("business_area", "=", business_area),
            ("metric_type", "=", metric_type),
            ("warehouse_id", "=", False),
        ]
        values = {
            "name": name,
            "company_id": company.id,
            "snapshot_date": snapshot_date,
            "period_type": "day",
            "business_area": business_area,
            "metric_type": metric_type,
            "amount": amount,
            "quantity": quantity,
            "count": count,
            "rate": rate,
            "notes": notes,
        }
        snapshot = self.search(domain, limit=1)
        if snapshot:
            snapshot.write(values)
        else:
            self.create(values)
