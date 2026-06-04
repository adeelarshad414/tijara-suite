from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_style_code = fields.Char(string="Style Code")
    tijara_fabric = fields.Char(string="Fabric")
    tijara_season = fields.Char(string="Season")
    tijara_size_family = fields.Selection(
        [
            ("kids", "Kids"),
            ("women", "Women"),
            ("men", "Men"),
            ("unisex", "Unisex"),
            ("other", "Other"),
        ],
        string="Size Family",
    )
    tijara_color_code = fields.Char(string="Color Code")
    tijara_allow_alteration = fields.Boolean(string="Allow Alteration")

