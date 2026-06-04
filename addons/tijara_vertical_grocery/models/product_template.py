from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_grocery_category = fields.Selection(
        [
            ("fresh", "Fresh"),
            ("frozen", "Frozen"),
            ("dairy", "Dairy"),
            ("packaged", "Packaged"),
            ("household", "Household"),
            ("personal_care", "Personal Care"),
            ("other", "Other"),
        ],
        string="Grocery Category",
    )
    tijara_perishable = fields.Boolean(string="Perishable")
    tijara_shelf_life_days = fields.Integer(string="Shelf Life Days")
    tijara_cold_chain_required = fields.Boolean(string="Cold Chain Required")
    tijara_weigh_scale_plu = fields.Char(string="Weigh Scale PLU")
    tijara_loose_item = fields.Boolean(string="Loose Item")
    tijara_price_embedded_barcode = fields.Boolean(string="Price Embedded Barcode")
    tijara_freshness_check_required = fields.Boolean(string="Freshness Check Required")

