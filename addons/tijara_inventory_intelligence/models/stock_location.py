from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    tijara_zone = fields.Char(string="Tijara Zone")
    tijara_aisle = fields.Char(string="Aisle")
    tijara_rack = fields.Char(string="Rack")
    tijara_shelf = fields.Char(string="Shelf")
    tijara_bin = fields.Char(string="Bin")
    tijara_location_barcode = fields.Char(string="Location Barcode / QR")
    tijara_capacity_qty = fields.Float(string="Capacity")
    tijara_is_front_shelf = fields.Boolean(string="Front Shelf")
    tijara_temperature_zone = fields.Selection(
        [
            ("ambient", "Ambient"),
            ("cool", "Cool"),
            ("cold", "Cold"),
            ("frozen", "Frozen"),
            ("controlled", "Controlled"),
        ],
        string="Temperature Zone",
        default="ambient",
    )
    tijara_picking_priority = fields.Selection(
        [
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Picking Priority",
        default="normal",
    )
