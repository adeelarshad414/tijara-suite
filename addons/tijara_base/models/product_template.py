from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_urdu_name = fields.Char(string="Urdu Name")
    tijara_local_sku = fields.Char(string="Local SKU")
    tijara_barcode_alias = fields.Char(string="Barcode Alias")
    tijara_hs_code = fields.Char(string="HS Code")
    tijara_label_name = fields.Char(string="Label Print Name")
    tijara_tax_category = fields.Selection(
        [
            ("standard", "Standard"),
            ("reduced", "Reduced"),
            ("exempt", "Exempt"),
            ("zero_rated", "Zero Rated"),
            ("custom", "Custom"),
        ],
        string="Pakistan Tax Category",
        default="standard",
    )
    tijara_is_weighed_item = fields.Boolean(string="Weighed Item")
    tijara_retail_unit = fields.Char(string="Retail Unit")

