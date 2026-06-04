from odoo import fields, models


class TijaraSaasPlan(models.Model):
    _name = "tijara.saas.plan"
    _description = "Tijara SaaS Plan"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    monthly_price = fields.Float(string="Monthly Price")
    annual_price = fields.Float(string="Annual Price")
    user_limit = fields.Integer(default=1)
    branch_limit = fields.Integer(default=1)
    product_limit = fields.Integer(default=1000)
    feature_ids = fields.Many2many(
        "tijara.saas.feature",
        "tijara_saas_plan_feature_rel",
        "plan_id",
        "feature_id",
        string="Features",
    )
    description = fields.Text()

