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
            ("cosmetics", "Cosmetics"),
            ("bakery", "Bakery"),
            ("cloth", "Cloth/Fabric"),
            ("pharmacy", "Pharmacy"),
            ("cafe", "Cafe"),
            ("fast_food", "Fast Food"),
            ("restaurant", "Restaurant"),
            ("garments", "Garments"),
            ("uniform", "Uniform Store"),
            ("shoes", "Shoes Brand / Store"),
            ("mobile_shop", "Mobile Shop"),
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
    tijara_gst_enabled = fields.Boolean(
        string="GST Enabled",
        default=True,
        help="Controls whether Tijara demo/seed products should use the standard Pakistan GST tax.",
    )
    tijara_service_charge_enabled = fields.Boolean(
        string="Service Charge Enabled",
        help="Cafe-only policy flag used by kiosk/POS order foundations.",
    )
    tijara_service_charge_percent = fields.Float(
        string="Service Charge %",
        default=7.5,
    )
    tijara_delivery_charge_enabled = fields.Boolean(string="Delivery Charge Enabled")
    tijara_delivery_charge_amount = fields.Float(
        string="Delivery Charge Amount",
        default=150.0,
    )
    tijara_food_payment_tax_enabled = fields.Boolean(
        string="Cafe/Restaurant Payment Tax Enabled",
        help="Applies only to cafe, fast food, and restaurant business types.",
    )
    tijara_food_card_tax_percent = fields.Float(string="Card Tax %", default=5.0)
    tijara_food_cash_tax_percent = fields.Float(string="Cash Tax %", default=16.0)
    tijara_loyalty_enabled = fields.Boolean(string="Loyalty Program Enabled")
    tijara_loyalty_points_per_currency = fields.Float(
        string="Loyalty Points per Currency",
        default=0.01,
    )

    def tijara_is_food_service_business(self):
        self.ensure_one()
        return self.tijara_business_type in {"cafe", "fast_food", "restaurant"}

    def tijara_has_cafe_service_charge_policy(self):
        self.ensure_one()
        return self.tijara_business_type == "cafe"

    def tijara_has_cafe_restaurant_payment_tax_policy(self):
        self.ensure_one()
        return self.tijara_business_type in {"cafe", "restaurant"}
