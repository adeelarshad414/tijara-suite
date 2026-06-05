import hashlib
import json

from odoo import _, api, fields, models

from .payment_settlement import PAYMENT_PROVIDERS


class TijaraSaasPaymentDispute(models.Model):
    _name = "tijara.saas.payment.dispute"
    _description = "Tijara SaaS Payment Refund and Chargeback Case"
    _order = "due_date, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    case_type = fields.Selection(
        [
            ("refund", "Refund"),
            ("chargeback", "Chargeback"),
        ],
        required=True,
        default="refund",
    )
    provider = fields.Selection(PAYMENT_PROVIDERS, required=True, default="manual")
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    subscription_id = fields.Many2one("tijara.saas.subscription")
    invoice_id = fields.Many2one("account.move")
    webhook_event_id = fields.Many2one("tijara.saas.payment.webhook.event")
    settlement_line_id = fields.Many2one("tijara.saas.payment.settlement.line")
    provider_reference = fields.Char()
    transaction_id = fields.Char()
    amount = fields.Monetary(currency_field="currency_id")
    provider_fee_amount = fields.Monetary(currency_field="currency_id")
    reason = fields.Text()
    due_date = fields.Date()
    assigned_user_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    opened_at = fields.Datetime()
    evidence_submitted_at = fields.Datetime()
    resolved_at = fields.Datetime()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("evidence", "Evidence Submitted"),
            ("won", "Won"),
            ("lost", "Lost"),
            ("refunded", "Refunded"),
            ("closed", "Closed"),
        ],
        default="draft",
        required=True,
    )
    accounting_action = fields.Selection(
        [
            ("none", "None"),
            ("manual_credit_note", "Manual Credit Note Required"),
            ("manual_refund", "Manual Refund Required"),
            ("chargeback_fee", "Chargeback Fee Required"),
        ],
        default="none",
        required=True,
    )
    evidence_summary = fields.Text()
    evidence_json = fields.Text()
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "tijara_saas_payment_dispute_attachment_rel",
        "dispute_id",
        "attachment_id",
        string="Evidence Files",
    )
    evidence_hash = fields.Char(copy=False, index=True)
    outcome_note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for case in records:
            if case.name == "New":
                prefix = "CBK" if case.case_type == "chargeback" else "REF"
                case.name = "%s-%05d" % (prefix, case.id)
        return records

    def _evidence_hash_payload(self):
        self.ensure_one()
        return {
            "name": self.name,
            "case_type": self.case_type,
            "provider": self.provider,
            "provider_reference": self.provider_reference or "",
            "transaction_id": self.transaction_id or "",
            "amount": self.amount or 0.0,
            "provider_fee_amount": self.provider_fee_amount or 0.0,
            "reason": self.reason or "",
            "evidence_summary": self.evidence_summary or "",
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
        for case in self:
            payload = json.dumps(
                case._evidence_hash_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            case.evidence_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _subscription_past_due(self, reason):
        self.ensure_one()
        if self.subscription_id:
            self.subscription_id.write(
                {
                    "payment_status": "failed",
                    "state": "past_due",
                    "suspension_reason": reason,
                }
            )

    def action_open(self):
        for case in self:
            case.write(
                {
                    "state": "open",
                    "opened_at": case.opened_at or fields.Datetime.now(),
                    "accounting_action": "chargeback_fee"
                    if case.case_type == "chargeback"
                    else "manual_refund",
                }
            )
            reason = _("%s case opened: %s") % (
                dict(case._fields["case_type"].selection)[case.case_type],
                case.reason or case.provider_reference or case.name,
            )
            case._subscription_past_due(reason)

    def action_submit_evidence(self):
        for case in self:
            case.action_refresh_evidence_hash()
            case.write(
                {
                    "state": "evidence",
                    "evidence_submitted_at": fields.Datetime.now(),
                }
            )

    def action_mark_won(self):
        for case in self:
            values = {
                "state": "won",
                "resolved_at": fields.Datetime.now(),
                "outcome_note": case.outcome_note
                or _("Provider accepted the merchant evidence."),
                "accounting_action": "none",
            }
            case.write(values)
            if case.subscription_id:
                case.subscription_id.write(
                    {
                        "payment_status": "paid",
                        "state": "active",
                        "suspension_reason": False,
                    }
                )

    def action_mark_lost(self):
        for case in self:
            case.write(
                {
                    "state": "lost",
                    "resolved_at": fields.Datetime.now(),
                    "outcome_note": case.outcome_note
                    or _("Provider ruled against the merchant."),
                    "accounting_action": "chargeback_fee"
                    if case.case_type == "chargeback"
                    else "manual_credit_note",
                }
            )
            case._subscription_past_due(
                _("Provider dispute lost: %s") % (case.provider_reference or case.name)
            )

    def action_mark_refunded(self):
        for case in self:
            case.write(
                {
                    "state": "refunded",
                    "resolved_at": fields.Datetime.now(),
                    "accounting_action": "manual_credit_note",
                    "outcome_note": case.outcome_note
                    or _("Refund completed and requires accounting confirmation."),
                }
            )
            case._subscription_past_due(
                _("Refund completed: %s") % (case.provider_reference or case.name)
            )

    def action_close(self):
        self.write({"state": "closed", "resolved_at": fields.Datetime.now()})
