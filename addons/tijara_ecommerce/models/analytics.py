from odoo import fields, models


class TijaraAnalyticsWidget(models.Model):
    _inherit = "tijara.analytics.widget"

    business_area = fields.Selection(
        selection_add=[("ecommerce", "Ecommerce")],
        ondelete={"ecommerce": "cascade"},
    )


class TijaraAnalyticsReport(models.Model):
    _inherit = "tijara.analytics.report"

    business_area = fields.Selection(
        selection_add=[("ecommerce", "Ecommerce")],
        ondelete={"ecommerce": "cascade"},
    )
