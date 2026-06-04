import json
from urllib.parse import quote

from markupsafe import Markup, escape

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    tijara_fbr_invoice_number = fields.Char(string="FBR Invoice Number")
    tijara_fbr_qr_payload = fields.Text(string="FBR QR Payload")
    tijara_exchange_origin_ref = fields.Char(string="Exchange Origin")
    tijara_is_refund_exchange = fields.Boolean(string="Refund/Exchange Order")
    tijara_invoice_barcode = fields.Char(
        string="Tijara Invoice Barcode",
        compute="_compute_tijara_invoice_barcode",
        store=True,
    )
    tijara_bridge_print_job_id = fields.Char(string="Bridge Print Job")
    tijara_bridge_print_status = fields.Selection(
        [
            ("not_sent", "Not Sent"),
            ("accepted", "Accepted"),
            ("error", "Error"),
        ],
        default="not_sent",
        string="Bridge Print Status",
    )
    tijara_bridge_print_result = fields.Text(string="Bridge Print Result")
    tijara_bridge_printed_at = fields.Datetime(string="Bridge Printed At")

    @api.depends("name", "tijara_fbr_invoice_number")
    def _compute_tijara_invoice_barcode(self):
        for order in self:
            order.tijara_invoice_barcode = (
                f"TJINV:{order.tijara_fbr_invoice_number or order.name or order.id}"
            )

    def action_tijara_print_receipt_template(self):
        return self.env.ref("tijara_pos_pk.action_report_tijara_pos_receipt").report_action(self)

    def action_tijara_print_receipt_to_bridge(self, receipt_payload):
        self.ensure_one()
        device = (
            self.config_id.tijara_receipt_printer_device_id
            or self.tijara_get_receipt_profile().printer_device_id
        )
        if not device:
            return {
                "successful": False,
                "message": {
                    "title": "Tijara Bridge Printer",
                    "body": "No Tijara bridge receipt printer is configured for this POS.",
                },
            }
        if device.device_type != "receipt_printer" or device.connection_type != "browser_bridge":
            return {
                "successful": False,
                "message": {
                    "title": "Tijara Bridge Printer",
                    "body": "Configured receipt printer must be a browser bridge receipt printer.",
                },
            }
        profile = self.tijara_get_receipt_profile()
        payload = dict(receipt_payload or {})
        payload.update(
            {
                "source": "odoo_pos_browser",
                "order_id": self.id,
                "order_name": self.name,
                "order_uuid": self.uuid,
                "company_id": self.company_id.id,
                "company_name": self.company_id.display_name,
                "config_id": self.config_id.id,
                "config_name": self.config_id.display_name,
                "receipt_profile_id": profile.id if profile else False,
                "receipt_profile_name": profile.display_name if profile else False,
                "barcode_value": self.tijara_barcode_value(profile) or "",
                "amount_total": self.amount_total,
                "amount_tax": self.amount_tax,
                "currency": self.currency_id.name,
            }
        )
        response = device.sudo().tijara_submit_bridge_job(
            "print_receipt",
            payload,
            "/v1/print/receipt",
        )
        status = "accepted" if response.get("status") == "accepted" else "error"
        self.write(
            {
                "tijara_bridge_print_job_id": response.get("job_id") or False,
                "tijara_bridge_print_status": status,
                "tijara_bridge_print_result": json.dumps(response, indent=2, ensure_ascii=False),
                "tijara_bridge_printed_at": fields.Datetime.now(),
            }
        )
        return {
            "successful": status == "accepted",
            "job_id": response.get("job_id"),
            "message": {
                "title": "Tijara Bridge Printer",
                "body": "Receipt job accepted by local bridge.",
            },
            "bridge_response": response,
        }

    @api.model
    def _load_pos_data_fields(self, config):
        field_names = super()._load_pos_data_fields(config)
        base_order_fields = [
            "name",
            "date_order",
            "user_id",
            "partner_id",
            "session_id",
            "config_id",
            "company_id",
            "pricelist_id",
            "fiscal_position_id",
            "preset_id",
            "floating_order_name",
            "state",
            "uuid",
            "access_token",
            "nb_print",
            "to_invoice",
            "shipping_date",
            "last_order_preparation_change",
            "general_customer_note",
            "internal_note",
            "amount_total",
            "amount_tax",
            "amount_paid",
            "amount_return",
            "lines",
            "payment_ids",
            "write_date",
        ]
        tijara_fields = [
            "tijara_fbr_invoice_number",
            "tijara_fbr_qr_payload",
            "tijara_invoice_barcode",
            "tijara_exchange_origin_ref",
            "tijara_is_refund_exchange",
        ]
        requested_fields = field_names + base_order_fields + tijara_fields
        fields_to_load = []
        for field in requested_fields:
            if field in self._fields and field not in fields_to_load:
                fields_to_load.append(field)
        return fields_to_load

    def tijara_get_receipt_profile(self):
        self.ensure_one()
        if self.config_id.tijara_receipt_profile_id:
            return self.config_id.tijara_receipt_profile_id
        return self.env["tijara.receipt.profile"].sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("template_scope", "=", "pos_receipt"),
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
            return self.name
        if profile and profile.barcode_source == "fbr_invoice_number":
            return self.tijara_fbr_invoice_number or self.name
        return self.tijara_invoice_barcode

    def tijara_barcode_url(self, profile=False, barcode_type="Code128", width=600, height=120):
        value = self.tijara_barcode_value(profile)
        if not value:
            return False
        return f"/report/barcode/{barcode_type}/{quote(str(value))}?width={width}&height={height}"

    def tijara_document_number(self):
        self.ensure_one()
        return self.name or ""

    def tijara_document_date(self):
        self.ensure_one()
        return self.date_order

    def tijara_document_partner_name(self):
        self.ensure_one()
        return self.partner_id.display_name or "Walk-in"

    def tijara_document_user_name(self):
        self.ensure_one()
        return self.user_id.display_name or self.create_uid.display_name or ""

    def tijara_report_lines(self):
        self.ensure_one()
        discount_product = self.config_id.discount_product_id
        lines = []
        for line in self.lines:
            if not line.product_id or (discount_product and line.product_id == discount_product):
                continue
            lines.append(
                {
                    "name": line.product_id.display_name,
                    "quantity": line.qty,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "subtotal": line.price_subtotal,
                    "total": line.price_subtotal_incl,
                }
            )
        return lines

    def tijara_payment_summary(self):
        self.ensure_one()
        return [
            {
                "name": payment.payment_method_id.name,
                "amount": payment.amount,
            }
            for payment in self.payment_ids
        ]

    def tijara_render_custom_body(self, profile=False):
        self.ensure_one()
        profile = profile or self.tijara_get_receipt_profile()
        if not profile or not profile.custom_body_html:
            return Markup("")
        replacements = {
            "document_number": self.name or "",
            "document_date": self.date_order or "",
            "customer_name": self.partner_id.display_name or "Walk-in",
            "cashier_name": self.user_id.display_name or self.create_uid.display_name or "",
            "company_name": self.company_id.display_name or "",
            "amount_total": self.amount_total,
            "amount_tax": self.amount_tax,
            "barcode_value": self.tijara_barcode_value(profile) or "",
            "fbr_invoice_number": self.tijara_fbr_invoice_number or "",
        }
        return self._tijara_replace_template_tokens(profile.custom_body_html, replacements)

    def _tijara_replace_template_tokens(self, html, replacements):
        rendered = html or ""
        for key, value in replacements.items():
            rendered = rendered.replace("{{ %s }}" % key, str(escape(value)))
            rendered = rendered.replace("{{%s}}" % key, str(escape(value)))
        return Markup(rendered)

    def tijara_prepare_fbr_payload(self):
        self.ensure_one()
        return {
            "invoice_ref": self.name,
            "company": self.company_id.name,
            "company_ntn": self.company_id.tijara_ntn,
            "company_strn": self.company_id.tijara_strn,
            "pos_id": self.company_id.tijara_fbr_pos_id,
            "customer": self.partner_id.name if self.partner_id else "Walk-in",
            "customer_cnic": self.partner_id.tijara_cnic if self.partner_id else False,
            "amount_total": self.amount_total,
            "amount_tax": self.amount_tax,
            "currency": self.currency_id.name,
            "lines": [
                {
                    "product": line.product_id.display_name,
                    "qty": line.qty,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "subtotal_incl": line.price_subtotal_incl,
                }
                for line in self.lines
            ],
        }

    def action_tijara_queue_fbr_invoice(self):
        queue_model = self.env["tijara.fbr.invoice.queue"]
        for order in self:
            payload = order.tijara_prepare_fbr_payload()
            queue_model.create(
                {
                    "name": order.name,
                    "pos_order_id": order.id,
                    "invoice_ref": order.name,
                    "payload": json.dumps(payload),
                    "qr_payload": order.tijara_fbr_qr_payload,
                    "state": "queued",
                    "company_id": order.company_id.id,
                }
            )
