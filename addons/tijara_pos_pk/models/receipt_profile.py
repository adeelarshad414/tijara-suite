from odoo import api, fields, models


class TijaraReceiptProfile(models.Model):
    _name = "tijara.receipt.profile"
    _inherit = ["pos.load.mixin"]
    _description = "Tijara Receipt Profile"
    _order = "company_id, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    template_scope = fields.Selection(
        [
            ("pos_receipt", "POS Receipt"),
            ("customer_invoice", "Customer Invoice"),
            ("refund_exchange", "Refund / Exchange"),
            ("quotation", "Quotation"),
        ],
        default="pos_receipt",
        required=True,
    )
    template_layout = fields.Selection(
        [
            ("compact", "Compact"),
            ("standard", "Standard"),
            ("detailed", "Detailed"),
            ("custom", "Custom HTML"),
        ],
        default="standard",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    language_mode = fields.Selection(
        [("en", "English"), ("ur", "Urdu"), ("both", "English + Urdu")],
        default="en",
        required=True,
    )
    printer_width = fields.Selection(
        [("58", "58mm"), ("80", "80mm"), ("a4", "A4"), ("custom", "Custom")],
        default="80",
        required=True,
    )
    show_qr = fields.Boolean(default=True)
    show_barcode = fields.Boolean(default=True)
    show_fbr_fields = fields.Boolean(default=False)
    show_logo = fields.Boolean(default=True)
    show_customer = fields.Boolean(default=True)
    show_cashier = fields.Boolean(default=True)
    show_tax_breakdown = fields.Boolean(default=True)
    show_discount_breakdown = fields.Boolean(default=True)
    show_payment_summary = fields.Boolean(default=True)
    show_company_ntn_strn = fields.Boolean(default=True)
    show_return_policy = fields.Boolean(default=True)
    barcode_source = fields.Selection(
        [
            ("tijara_invoice_barcode", "Tijara Invoice Barcode"),
            ("order_name", "Order / Invoice Number"),
            ("fbr_invoice_number", "FBR Invoice Number"),
            ("custom", "Custom Value"),
        ],
        default="tijara_invoice_barcode",
        required=True,
    )
    custom_barcode_value = fields.Char()
    printer_device_id = fields.Many2one(
        "tijara.hardware.device",
        domain="[('device_type', 'in', ('receipt_printer', 'label_printer'))]",
    )
    custom_width_mm = fields.Float(string="Custom Width mm")
    custom_height_mm = fields.Float(string="Custom Height mm")
    receipt_title_english = fields.Char(default="Sales Receipt")
    receipt_title_urdu = fields.Char()
    header_english = fields.Text()
    header_urdu = fields.Text()
    footer_english = fields.Text()
    footer_urdu = fields.Text()
    terms_english = fields.Text(string="Terms / Return Policy English")
    terms_urdu = fields.Text(string="Terms / Return Policy Urdu")
    custom_body_html = fields.Html(string="Custom Body HTML")
    custom_css = fields.Text(string="Custom CSS")
    internal_notes = fields.Text()

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [
            ("company_id", "=", config.company_id.id),
            ("template_scope", "=", "pos_receipt"),
            ("active", "=", True),
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        return [
            "id",
            "name",
            "active",
            "template_scope",
            "template_layout",
            "language_mode",
            "printer_width",
            "show_qr",
            "show_barcode",
            "show_fbr_fields",
            "show_logo",
            "show_customer",
            "show_cashier",
            "show_tax_breakdown",
            "show_discount_breakdown",
            "show_payment_summary",
            "show_company_ntn_strn",
            "show_return_policy",
            "barcode_source",
            "custom_barcode_value",
            "receipt_title_english",
            "receipt_title_urdu",
            "header_english",
            "header_urdu",
            "footer_english",
            "footer_urdu",
            "terms_english",
            "terms_urdu",
            "custom_body_html",
            "custom_css",
            "write_date",
        ]
