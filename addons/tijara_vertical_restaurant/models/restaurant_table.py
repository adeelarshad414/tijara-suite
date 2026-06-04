from odoo import fields, models


class TijaraRestaurantTable(models.Model):
    _name = "tijara.restaurant.table"
    _description = "Tijara Restaurant Table"
    _order = "area, name"

    name = fields.Char(required=True)
    area = fields.Char(default="Main Floor")
    capacity = fields.Integer(default=4)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("available", "Available"),
            ("occupied", "Occupied"),
            ("reserved", "Reserved"),
            ("cleaning", "Cleaning"),
        ],
        default="available",
        required=True,
    )
    active = fields.Boolean(default=True)

