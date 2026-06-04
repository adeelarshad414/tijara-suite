import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from odoo import _, fields, models
from odoo.exceptions import UserError


class TijaraHardwareDevice(models.Model):
    _name = "tijara.hardware.device"
    _description = "Tijara Hardware Device"
    _order = "company_id, device_type, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    branch_code = fields.Char(related="company_id.tijara_branch_code", store=True)
    device_type = fields.Selection(
        [
            ("receipt_printer", "Receipt Printer"),
            ("label_printer", "Label Printer"),
            ("barcode_scanner", "Barcode Scanner"),
            ("qr_scanner", "QR Scanner"),
            ("cash_drawer", "Cash Drawer"),
            ("weighing_scale", "Weighing Scale"),
            ("customer_display", "Customer Display"),
            ("fiscal_device", "Fiscal Device"),
        ],
        required=True,
    )
    connection_type = fields.Selection(
        [
            ("usb", "USB"),
            ("network", "Network"),
            ("serial", "Serial"),
            ("bluetooth", "Bluetooth"),
            ("browser_bridge", "Browser Bridge"),
            ("keyboard_wedge", "Keyboard Wedge"),
            ("cups", "CUPS / System Printer"),
        ],
        required=True,
        default="network",
    )
    integration_role = fields.Selection(
        [
            ("scan_input", "Scanner Input"),
            ("receipt_output", "Receipt Output"),
            ("label_output", "Label Output"),
            ("customer_display", "Customer Display"),
            ("scale_input", "Scale Input"),
            ("cash_drawer", "Cash Drawer"),
            ("fiscal_submit", "Fiscal Submit"),
        ],
        string="Integration Role",
    )
    integration_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("offline", "Offline"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
    )
    printer_language = fields.Selection(
        [
            ("escpos", "ESC/POS"),
            ("zpl", "ZPL"),
            ("pdf", "PDF"),
            ("browser", "Browser Print"),
            ("cups", "CUPS"),
        ],
        string="Printer Language",
    )
    scanner_mode = fields.Selection(
        [
            ("keyboard_wedge", "Keyboard Wedge"),
            ("serial", "Serial"),
            ("network", "Network"),
            ("browser_bridge", "Browser Bridge"),
        ],
        string="Scanner Mode",
    )
    ip_address = fields.Char()
    port = fields.Char()
    serial_path = fields.Char()
    bridge_endpoint = fields.Char(string="Bridge Endpoint")
    driver_name = fields.Char()
    paper_width_mm = fields.Integer()
    dpi = fields.Integer(string="DPI")
    supports_barcode = fields.Boolean(default=True)
    supports_qr = fields.Boolean(default=True)
    supports_duplex = fields.Boolean()
    auto_open_cash_drawer = fields.Boolean()
    model_name = fields.Char()
    vendor_name = fields.Char()
    config_json = fields.Text(string="Configuration JSON")
    test_payload = fields.Text()
    last_test_result = fields.Text()
    last_seen_at = fields.Datetime()
    bridge_last_job_id = fields.Char(string="Last Bridge Job")
    bridge_last_operation = fields.Char(string="Last Bridge Operation")
    bridge_last_response_code = fields.Integer(string="Last Bridge HTTP Status")

    def action_test_connection(self):
        for device in self:
            device._tijara_validate_connection_metadata()
            if device.connection_type == "browser_bridge":
                response = device._tijara_bridge_request(
                    "POST",
                    "/v1/test",
                    device._tijara_bridge_payload("test"),
                    signed=True,
                )
                device._tijara_write_bridge_result("test", response)
            else:
                device.write(
                    {
                        "integration_status": "ready",
                        "last_seen_at": fields.Datetime.now(),
                        "last_test_result": _(
                            "Configuration check passed. Hardware bridge runtime test is pending."
                        ),
                    }
                )

    def action_mark_offline(self):
        self.write({"integration_status": "offline"})

    def action_bridge_health_check(self):
        for device in self:
            device._tijara_validate_bridge_endpoint()
            response = device._tijara_bridge_request("GET", "/health", signed=False)
            device._tijara_write_bridge_result("health", response)

    def action_send_bridge_test_job(self):
        for device in self:
            device._tijara_validate_connection_metadata()
            operation, endpoint = device._tijara_bridge_operation_endpoint()
            device.tijara_submit_bridge_job(operation, device._tijara_bridge_payload(operation), endpoint)

    def tijara_submit_bridge_job(self, operation, payload, endpoint=False):
        self.ensure_one()
        self._tijara_validate_connection_metadata()
        if not endpoint:
            _operation, endpoint = self._tijara_bridge_operation_endpoint()
        payload = self._tijara_prepare_bridge_job_payload(operation, payload or {})
        response = self._tijara_bridge_request("POST", endpoint, payload, signed=True)
        self._tijara_write_bridge_result(operation, response)
        return response

    def _tijara_validate_connection_metadata(self):
        self.ensure_one()
        if self.connection_type == "network" and not self.ip_address:
            raise UserError(_("Network devices require an IP address."))
        if self.connection_type == "serial" and not self.serial_path:
            raise UserError(_("Serial devices require a serial path."))
        if self.connection_type == "browser_bridge":
            self._tijara_validate_bridge_endpoint()

    def _tijara_validate_bridge_endpoint(self):
        self.ensure_one()
        if not self.bridge_endpoint:
            raise UserError(_("Browser bridge devices require a bridge endpoint."))

    def _tijara_bridge_operation_endpoint(self):
        self.ensure_one()
        mapping = {
            "receipt_printer": ("print_receipt", "/v1/print/receipt"),
            "label_printer": ("print_label", "/v1/print/label"),
            "cash_drawer": ("open_cash_drawer", "/v1/cash-drawer/open"),
            "weighing_scale": ("read_scale", "/v1/scale/read"),
            "customer_display": ("customer_display", "/v1/display/customer"),
            "barcode_scanner": ("scanner_event", "/v1/scan/event"),
            "qr_scanner": ("scanner_event", "/v1/scan/event"),
            "fiscal_device": ("test", "/v1/test"),
        }
        return mapping.get(self.device_type, ("test", "/v1/test"))

    def _tijara_bridge_payload(self, operation):
        self.ensure_one()
        payload = {
            "device_code": self.code,
            "device_name": self.name,
            "device_type": self.device_type,
            "connection_type": self.connection_type,
            "operation": operation,
            "printer_language": self.printer_language or False,
            "scanner_mode": self.scanner_mode or False,
            "paper_width_mm": self.paper_width_mm or False,
            "dpi": self.dpi or False,
            "supports_barcode": self.supports_barcode,
            "supports_qr": self.supports_qr,
            "auto_open_cash_drawer": self.auto_open_cash_drawer,
            "payload": self.test_payload or self._tijara_default_test_payload(operation),
        }
        if operation == "read_scale":
            payload.update({"test_weight": 0, "unit": "kg"})
        if operation == "scanner_event":
            payload.update({"scan_value": self.test_payload or "TJINV:BRIDGE-SMOKE"})
        if self.config_json:
            try:
                payload["device_config"] = json.loads(self.config_json)
            except json.JSONDecodeError as error:
                raise UserError(_("Invalid hardware configuration JSON: %s") % error) from error
        return payload

    def _tijara_prepare_bridge_job_payload(self, operation, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            raise UserError(_("Hardware bridge payload must be a JSON object."))
        prepared = dict(payload)
        prepared.update(
            {
                "device_code": prepared.get("device_code") or self.code,
                "device_name": prepared.get("device_name") or self.name,
                "device_type": prepared.get("device_type") or self.device_type,
                "connection_type": prepared.get("connection_type") or self.connection_type,
                "operation": operation,
                "printer_language": prepared.get("printer_language") or self.printer_language or False,
                "scanner_mode": prepared.get("scanner_mode") or self.scanner_mode or False,
                "paper_width_mm": prepared.get("paper_width_mm") or self.paper_width_mm or False,
                "dpi": prepared.get("dpi") or self.dpi or False,
                "supports_barcode": self.supports_barcode,
                "supports_qr": self.supports_qr,
                "auto_open_cash_drawer": self.auto_open_cash_drawer,
            }
        )
        if self.config_json:
            try:
                prepared["device_config"] = json.loads(self.config_json)
            except json.JSONDecodeError as error:
                raise UserError(_("Invalid hardware configuration JSON: %s") % error) from error
        return prepared

    def _tijara_default_test_payload(self, operation):
        self.ensure_one()
        defaults = {
            "print_receipt": "Tijara bridge receipt test\nDevice: %s\n" % self.code,
            "print_label": "^XA^FO50,50^A0N,30,30^FDTijara Label Test %s^FS^XZ" % self.code,
            "open_cash_drawer": "open",
            "customer_display": {
                "title": "Tijara",
                "line_1": "Customer display test",
                "total": "0.00",
            },
            "scanner_event": "TJINV:BRIDGE-SMOKE",
            "read_scale": "read",
            "test": "Tijara bridge test for %s" % self.code,
        }
        return defaults.get(operation, defaults["test"])

    def _tijara_bridge_request(self, method, path, payload=None, signed=True):
        self.ensure_one()
        timeout = float(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "tijara.bridge.timeout_seconds",
                os.environ.get("TIJARA_BRIDGE_TIMEOUT_SECONDS", "5"),
            )
        )
        url = urllib.parse.urljoin(self.bridge_endpoint.rstrip("/") + "/", path.lstrip("/"))
        body = b""
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if signed:
            headers.update(self._tijara_bridge_signature_headers(body))
        request = urllib.request.Request(
            url,
            data=body if method != "GET" else None,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read().decode("utf-8")
                result = json.loads(data or "{}")
                result["_http_status"] = response.status
                return result
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8")
            try:
                result = json.loads(raw or "{}")
            except json.JSONDecodeError:
                result = {"status": "error", "message": raw or str(error)}
            result["_http_status"] = error.code
            raise UserError(_("Hardware bridge error: %s") % json.dumps(result)) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise UserError(_("Hardware bridge is unreachable: %s") % error) from error

    def _tijara_bridge_signature_headers(self, body):
        self.ensure_one()
        secret = (
            self.env["ir.config_parameter"].sudo().get_param("tijara.bridge.shared_secret")
            or os.environ.get("TIJARA_BRIDGE_SHARED_SECRET")
        )
        if not secret:
            raise UserError(
                _(
                    "Hardware bridge shared secret is missing. Set "
                    "TIJARA_BRIDGE_SHARED_SECRET or system parameter "
                    "tijara.bridge.shared_secret."
                )
            )
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Tijara-Timestamp": timestamp,
            "X-Tijara-Signature": "sha256=%s" % signature,
        }

    def _tijara_write_bridge_result(self, operation, response):
        self.ensure_one()
        self.write(
            {
                "integration_status": "ready" if response.get("status") in ("ok", "accepted") else "error",
                "last_seen_at": fields.Datetime.now(),
                "last_test_result": json.dumps(response, indent=2, ensure_ascii=False),
                "bridge_last_job_id": response.get("job_id") or False,
                "bridge_last_operation": operation,
                "bridge_last_response_code": response.get("_http_status") or 0,
            }
        )
