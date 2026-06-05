import hashlib
import json
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TijaraHardwareCertification(models.Model):
    _name = "tijara.hardware.certification"
    _description = "Tijara Hardware Certification"
    _order = "tested_at desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    device_id = fields.Many2one("tijara.hardware.device", required=True)
    company_id = fields.Many2one(
        "res.company",
        related="device_id.company_id",
        store=True,
    )
    device_type = fields.Selection(related="device_id.device_type", store=True)
    connection_type = fields.Selection(related="device_id.connection_type", store=True)
    vendor_name = fields.Char(related="device_id.vendor_name", store=True)
    model_name = fields.Char(related="device_id.model_name", store=True)
    driver_name = fields.Char(related="device_id.driver_name", store=True)
    profile_name = fields.Char(required=True)
    certification_type = fields.Selection(
        [
            ("dry_run", "Dry Run"),
            ("physical", "Physical Device"),
            ("pilot", "Pilot Store"),
        ],
        default="physical",
        required=True,
    )
    tested_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    tested_at = fields.Datetime(default=fields.Datetime.now)
    firmware_version = fields.Char()
    driver_version = fields.Char()
    observed_serial_number = fields.Char()
    store_location = fields.Char()
    certification_standard = fields.Char(default="Tijara Hardware Certification v1")
    physical_signature = fields.Char()
    last_physical_seen_at = fields.Datetime()
    result = fields.Selection(
        [
            ("draft", "Draft"),
            ("passed", "Passed"),
            ("failed", "Failed"),
            ("blocked", "Blocked"),
        ],
        default="draft",
        required=True,
    )
    receipt_print_ok = fields.Boolean()
    label_print_ok = fields.Boolean()
    barcode_scan_ok = fields.Boolean()
    qr_scan_ok = fields.Boolean()
    cash_drawer_ok = fields.Boolean()
    scale_read_ok = fields.Boolean()
    customer_display_ok = fields.Boolean()
    evidence_summary = fields.Text()
    evidence_json = fields.Text()
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "tijara_hardware_certification_attachment_rel",
        "certification_id",
        "attachment_id",
        string="Evidence Files",
    )
    check_ids = fields.One2many(
        "tijara.hardware.certification.check",
        "certification_id",
        string="Execution Checks",
    )
    check_count = fields.Integer(compute="_compute_check_counts")
    passed_check_count = fields.Integer(compute="_compute_check_counts")
    evidence_hash = fields.Char(copy=False)
    next_retest_date = fields.Date()
    notes = fields.Text()

    def _compute_check_counts(self):
        for certification in self:
            certification.check_count = len(certification.check_ids)
            certification.passed_check_count = len(
                certification.check_ids.filtered(lambda check: check.result == "passed")
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for certification in records:
            if certification.name == "New":
                certification.name = "HWC-%05d" % certification.id
        return records

    def action_mark_passed(self):
        for certification in self:
            if certification.check_ids and certification.passed_check_count != certification.check_count:
                raise UserError(
                    _(
                        "All hardware execution checks must pass before marking certification %s as passed."
                    )
                    % certification.name
                )
        self.action_refresh_evidence_hash()
        self.write(
            {
                "result": "passed",
                "tested_at": fields.Datetime.now(),
                "last_physical_seen_at": fields.Datetime.now(),
            }
        )

    def action_mark_failed(self):
        self.action_refresh_evidence_hash()
        self.write({"result": "failed", "tested_at": fields.Datetime.now()})

    def action_mark_blocked(self):
        self.write({"result": "blocked", "tested_at": fields.Datetime.now()})

    def _evidence_hash_payload(self):
        self.ensure_one()
        return {
            "device": self.device_id.display_name,
            "device_type": self.device_type,
            "vendor": self.vendor_name,
            "model": self.model_name,
            "serial": self.observed_serial_number,
            "driver": self.driver_name,
            "driver_version": self.driver_version,
            "firmware": self.firmware_version,
            "profile": self.profile_name,
            "checks": {
                "receipt_print_ok": self.receipt_print_ok,
                "label_print_ok": self.label_print_ok,
                "barcode_scan_ok": self.barcode_scan_ok,
                "qr_scan_ok": self.qr_scan_ok,
                "cash_drawer_ok": self.cash_drawer_ok,
                "scale_read_ok": self.scale_read_ok,
                "customer_display_ok": self.customer_display_ok,
            },
            "evidence_json": self.evidence_json or "",
            "attachments": [
                {
                    "name": attachment.name,
                    "checksum": attachment.checksum,
                }
                for attachment in self.evidence_attachment_ids
            ],
            "checks": [
                {
                    "name": check.name,
                    "operation": check.operation,
                    "result": check.result,
                    "bridge_job_id": check.bridge_job_id,
                    "response_code": check.bridge_response_code,
                    "duration_ms": check.duration_ms,
                    "evidence_hash": check.evidence_hash,
                }
                for check in self.check_ids
            ],
        }

    def action_refresh_evidence_hash(self):
        for certification in self:
            payload = json.dumps(
                certification._evidence_hash_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            certification.evidence_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _default_check_templates(self):
        self.ensure_one()
        common = {
            "receipt_printer": [
                ("receipt-print", "print_receipt", _("Print receipt with totals, QR, barcode, and Urdu text.")),
            ],
            "label_printer": [
                ("zpl-label", "print_label", _("Print product label with barcode/QR using ZPL or configured language.")),
            ],
            "barcode_scanner": [
                ("barcode-scan", "scanner_event", _("Scan invoice/POS barcode and confirm captured payload.")),
            ],
            "qr_scanner": [
                ("qr-scan", "scanner_event", _("Scan QR invoice code and confirm captured payload.")),
            ],
            "cash_drawer": [
                ("drawer-pulse", "open_cash_drawer", _("Open cash drawer with configured pulse.")),
            ],
            "weighing_scale": [
                ("scale-read", "read_scale", _("Read stable scale value and unit.")),
            ],
            "customer_display": [
                ("display-state", "customer_display", _("Publish customer-facing cart state and total.")),
            ],
            "fiscal_device": [
                ("fiscal-test", "test", _("Validate fiscal device bridge handshake.")),
            ],
        }
        return common.get(self.device_type or "", [("bridge-test", "test", _("Run generic bridge test."))])

    def action_prepare_execution_checks(self):
        for certification in self:
            existing_codes = set(certification.check_ids.mapped("check_code"))
            sequence = len(existing_codes) + 1
            for check_code, operation, expected_result in certification._default_check_templates():
                if check_code in existing_codes:
                    continue
                self.env["tijara.hardware.certification.check"].create(
                    {
                        "certification_id": certification.id,
                        "sequence": sequence,
                        "check_code": check_code,
                        "name": "%s - %s" % (certification.name, check_code),
                        "operation": operation,
                        "expected_result": expected_result,
                    }
                )
                sequence += 1


class TijaraHardwareCertificationCheck(models.Model):
    _name = "tijara.hardware.certification.check"
    _description = "Tijara Hardware Certification Execution Check"
    _order = "certification_id, sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    certification_id = fields.Many2one(
        "tijara.hardware.certification",
        required=True,
        ondelete="cascade",
    )
    device_id = fields.Many2one(
        "tijara.hardware.device",
        related="certification_id.device_id",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="certification_id.company_id",
        store=True,
    )
    check_code = fields.Char(required=True)
    operation = fields.Selection(
        [
            ("test", "Bridge Test"),
            ("print_receipt", "Print Receipt"),
            ("print_label", "Print Label"),
            ("open_cash_drawer", "Open Cash Drawer"),
            ("read_scale", "Read Scale"),
            ("scanner_event", "Scanner Event"),
            ("customer_display", "Customer Display"),
        ],
        required=True,
        default="test",
    )
    expected_result = fields.Text(required=True)
    observed_result = fields.Text()
    bridge_job_id = fields.Char()
    bridge_response_code = fields.Integer()
    duration_ms = fields.Integer()
    executed_by_id = fields.Many2one("res.users")
    executed_at = fields.Datetime()
    result = fields.Selection(
        [
            ("draft", "Draft"),
            ("passed", "Passed"),
            ("failed", "Failed"),
            ("blocked", "Blocked"),
        ],
        default="draft",
        required=True,
    )
    evidence_hash = fields.Char(copy=False)
    notes = fields.Text()

    def _endpoint_for_operation(self):
        self.ensure_one()
        mapping = {
            "test": "/v1/test",
            "print_receipt": "/v1/print/receipt",
            "print_label": "/v1/print/label",
            "open_cash_drawer": "/v1/cash-drawer/open",
            "read_scale": "/v1/scale/read",
            "scanner_event": "/v1/scan/event",
            "customer_display": "/v1/display/customer",
        }
        return mapping.get(self.operation, "/v1/test")

    def _refresh_evidence_hash(self):
        for check in self:
            payload = json.dumps(
                {
                    "certification": check.certification_id.name,
                    "device": check.device_id.display_name,
                    "check_code": check.check_code,
                    "operation": check.operation,
                    "expected_result": check.expected_result,
                    "observed_result": check.observed_result or "",
                    "bridge_job_id": check.bridge_job_id or "",
                    "bridge_response_code": check.bridge_response_code or 0,
                    "duration_ms": check.duration_ms or 0,
                    "result": check.result,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            check.evidence_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def action_run_bridge_check(self):
        for check in self:
            if not check.device_id:
                raise UserError(_("Certification check has no hardware device."))
            start = time.monotonic()
            try:
                payload = check.device_id._tijara_bridge_payload(check.operation)
                response = check.device_id.tijara_submit_bridge_job(
                    check.operation,
                    payload,
                    check._endpoint_for_operation(),
                )
                result = "passed" if response.get("status") in ("ok", "accepted") else "failed"
                check.write(
                    {
                        "observed_result": json.dumps(response, indent=2, ensure_ascii=False),
                        "bridge_job_id": response.get("job_id") or False,
                        "bridge_response_code": response.get("_http_status") or 0,
                        "duration_ms": int((time.monotonic() - start) * 1000),
                        "executed_by_id": self.env.user.id,
                        "executed_at": fields.Datetime.now(),
                        "result": result,
                    }
                )
            except UserError as error:
                check.write(
                    {
                        "observed_result": str(error),
                        "duration_ms": int((time.monotonic() - start) * 1000),
                        "executed_by_id": self.env.user.id,
                        "executed_at": fields.Datetime.now(),
                        "result": "failed",
                    }
                )
            check._refresh_evidence_hash()
        self.mapped("certification_id").action_refresh_evidence_hash()

    def action_mark_blocked(self):
        self.write(
            {
                "result": "blocked",
                "executed_by_id": self.env.user.id,
                "executed_at": fields.Datetime.now(),
            }
        )
        self._refresh_evidence_hash()

    def action_mark_passed_manual(self):
        self.write(
            {
                "result": "passed",
                "executed_by_id": self.env.user.id,
                "executed_at": fields.Datetime.now(),
            }
        )
        self._refresh_evidence_hash()
