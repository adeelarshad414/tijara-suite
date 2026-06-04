import base64
import csv
import io

from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class TijaraBulkDataOperation(models.Model):
    _name = "tijara.bulk.data.operation"
    _description = "Tijara Bulk Import Export Operation"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True)
    operation_type = fields.Selection(
        [("import", "Import"), ("export", "Export")],
        default="import",
        required=True,
    )
    data_type = fields.Selection(
        [
            ("product", "Products and Prices"),
            ("inventory", "Inventory Quantities"),
            ("contact", "Customers and Suppliers"),
            ("hardware_device", "Hardware Devices"),
            ("receipt_template", "Invoice and Receipt Templates"),
            ("storage_position", "Storage Positions"),
            ("promotion", "Promotions and Deals"),
        ],
        default="product",
        required=True,
    )
    file_binary = fields.Binary(string="CSV Import File")
    file_name = fields.Char()
    result_binary = fields.Binary(string="CSV Export / Result")
    result_file_name = fields.Char()
    processed_count = fields.Integer(readonly=True)
    error_count = fields.Integer(readonly=True)
    message = fields.Text(readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
    )

    def action_process(self):
        for operation in self:
            try:
                if operation.operation_type == "import":
                    processed = operation._process_import()
                    operation.write(
                        {
                            "state": "done",
                            "processed_count": processed,
                            "message": _("Imported %s records.") % processed,
                        }
                    )
                else:
                    processed = operation._process_export()
                    operation.write(
                        {
                            "state": "done",
                            "processed_count": processed,
                            "message": _("Exported %s records.") % processed,
                        }
                    )
            except Exception as exc:
                operation.write({"state": "failed", "error_count": 1, "message": str(exc)})
                raise

    def action_reset(self):
        self.write(
            {
                "state": "draft",
                "processed_count": 0,
                "error_count": 0,
                "message": False,
            }
        )

    def action_export_template(self):
        for operation in self:
            headers = operation._headers_for_type(operation.data_type)
            operation._write_csv_result(
                [dict.fromkeys(headers, "")],
                headers,
                f"tijara_{operation.data_type}_template.csv",
            )
            operation.message = _("Template exported.")
            operation.state = "done"

    def _process_import(self):
        rows = self._read_csv_rows()
        method = getattr(self, f"_import_{self.data_type}", None)
        if not method:
            raise UserError(_("Import is not implemented for %s.") % self.data_type)
        return method(rows)

    def _process_export(self):
        method = getattr(self, f"_export_{self.data_type}", None)
        if not method:
            raise UserError(_("Export is not implemented for %s.") % self.data_type)
        rows, headers = method()
        self._write_csv_result(rows, headers, f"tijara_{self.data_type}_export.csv")
        return len(rows)

    def _read_csv_rows(self):
        self.ensure_one()
        if not self.file_binary:
            raise UserError(_("Upload a CSV file first."))
        raw = base64.b64decode(self.file_binary)
        text = raw.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))

    def _write_csv_result(self, rows, headers, file_name):
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        self.result_binary = base64.b64encode(output.getvalue().encode("utf-8"))
        self.result_file_name = file_name

    def _headers_for_type(self, data_type):
        headers = {
            "product": [
                "default_code",
                "name",
                "tijara_urdu_name",
                "tijara_local_sku",
                "tijara_barcode_alias",
                "barcode",
                "tijara_label_name",
                "list_price",
                "standard_price",
                "tijara_b2c_price",
                "tijara_b2b_price",
                "tijara_b2b_min_qty",
                "available_in_pos",
                "is_storable",
                "sale_ok",
                "purchase_ok",
                "tijara_quick_sale",
                "tijara_min_stock_alert",
                "tijara_reorder_multiple",
                "tijara_allow_refund",
                "tijara_allow_exchange",
                "tijara_inventory_critical_qty",
                "tijara_expiry_alert_days",
                "tijara_retail_unit",
                "tijara_tax_category",
            ],
            "inventory": ["default_code", "barcode", "quantity", "location_barcode", "location_name"],
            "contact": [
                "name",
                "ref",
                "email",
                "phone",
                "mobile",
                "tijara_customer_type",
                "is_supplier",
            ],
            "hardware_device": [
                "name",
                "code",
                "device_type",
                "connection_type",
                "integration_role",
                "integration_status",
                "printer_language",
                "scanner_mode",
                "ip_address",
                "port",
                "serial_path",
                "bridge_endpoint",
                "driver_name",
                "paper_width_mm",
                "dpi",
                "supports_barcode",
                "supports_qr",
                "supports_duplex",
                "auto_open_cash_drawer",
                "vendor_name",
                "model_name",
                "config_json",
            ],
            "receipt_template": [
                "name",
                "template_scope",
                "template_layout",
                "language_mode",
                "printer_width",
                "printer_device_code",
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
                "custom_width_mm",
                "custom_height_mm",
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
            ],
            "storage_position": [
                "name",
                "code",
                "warehouse",
                "location_name",
                "zone",
                "aisle",
                "rack",
                "shelf",
                "bin",
                "barcode",
            ],
            "promotion": [
                "name",
                "code",
                "promotion_type",
                "applies_to",
                "discount_percent",
                "fixed_price",
                "title_english",
                "title_urdu",
            ],
        }
        return headers[data_type]

    def _truthy(self, value):
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _float(self, value, default=0.0):
        value = str(value or "").strip()
        return float(value) if value else default

    def _int(self, value, default=0):
        value = str(value or "").strip()
        return int(value) if value else default

    def _bool_from_row(self, row, field_name, default=False):
        value = row.get(field_name)
        if value in (None, ""):
            return default
        return self._truthy(value)

    def _values_for_model(self, model, values):
        return {key: value for key, value in values.items() if key in model._fields}

    def _required(self, row, field_name, label=None):
        value = (row.get(field_name) or "").strip()
        if not value:
            raise UserError(_("%s is required.") % (label or field_name))
        return value

    def _import_product(self, rows):
        model = self.env["product.template"].sudo()
        count = 0
        for row in rows:
            default_code = (row.get("default_code") or "").strip()
            barcode = (row.get("barcode") or "").strip()
            name = (row.get("name") or "").strip()
            if not (name or default_code or barcode):
                raise UserError(_("Product rows require name, default_code, or barcode."))
            product = model.browse()
            if default_code:
                product = model.search([("default_code", "=", default_code)], limit=1)
            if not product and barcode:
                product = model.search([("barcode", "=", barcode)], limit=1)
            values = self._values_for_model(
                model,
                {
                "name": name or default_code or barcode,
                "default_code": default_code or False,
                "tijara_urdu_name": row.get("tijara_urdu_name") or False,
                "tijara_local_sku": row.get("tijara_local_sku") or False,
                "tijara_barcode_alias": row.get("tijara_barcode_alias") or False,
                "barcode": barcode or False,
                "tijara_label_name": row.get("tijara_label_name") or False,
                "list_price": self._float(row.get("list_price")),
                "standard_price": self._float(row.get("standard_price")),
                "tijara_b2c_price": self._float(row.get("tijara_b2c_price")),
                "tijara_b2b_price": self._float(row.get("tijara_b2b_price")),
                "tijara_b2b_min_qty": self._float(row.get("tijara_b2b_min_qty")),
                "available_in_pos": self._bool_from_row(row, "available_in_pos"),
                "is_storable": self._bool_from_row(row, "is_storable"),
                "type": "consu",
                "sale_ok": self._bool_from_row(row, "sale_ok", True),
                "purchase_ok": self._bool_from_row(row, "purchase_ok", True),
                "tijara_quick_sale": self._bool_from_row(row, "tijara_quick_sale"),
                "tijara_min_stock_alert": self._float(row.get("tijara_min_stock_alert")),
                "tijara_reorder_multiple": self._float(row.get("tijara_reorder_multiple")),
                "tijara_allow_refund": self._bool_from_row(row, "tijara_allow_refund", True),
                "tijara_allow_exchange": self._bool_from_row(row, "tijara_allow_exchange", True),
                "tijara_inventory_critical_qty": self._float(row.get("tijara_inventory_critical_qty")),
                "tijara_expiry_alert_days": self._int(row.get("tijara_expiry_alert_days"), 30),
                "tijara_retail_unit": row.get("tijara_retail_unit") or False,
                "tijara_tax_category": row.get("tijara_tax_category") or "standard",
                },
            )
            if product:
                product.write(values)
            else:
                model.create(values)
            count += 1
        return count

    def _import_inventory(self, rows):
        product_model = self.env["product.product"].sudo()
        quant_model = self.env["stock.quant"].sudo()
        count = 0
        for row in rows:
            product = self._find_product(row, product_model)
            location = self._find_location(row)
            quantity = self._float(row.get("quantity"))
            current = quant_model._get_available_quantity(product, location)
            quant_model._update_available_quantity(product, location, quantity - current)
            count += 1
        return count

    def _import_contact(self, rows):
        model = self.env["res.partner"].sudo()
        count = 0
        for row in rows:
            ref = (row.get("ref") or "").strip()
            email = (row.get("email") or "").strip()
            phone = (row.get("phone") or row.get("mobile") or "").strip()
            name = (row.get("name") or "").strip()
            if not (name or ref or email or phone):
                raise UserError(_("Contact rows require name, ref, email, phone, or mobile."))
            partner = model.browse()
            if ref:
                partner = model.search([("ref", "=", ref)], limit=1)
            if not partner and email:
                partner = model.search([("email", "=", email)], limit=1)
            values = {
                "name": name or ref or email or phone,
                "ref": ref or False,
                "email": email or False,
                "phone": row.get("phone") or False,
                "mobile": row.get("mobile") or False,
                "tijara_customer_type": row.get("tijara_customer_type") or "retail",
                "supplier_rank": 1 if self._truthy(row.get("is_supplier")) else 0,
            }
            if partner:
                partner.write(values)
            else:
                model.create(values)
            count += 1
        return count

    def _import_hardware_device(self, rows):
        model = self.env["tijara.hardware.device"].sudo()
        count = 0
        for row in rows:
            code = (row.get("code") or "").strip()
            if not code:
                raise UserError(_("Hardware device code is required."))
            device = model.search([("code", "=", code)], limit=1)
            values = {
                "name": row.get("name") or code,
                "code": code,
                "active": self._bool_from_row(row, "active", True),
                "device_type": row.get("device_type") or "barcode_scanner",
                "connection_type": row.get("connection_type") or "keyboard_wedge",
                "integration_role": row.get("integration_role") or False,
                "integration_status": row.get("integration_status") or "draft",
                "printer_language": row.get("printer_language") or False,
                "scanner_mode": row.get("scanner_mode") or False,
                "ip_address": row.get("ip_address") or False,
                "port": row.get("port") or False,
                "serial_path": row.get("serial_path") or False,
                "bridge_endpoint": row.get("bridge_endpoint") or False,
                "driver_name": row.get("driver_name") or False,
                "paper_width_mm": self._int(row.get("paper_width_mm")),
                "dpi": self._int(row.get("dpi")),
                "supports_barcode": self._bool_from_row(row, "supports_barcode", True),
                "supports_qr": self._bool_from_row(row, "supports_qr", True),
                "supports_duplex": self._bool_from_row(row, "supports_duplex"),
                "auto_open_cash_drawer": self._bool_from_row(row, "auto_open_cash_drawer"),
                "vendor_name": row.get("vendor_name") or False,
                "model_name": row.get("model_name") or False,
                "config_json": row.get("config_json") or False,
                "company_id": self.company_id.id,
            }
            if device:
                device.write(values)
            else:
                model.create(values)
            count += 1
        return count

    def _import_receipt_template(self, rows):
        model = self.env["tijara.receipt.profile"].sudo()
        count = 0
        for row in rows:
            name = self._required(row, "name", _("Template name"))
            template = model.search([("name", "=", name), ("company_id", "=", self.company_id.id)], limit=1)
            printer_device = self._find_hardware_device(row.get("printer_device_code"))
            values = {
                "name": name,
                "company_id": self.company_id.id,
                "template_scope": row.get("template_scope") or "pos_receipt",
                "template_layout": row.get("template_layout") or "standard",
                "language_mode": row.get("language_mode") or "both",
                "printer_width": row.get("printer_width") or "80",
                "printer_device_id": printer_device.id if printer_device else False,
                "show_qr": self._bool_from_row(row, "show_qr", True),
                "show_barcode": self._bool_from_row(row, "show_barcode", True),
                "show_fbr_fields": self._bool_from_row(row, "show_fbr_fields"),
                "show_logo": self._bool_from_row(row, "show_logo", True),
                "show_customer": self._bool_from_row(row, "show_customer", True),
                "show_cashier": self._bool_from_row(row, "show_cashier", True),
                "show_tax_breakdown": self._bool_from_row(row, "show_tax_breakdown", True),
                "show_discount_breakdown": self._bool_from_row(row, "show_discount_breakdown", True),
                "show_payment_summary": self._bool_from_row(row, "show_payment_summary", True),
                "show_company_ntn_strn": self._bool_from_row(row, "show_company_ntn_strn", True),
                "show_return_policy": self._bool_from_row(row, "show_return_policy", True),
                "barcode_source": row.get("barcode_source") or "tijara_invoice_barcode",
                "custom_barcode_value": row.get("custom_barcode_value") or False,
                "custom_width_mm": self._float(row.get("custom_width_mm")),
                "custom_height_mm": self._float(row.get("custom_height_mm")),
                "receipt_title_english": row.get("receipt_title_english") or False,
                "receipt_title_urdu": row.get("receipt_title_urdu") or False,
                "header_english": row.get("header_english") or False,
                "header_urdu": row.get("header_urdu") or False,
                "footer_english": row.get("footer_english") or False,
                "footer_urdu": row.get("footer_urdu") or False,
                "terms_english": row.get("terms_english") or False,
                "terms_urdu": row.get("terms_urdu") or False,
                "custom_body_html": row.get("custom_body_html") or False,
                "custom_css": row.get("custom_css") or False,
            }
            if template:
                template.write(values)
            else:
                model.create(values)
            count += 1
        return count

    def _import_storage_position(self, rows):
        self._ensure_model("tijara.storage.position")
        model = self.env["tijara.storage.position"].sudo()
        count = 0
        for row in rows:
            code = self._required(row, "code", _("Storage position code"))
            position = model.search([("code", "=", code)], limit=1)
            warehouse = self._find_warehouse(row.get("warehouse"))
            location = self._find_location(row)
            values = {
                "name": row.get("name") or code,
                "code": code,
                "warehouse_id": warehouse.id if warehouse else False,
                "location_id": location.id,
                "zone": row.get("zone") or False,
                "aisle": row.get("aisle") or False,
                "rack": row.get("rack") or False,
                "shelf": row.get("shelf") or False,
                "bin": row.get("bin") or False,
                "barcode": row.get("barcode") or False,
                "company_id": self.company_id.id,
            }
            if position:
                position.write(values)
            else:
                model.create(values)
            count += 1
        return count

    def _import_promotion(self, rows):
        self._ensure_model("tijara.promotion")
        model = self.env["tijara.promotion"].sudo()
        count = 0
        for row in rows:
            code = self._required(row, "code", _("Promotion code"))
            promotion = model.search([("code", "=", code)], limit=1)
            values = {
                "name": row.get("name") or code,
                "code": code,
                "company_id": self.company_id.id,
                "promotion_type": row.get("promotion_type") or "discount",
                "applies_to": row.get("applies_to") or "both",
                "discount_percent": self._float(row.get("discount_percent")),
                "fixed_price": self._float(row.get("fixed_price")),
                "title_english": row.get("title_english") or False,
                "title_urdu": row.get("title_urdu") or False,
            }
            if promotion:
                promotion.write(values)
            else:
                model.create(values)
            count += 1
        return count

    def _export_product(self):
        headers = self._headers_for_type("product")
        records = self.env["product.template"].sudo().search([])
        rows = [
            {header: self._export_field(record, header) for header in headers}
            for record in records
        ]
        return rows, headers

    def _export_inventory(self):
        headers = self._headers_for_type("inventory")
        quants = self.env["stock.quant"].sudo().search([("location_id.usage", "=", "internal")])
        rows = [
            {
                "default_code": quant.product_id.default_code or "",
                "barcode": quant.product_id.barcode or "",
                "quantity": quant.quantity,
                "location_barcode": quant.location_id.barcode or "",
                "location_name": quant.location_id.complete_name or quant.location_id.name,
            }
            for quant in quants
            if quant.product_id
        ]
        return rows, headers

    def _export_contact(self):
        headers = self._headers_for_type("contact")
        partners = self.env["res.partner"].sudo().search([])
        rows = [
            {
                "name": partner.name or "",
                "ref": partner.ref or "",
                "email": partner.email or "",
                "phone": partner.phone or "",
                "mobile": partner.mobile or "",
                "tijara_customer_type": partner.tijara_customer_type or "",
                "is_supplier": bool(partner.supplier_rank),
            }
            for partner in partners
        ]
        return rows, headers

    def _export_hardware_device(self):
        headers = self._headers_for_type("hardware_device")
        records = self.env["tijara.hardware.device"].sudo().search([])
        rows = [{header: self._export_field(record, header) for header in headers} for record in records]
        return rows, headers

    def _export_receipt_template(self):
        headers = self._headers_for_type("receipt_template")
        records = self.env["tijara.receipt.profile"].sudo().search([])
        rows = []
        for record in records:
            row = {header: self._export_field(record, header) for header in headers}
            row["printer_device_code"] = record.printer_device_id.code or ""
            rows.append(row)
        return rows, headers

    def _export_storage_position(self):
        self._ensure_model("tijara.storage.position")
        headers = self._headers_for_type("storage_position")
        records = self.env["tijara.storage.position"].sudo().search([])
        rows = [
            {
                "name": record.name or "",
                "code": record.code or "",
                "warehouse": record.warehouse_id.name or "",
                "location_name": record.location_id.complete_name or record.location_id.name or "",
                "zone": record.zone or "",
                "aisle": record.aisle or "",
                "rack": record.rack or "",
                "shelf": record.shelf or "",
                "bin": record.bin or "",
                "barcode": record.barcode or "",
            }
            for record in records
        ]
        return rows, headers

    def _export_promotion(self):
        self._ensure_model("tijara.promotion")
        headers = self._headers_for_type("promotion")
        records = self.env["tijara.promotion"].sudo().search([])
        rows = [{header: self._export_field(record, header) for header in headers} for record in records]
        return rows, headers

    def _find_product(self, row, product_model):
        default_code = (row.get("default_code") or "").strip()
        barcode = (row.get("barcode") or "").strip()
        product = product_model.browse()
        if default_code:
            product = product_model.search([("default_code", "=", default_code)], limit=1)
        if not product and barcode:
            product = product_model.search([("barcode", "=", barcode)], limit=1)
        if not product:
            raise UserError(_("Product not found for row: %s") % (default_code or barcode))
        return product

    def _find_location(self, row):
        model = self.env["stock.location"].sudo()
        barcode = (row.get("location_barcode") or row.get("barcode") or "").strip()
        name = (row.get("location_name") or "").strip()
        location = model.search([("barcode", "=", barcode), ("usage", "=", "internal")], limit=1) if barcode else model
        if not location and name:
            location = model.search(
                ["|", ("complete_name", "=", name), ("name", "=", name), ("usage", "=", "internal")],
                limit=1,
            )
        if not location:
            warehouse = self.env["stock.warehouse"].sudo().search([("company_id", "=", self.company_id.id)], limit=1)
            location = warehouse.lot_stock_id
        if not location:
            raise UserError(_("No internal stock location found."))
        return location

    def _find_warehouse(self, name):
        if not name:
            return self.env["stock.warehouse"].sudo().search([("company_id", "=", self.company_id.id)], limit=1)
        return self.env["stock.warehouse"].sudo().search(
            ["|", ("name", "=", name), ("code", "=", name)],
            limit=1,
        )

    def _find_hardware_device(self, code):
        code = (code or "").strip()
        if not code:
            return self.env["tijara.hardware.device"].sudo()
        device = self.env["tijara.hardware.device"].sudo().search(
            [("code", "=", code), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if not device:
            raise UserError(_("Hardware device %s was not found.") % code)
        return device

    def _export_field(self, record, field_name):
        if field_name not in record._fields:
            return ""
        value = record[field_name]
        if hasattr(value, "_name"):
            return value.display_name if len(value) == 1 else ",".join(value.mapped("display_name"))
        return value or ""

    def _ensure_model(self, model_name):
        if model_name not in self.env.registry.models:
            raise UserError(_("%s is not installed in this database.") % model_name)
