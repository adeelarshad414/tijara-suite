from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_bakery_item = fields.Boolean(string="Bakery Item")
    tijara_bakery_category = fields.Selection(
        [
            ("bread", "Bread"),
            ("cake", "Cake"),
            ("pastry", "Pastry"),
            ("biscuit", "Biscuit"),
            ("sweet", "Sweet"),
            ("savory", "Savory"),
            ("other", "Other"),
        ],
        string="Bakery Category",
    )
    tijara_recipe_code = fields.Char(string="Recipe Code")
    tijara_bake_time_minutes = fields.Integer(string="Bake Time Minutes")
    tijara_shelf_life_hours = fields.Integer(string="Shelf Life Hours")
    tijara_made_to_order = fields.Boolean(string="Made to Order")
    tijara_allergen_notes = fields.Text(string="Allergen Notes")

