from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    tijara_urdu_name = fields.Char(string="Urdu Name")
    tijara_cnic = fields.Char(string="CNIC")
    tijara_ntn = fields.Char(string="NTN")
    tijara_strn = fields.Char(string="STRN")
    tijara_customer_type = fields.Selection(
        [
            ("walk_in", "Walk-in"),
            ("retail", "Retail"),
            ("wholesale", "Wholesale"),
            ("corporate", "Corporate"),
            ("supplier", "Supplier"),
        ],
        string="Tijara Customer Type",
        default="retail",
    )
    tijara_is_walk_in = fields.Boolean(string="Walk-in Customer")
    tijara_credit_limit = fields.Float(string="Retail Credit Limit")
    tijara_loyalty_opt_in = fields.Boolean(string="Loyalty Opt-in")
    tijara_loyalty_number = fields.Char(string="Loyalty Number")
    tijara_loyalty_tier = fields.Selection(
        [
            ("standard", "Standard"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
        ],
        string="Loyalty Tier",
        default="standard",
    )
    tijara_loyalty_points = fields.Float(string="Loyalty Points")
