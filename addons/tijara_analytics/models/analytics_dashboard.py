from odoo import fields, models


class TijaraAnalyticsDashboard(models.Model):
    _name = "tijara.analytics.dashboard"
    _description = "Tijara Analytics Dashboard"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    audience = fields.Selection(
        [
            ("owner", "Owner / CEO"),
            ("branch_manager", "Branch Manager"),
            ("cashier_manager", "Cashier Manager"),
            ("inventory_manager", "Inventory Manager"),
            ("purchase_manager", "Purchase Manager"),
            ("accountant", "Accountant"),
        ],
        default="owner",
        required=True,
    )
    refresh_interval_minutes = fields.Integer(default=15)
    widget_ids = fields.One2many(
        "tijara.analytics.widget",
        "dashboard_id",
        string="Widgets",
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )


class TijaraAnalyticsWidget(models.Model):
    _name = "tijara.analytics.widget"
    _description = "Tijara Analytics Widget"
    _order = "dashboard_id, sequence, name"

    name = fields.Char(required=True)
    dashboard_id = fields.Many2one(
        "tijara.analytics.dashboard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    widget_type = fields.Selection(
        [
            ("kpi", "KPI"),
            ("trend", "Trend"),
            ("chart", "Chart"),
            ("graph", "Graph"),
            ("table", "Table"),
            ("alert", "Alert"),
        ],
        default="kpi",
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
        default="sales",
    )
    metric_code = fields.Char(required=True)
    feature_code = fields.Char(
        help="Optional SaaS feature code required to show this widget."
    )
    target_note = fields.Char(string="Target / Benchmark")
    query_note = fields.Text(string="Data Source Notes")
