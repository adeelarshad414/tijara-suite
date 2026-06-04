import hashlib
import json

from odoo import api, fields, models


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
    evidence_hash = fields.Char(copy=False)
    next_retest_date = fields.Date()
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for certification in records:
            if certification.name == "New":
                certification.name = "HWC-%05d" % certification.id
        return records

    def action_mark_passed(self):
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
