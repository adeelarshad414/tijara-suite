from odoo import fields, models


class TijaraSaasFeature(models.Model):
    _name = "tijara.saas.feature"
    _description = "Tijara SaaS Feature"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    module_name = fields.Char(
        help="Optional Odoo module technical name that provides this feature."
    )
    description = fields.Text()

