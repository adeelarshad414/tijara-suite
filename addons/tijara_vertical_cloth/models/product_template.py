from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_is_fabric = fields.Boolean(string="Fabric Item")
    tijara_fabric_type = fields.Selection(
        [
            ("cotton", "Cotton"),
            ("lawn", "Lawn"),
            ("linen", "Linen"),
            ("silk", "Silk"),
            ("khaddar", "Khaddar"),
            ("wash_wear", "Wash & Wear"),
            ("denim", "Denim"),
            ("other", "Other"),
        ],
        string="Fabric Type",
    )
    tijara_sale_by_meter = fields.Boolean(string="Sale by Meter/Yard")
    tijara_measure_unit = fields.Selection(
        [("meter", "Meter"), ("yard", "Yard")],
        string="Measurement Unit",
        default="meter",
    )
    tijara_roll_number = fields.Char(string="Roll Number")
    tijara_roll_length = fields.Float(string="Roll Length")
    tijara_cutting_loss_percent = fields.Float(string="Cutting Loss %")
    tijara_tailoring_available = fields.Boolean(string="Tailoring Available")
    tijara_tailoring_days = fields.Integer(string="Tailoring Days")

