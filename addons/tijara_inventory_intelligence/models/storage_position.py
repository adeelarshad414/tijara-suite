from odoo import api, fields, models


class TijaraStoragePosition(models.Model):
    _name = "tijara.storage.position"
    _description = "Tijara Storage Position"
    _order = "warehouse_id, location_id, aisle, rack, shelf, bin"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse")
    location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        domain="[('usage', '=', 'internal')]",
    )
    zone = fields.Char(string="Zone")
    aisle = fields.Char(string="Aisle")
    rack = fields.Char(string="Rack")
    shelf = fields.Char(string="Shelf")
    bin = fields.Char(string="Bin")
    barcode = fields.Char(string="Location Barcode / QR")
    capacity_qty = fields.Float(string="Capacity")
    preferred_min_qty = fields.Float(string="Preferred Minimum Qty")
    temperature_zone = fields.Selection(
        [
            ("ambient", "Ambient"),
            ("cool", "Cool"),
            ("cold", "Cold"),
            ("frozen", "Frozen"),
            ("controlled", "Controlled"),
        ],
        default="ambient",
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        for position in self:
            if position.warehouse_id:
                position.company_id = position.warehouse_id.company_id
