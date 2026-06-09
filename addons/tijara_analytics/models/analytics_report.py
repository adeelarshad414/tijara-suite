from odoo import fields, models


class TijaraAnalyticsReport(models.Model):
    _name = "tijara.analytics.report"
    _description = "Tijara Analytics Report Catalog"
    _order = "business_area, sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
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
            ("backoffice", "Back Office"),
            ("payroll", "Payroll"),
            ("loyalty", "Loyalty"),
            ("food_service", "Food Service"),
            ("verticals", "Vertical Retail"),
            ("tax_policy", "Tax and Charges"),
        ],
        required=True,
    )
    report_type = fields.Selection(
        [
            ("dashboard", "Dashboard"),
            ("list", "List"),
            ("pivot", "Pivot"),
            ("graph", "Graph"),
            ("export", "Export"),
            ("scheduled", "Scheduled"),
        ],
        default="dashboard",
        required=True,
    )
    frequency = fields.Selection(
        [
            ("realtime", "Realtime"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
        ],
        default="daily",
    )
    owner_role = fields.Char(string="Owner Role")
    feature_code = fields.Char(
        help="Optional SaaS feature code required to enable this report."
    )
    description = fields.Text()
    acceptance_notes = fields.Text()
