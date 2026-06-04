from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_quick_sale = fields.Boolean(string="Show in Quick Sale")
    tijara_min_stock_alert = fields.Float(string="Minimum Stock Alert")
    tijara_reorder_multiple = fields.Float(string="Reorder Multiple")
    tijara_b2c_price = fields.Float(string="B2C Retail Price")
    tijara_b2b_price = fields.Float(string="B2B Trade Price")
    tijara_b2b_min_qty = fields.Float(string="B2B Minimum Quantity")
    tijara_b2c_tax_included = fields.Boolean(string="B2C Price Includes Tax")
    tijara_b2b_tax_included = fields.Boolean(string="B2B Price Includes Tax")
    tijara_allow_refund = fields.Boolean(string="Allow Refund", default=True)
    tijara_allow_exchange = fields.Boolean(string="Allow Exchange", default=True)
    tijara_requires_manager_discount = fields.Boolean(
        string="Manager Approval for Discount"
    )
