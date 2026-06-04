from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_warranty_months = fields.Integer(string="Warranty Months")
    tijara_serial_required = fields.Boolean(string="Serial Required")
    tijara_imei_required = fields.Boolean(string="IMEI Required")
    tijara_installation_required = fields.Boolean(string="Installation Required")
    tijara_warranty_provider = fields.Char(string="Warranty Provider")
    tijara_warranty_terms = fields.Text(string="Warranty Terms")

