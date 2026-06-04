from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_preferred_position_id = fields.Many2one(
        "tijara.storage.position",
        string="Preferred Storage Position",
    )
    tijara_expiry_alert_days = fields.Integer(
        string="Expiry Alert Days",
        default=30,
        help="Create expiry alerts this many days before lot expiration.",
    )
    tijara_inventory_critical_qty = fields.Float(string="Critical Stock Qty")
    tijara_cycle_count_frequency_days = fields.Integer(
        string="Cycle Count Frequency Days",
        default=30,
    )
    tijara_requires_temperature_control = fields.Boolean(
        string="Requires Temperature Control"
    )
    tijara_storage_note = fields.Text(string="Storage Notes")
