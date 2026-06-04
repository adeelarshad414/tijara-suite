from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_is_medicine = fields.Boolean(string="Medicine")
    tijara_generic_name = fields.Char(string="Generic Name")
    tijara_dosage_form = fields.Selection(
        [
            ("tablet", "Tablet"),
            ("capsule", "Capsule"),
            ("syrup", "Syrup"),
            ("injection", "Injection"),
            ("cream", "Cream/Ointment"),
            ("drops", "Drops"),
            ("other", "Other"),
        ],
        string="Dosage Form",
    )
    tijara_strength = fields.Char(string="Strength")
    tijara_manufacturer = fields.Char(string="Manufacturer")
    tijara_drug_registration_no = fields.Char(string="Drug Registration No.")
    tijara_pharmacy_mrp = fields.Float(string="MRP")
    tijara_requires_prescription = fields.Boolean(string="Requires Prescription")
    tijara_expiry_sensitive = fields.Boolean(string="Expiry Sensitive", default=True)

