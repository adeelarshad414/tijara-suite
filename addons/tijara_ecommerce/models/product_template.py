from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_ecommerce_published = fields.Boolean(string="Publish on Tijara Ecommerce")
    tijara_ecommerce_featured = fields.Boolean(string="Featured Online")
    tijara_ecommerce_sequence = fields.Integer(string="Online Sequence", default=10)
    tijara_ecommerce_short_description_en = fields.Char(string="Online Short Description")
    tijara_ecommerce_short_description_ur = fields.Char(string="Online Urdu Description")
    tijara_ecommerce_meta_keywords = fields.Char(string="Online Search Keywords")
