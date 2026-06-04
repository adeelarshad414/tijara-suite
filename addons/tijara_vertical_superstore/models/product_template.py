from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_superstore_department = fields.Char(string="Store Department")
    tijara_aisle = fields.Char(string="Aisle")
    tijara_shelf = fields.Char(string="Shelf")
    tijara_shelf_capacity = fields.Float(string="Shelf Capacity")
    tijara_case_pack_qty = fields.Float(string="Case Pack Quantity")
    tijara_inner_pack_qty = fields.Float(string="Inner Pack Quantity")
    tijara_promo_eligible = fields.Boolean(string="Promotion Eligible")
    tijara_loyalty_points = fields.Float(string="Loyalty Points")
    tijara_fast_moving_item = fields.Boolean(string="Fast Moving Item")

