import json
import os
import hashlib
import urllib.error
import urllib.request
import uuid

from odoo import fields, models
from odoo.exceptions import UserError


class TijaraFbrInvoiceQueue(models.Model):
    _name = "tijara.fbr.invoice.queue"
    _description = "Tijara FBR Invoice Queue"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    pos_order_id = fields.Many2one("pos.order", string="POS Order")
    invoice_ref = fields.Char(string="Invoice Reference", required=True)
    payload = fields.Text(required=True)
    response = fields.Text()
    fbr_invoice_number = fields.Char(string="FBR Invoice Number")
    qr_payload = fields.Text(string="QR Payload")
    submitted_at = fields.Datetime()
    error_message = fields.Text()
    adapter_mode = fields.Selection(
        [("dry_run", "Dry Run"), ("live", "Live")],
        default="dry_run",
        required=True,
    )
    adapter_provider = fields.Selection(
        [
            ("generic", "Generic Certified Adapter"),
            ("custom", "Custom Provider"),
        ],
        default="generic",
        required=True,
    )
    adapter_endpoint = fields.Char(string="Adapter Endpoint")
    adapter_client_id = fields.Char(string="Adapter Client ID")
    certification_environment = fields.Selection(
        [
            ("sandbox", "Sandbox"),
            ("uat", "UAT / Certification"),
            ("production", "Production"),
        ],
        default="sandbox",
        required=True,
    )
    certified_provider_name = fields.Char(string="Certified Provider")
    provider_credential_reference = fields.Char()
    provider_invoice_uuid = fields.Char(copy=False)
    sandbox_reference = fields.Char(copy=False)
    signed_payload_hash = fields.Char(copy=False)
    compliance_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("needs_credentials", "Needs Credentials"),
            ("ready", "Ready"),
            ("sandbox_passed", "Sandbox Passed"),
            ("production_ready", "Production Ready"),
            ("certified", "Certified"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
    )
    last_certification_check_at = fields.Datetime(copy=False)
    idempotency_key = fields.Char(
        default=lambda self: "tijara-fbr-%s" % uuid.uuid4().hex,
        required=True,
        copy=False,
    )
    submission_attempts = fields.Integer(default=0, copy=False)
    last_request_at = fields.Datetime(copy=False)
    last_response_status = fields.Char(copy=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("submitted", "Submitted"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    def action_queue(self):
        self.write({"state": "queued"})

    def action_submit_stub(self):
        return self.action_submit_to_fbr_adapter()

    def action_submit_to_fbr_adapter(self):
        for record in self:
            record._submit_to_fbr_adapter()

    def action_fail(self):
        self.write({"state": "failed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def _adapter_mode(self):
        self.ensure_one()
        return (
            self.adapter_mode
            or self.env["ir.config_parameter"].sudo().get_param("tijara.fbr.adapter_mode")
            or os.environ.get("FBR_ADAPTER_MODE")
            or "dry_run"
        )

    def _adapter_endpoint(self):
        self.ensure_one()
        return (
            self.adapter_endpoint
            or self.env["ir.config_parameter"].sudo().get_param("tijara.fbr.endpoint", "")
            or os.environ.get("FBR_ADAPTER_ENDPOINT", "")
        )

    def _adapter_secret(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param("tijara.fbr.client_secret", "")
            or os.environ.get("FBR_CLIENT_SECRET", "")
        )

    def _adapter_client_id(self):
        self.ensure_one()
        return (
            self.adapter_client_id
            or self.env["ir.config_parameter"].sudo().get_param("tijara.fbr.client_id", "")
            or os.environ.get("FBR_CLIENT_ID", "")
        )

    def _certified_provider_name(self):
        self.ensure_one()
        return (
            self.certified_provider_name
            or self.env["ir.config_parameter"].sudo().get_param("tijara.fbr.provider_name", "")
            or os.environ.get("FBR_PROVIDER_NAME", "")
        )

    def _allow_insecure_endpoint(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "tijara.fbr.allow_insecure_endpoint",
            os.environ.get("FBR_ALLOW_INSECURE_ENDPOINT", "0"),
        )
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _payload_dict(self):
        self.ensure_one()
        try:
            return json.loads(self.payload or "{}")
        except json.JSONDecodeError as error:
            raise UserError("FBR payload must be valid JSON: %s" % error) from error

    def _payload_hash(self):
        self.ensure_one()
        normalized = json.dumps(
            self._payload_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(("%s:%s" % (self.idempotency_key, normalized)).encode("utf-8")).hexdigest()

    def _check_live_readiness(self):
        self.ensure_one()
        if self._adapter_mode() != "live":
            return
        if not self._certified_provider_name():
            raise UserError("Set a certified FBR provider name before live FBR submission.")
        if not self._adapter_client_id():
            raise UserError("Set FBR_CLIENT_ID or tijara.fbr.client_id before live FBR submission.")
        if not self.provider_credential_reference and not self._adapter_secret():
            raise UserError("Set provider credentials before live FBR submission.")

    def _dry_run_response(self):
        self.ensure_one()
        invoice_number = "DRY-FBR-%05d" % self.id
        return {
            "status": "accepted",
            "mode": "dry_run",
            "fbr_invoice_number": invoice_number,
            "qr_payload": "FBR:%s:%s" % (self.company_id.tijara_fbr_pos_id or "POS", invoice_number),
            "message": "Dry-run FBR adapter accepted the invoice payload.",
        }

    def _live_response(self):
        self.ensure_one()
        endpoint = self._adapter_endpoint()
        if not endpoint:
            raise UserError("Set tijara.fbr.endpoint or Adapter Endpoint before live FBR submission.")
        if not endpoint.startswith("https://") and not self._allow_insecure_endpoint():
            raise UserError("Live FBR adapter endpoint must use HTTPS.")
        self._check_live_readiness()
        secret = self._adapter_secret()
        if not secret:
            raise UserError("Set FBR_CLIENT_SECRET or tijara.fbr.client_secret before live FBR submission.")
        client_id = self._adapter_client_id()
        body = json.dumps(self._payload_dict(), ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "Bearer %s" % secret,
            "X-Tijara-FBR-Reference": self.invoice_ref,
            "X-Idempotency-Key": self.idempotency_key,
            "X-Tijara-FBR-Environment": self.certification_environment,
            "X-Tijara-FBR-Provider": self._certified_provider_name(),
        }
        if client_id:
            headers["X-Client-ID"] = client_id
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise UserError("FBR adapter request failed: %s" % error) from error
        try:
            return json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {"status": "accepted", "raw_response": raw}

    def _validated_response_values(self, response):
        self.ensure_one()
        status = str(
            response.get("status")
            or response.get("Status")
            or response.get("result")
            or response.get("Result")
            or ""
        )
        normalized_status = status.strip().lower()
        fbr_invoice_number = (
            response.get("fbr_invoice_number")
            or response.get("invoiceNumber")
            or response.get("invoice_number")
        )
        qr_payload = response.get("qr_payload") or response.get("qrCode") or response.get("qr")
        if normalized_status and normalized_status not in {
            "accepted",
            "success",
            "successful",
            "submitted",
            "ok",
        }:
            raise UserError("FBR adapter returned a non-success status: %s" % status)
        if not fbr_invoice_number:
            raise UserError("FBR adapter response did not include an invoice number.")
        return normalized_status or "accepted", fbr_invoice_number, qr_payload

    def _submit_to_fbr_adapter(self):
        self.ensure_one()
        mode = self._adapter_mode()
        try:
            self.write(
                {
                    "submission_attempts": self.submission_attempts + 1,
                    "last_request_at": fields.Datetime.now(),
                    "signed_payload_hash": self._payload_hash(),
                    "last_certification_check_at": fields.Datetime.now(),
                }
            )
            response = self._dry_run_response() if mode == "dry_run" else self._live_response()
            response_status, fbr_invoice_number, qr_payload = self._validated_response_values(response)
            self.write(
                {
                    "adapter_mode": mode,
                    "response": json.dumps(response, indent=2, ensure_ascii=False),
                    "last_response_status": response_status,
                    "fbr_invoice_number": fbr_invoice_number,
                    "qr_payload": qr_payload,
                    "provider_invoice_uuid": response.get("provider_invoice_uuid")
                    or response.get("invoice_uuid")
                    or response.get("uuid"),
                    "sandbox_reference": response.get("sandbox_reference")
                    or response.get("certification_reference")
                    or "",
                    "compliance_status": "sandbox_passed"
                    if self.certification_environment in ("sandbox", "uat")
                    else "certified",
                    "submitted_at": fields.Datetime.now(),
                    "error_message": False,
                    "state": "submitted",
                }
            )
            if self.pos_order_id:
                self.pos_order_id.write(
                    {
                        "tijara_fbr_invoice_number": fbr_invoice_number,
                        "tijara_fbr_qr_payload": qr_payload,
                    }
                )
        except Exception as error:
            self.write(
                {
                    "error_message": str(error),
                    "submitted_at": fields.Datetime.now(),
                    "compliance_status": "failed",
                    "state": "failed",
                }
            )
            return False
        return True

    def _cron_submit_queued(self, limit=25):
        queued = self.search([("state", "=", "queued")], order="create_date", limit=limit)
        for record in queued:
            try:
                record._submit_to_fbr_adapter()
            except Exception:
                continue
