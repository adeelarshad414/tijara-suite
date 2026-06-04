from urllib.parse import quote

from markupsafe import Markup, escape

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    tijara_invoice_profile_id = fields.Many2one(
        "tijara.receipt.profile",
        string="Tijara Invoice Template",
        domain="[('template_scope', 'in', ('customer_invoice', 'refund_exchange')), ('active', '=', True)]",
        help="Optional template override for Tijara customer invoice reports.",
    )
    tijara_invoice_barcode = fields.Char(
        string="Tijara Invoice Barcode",
        compute="_compute_tijara_invoice_barcode",
        store=True,
    )

    @api.depends("name", "ref", "payment_reference")
    def _compute_tijara_invoice_barcode(self):
        for move in self:
            reference = move.name if move.name and move.name != "/" else move.ref or move.payment_reference or move.id
            move.tijara_invoice_barcode = f"TJINV:{reference}"

    def action_tijara_print_invoice_template(self):
        return self.env.ref("tijara_pos_pk.action_report_tijara_customer_invoice").report_action(self)

    def tijara_get_receipt_profile(self):
        self.ensure_one()
        scope = "refund_exchange" if self.move_type == "out_refund" else "customer_invoice"
        if self.tijara_invoice_profile_id and self.tijara_invoice_profile_id.template_scope in (scope, "customer_invoice"):
            return self.tijara_invoice_profile_id
        return self.env["tijara.receipt.profile"].sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("template_scope", "=", scope),
                ("active", "=", True),
            ],
            limit=1,
        )

    def tijara_barcode_value(self, profile=False):
        self.ensure_one()
        profile = profile or self.tijara_get_receipt_profile()
        if profile and profile.barcode_source == "custom":
            return profile.custom_barcode_value
        if profile and profile.barcode_source == "order_name":
            return self.name if self.name != "/" else self.ref
        if profile and profile.barcode_source == "fbr_invoice_number":
            return getattr(self, "tijara_fbr_invoice_number", False) or self.ref or self.name
        return self.tijara_invoice_barcode

    def tijara_barcode_url(self, profile=False, barcode_type="Code128", width=600, height=120):
        value = self.tijara_barcode_value(profile)
        if not value:
            return False
        return f"/report/barcode/{barcode_type}/{quote(str(value))}?width={width}&height={height}"

    def tijara_document_number(self):
        self.ensure_one()
        return self.name if self.name and self.name != "/" else self.ref or ""

    def tijara_document_date(self):
        self.ensure_one()
        return self.invoice_date or self.date

    def tijara_document_partner_name(self):
        self.ensure_one()
        return self.partner_id.display_name or "Walk-in"

    def tijara_document_user_name(self):
        self.ensure_one()
        return self.invoice_user_id.display_name or self.create_uid.display_name or ""

    def tijara_report_lines(self):
        self.ensure_one()
        return [
            {
                "name": line.name or line.product_id.display_name,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "subtotal": line.price_subtotal,
                "total": line.price_total,
            }
            for line in self.invoice_line_ids.filtered(lambda line: line.display_type == "product")
        ]

    def tijara_payment_summary(self):
        self.ensure_one()
        return [
            {"name": "Payment Status", "amount": self.amount_total - self.amount_residual},
            {"name": "Balance Due", "amount": self.amount_residual},
        ]

    def tijara_render_custom_body(self, profile=False):
        self.ensure_one()
        profile = profile or self.tijara_get_receipt_profile()
        if not profile or not profile.custom_body_html:
            return Markup("")
        replacements = {
            "document_number": self.name if self.name != "/" else self.ref or "",
            "document_date": self.invoice_date or self.date or "",
            "customer_name": self.partner_id.display_name or "",
            "cashier_name": self.invoice_user_id.display_name or self.create_uid.display_name or "",
            "company_name": self.company_id.display_name or "",
            "amount_total": self.amount_total,
            "amount_tax": self.amount_tax,
            "barcode_value": self.tijara_barcode_value(profile) or "",
        }
        return self._tijara_replace_template_tokens(profile.custom_body_html, replacements)

    def _tijara_replace_template_tokens(self, html, replacements):
        rendered = html or ""
        for key, value in replacements.items():
            rendered = rendered.replace("{{ %s }}" % key, str(escape(value)))
            rendered = rendered.replace("{{%s}}" % key, str(escape(value)))
        return Markup(rendered)
