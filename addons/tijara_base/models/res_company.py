from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tijara_urdu_name = fields.Char(string="Urdu Name")
    tijara_ntn = fields.Char(string="NTN")
    tijara_strn = fields.Char(string="STRN")
    tijara_branch_code = fields.Char(string="Branch Code")
    tijara_business_type = fields.Selection(
        [
            ("superstore", "Superstore"),
            ("grocery", "Grocery Store"),
            ("bakery", "Bakery"),
            ("cloth", "Cloth/Fabric"),
            ("pharmacy", "Pharmacy"),
            ("restaurant", "Restaurant"),
            ("garments", "Garments"),
            ("electronics", "Electronics"),
            ("wholesale", "Wholesale"),
            ("other", "Other"),
        ],
        string="Business Type",
        default="superstore",
    )
    tijara_receipt_language = fields.Selection(
        [("en", "English"), ("ur", "Urdu"), ("both", "English + Urdu")],
        string="Receipt Language",
        default="en",
    )
    tijara_fbr_pos_enabled = fields.Boolean(string="FBR POS Enabled")
    tijara_fbr_pos_id = fields.Char(string="FBR POS ID")
    tijara_fiscal_device_id = fields.Char(string="Fiscal Device ID")
