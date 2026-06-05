import hashlib
import json

from odoo import _, api, fields, models

from .payment_settlement import PAYMENT_PROVIDERS


ACCOUNTING_ACTION_TYPES = [
    ("payout_clearing", "Payout Clearing"),
    ("provider_fee", "Provider Fee"),
    ("refund_credit_note", "Refund Credit Note"),
    ("refund_payment", "Refund Payment"),
    ("chargeback_receivable", "Chargeback Receivable"),
    ("chargeback_fee", "Chargeback Fee"),
    ("write_off", "Write-Off"),
    ("manual_review", "Manual Review"),
]


class TijaraSaasPaymentAccountingAction(models.Model):
    _name = "tijara.saas.payment.accounting.action"
    _description = "Tijara SaaS Payment Accounting Action"
    _order = "requested_at desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    action_type = fields.Selection(ACCOUNTING_ACTION_TYPES, required=True)
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
    settlement_batch_id = fields.Many2one("tijara.saas.payment.settlement.batch")
    settlement_line_id = fields.Many2one("tijara.saas.payment.settlement.line")
    dispute_case_id = fields.Many2one("tijara.saas.payment.dispute")
    webhook_event_id = fields.Many2one("tijara.saas.payment.webhook.event")
    subscription_id = fields.Many2one("tijara.saas.subscription")
    invoice_id = fields.Many2one("account.move")
    accounting_move_id = fields.Many2one("account.move", string="Accounting Move")
    amount = fields.Monetary(currency_field="currency_id")
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("posted", "Posted"),
            ("blocked", "Blocked"),
        ],
        default="draft",
        required=True,
    )
    requested_by_id = fields.Many2one("res.users")
    requested_at = fields.Datetime()
    approval_user_id = fields.Many2one("res.users")
    approved_at = fields.Datetime()
    posted_at = fields.Datetime()
    rejection_reason = fields.Text()
    notes = fields.Text()
    raw_context_json = fields.Text()
    audit_hash = fields.Char(copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for action in records:
            if action.name == "New":
                action.name = "PACT-%05d" % action.id
        return records

    def _audit_hash_payload(self):
        self.ensure_one()
        return {
            "name": self.name,
            "action_type": self.action_type,
            "provider": self.provider,
            "settlement_batch_id": self.settlement_batch_id.id or False,
            "settlement_line_id": self.settlement_line_id.id or False,
            "dispute_case_id": self.dispute_case_id.id or False,
            "webhook_event_id": self.webhook_event_id.id or False,
            "subscription_id": self.subscription_id.id or False,
            "invoice_id": self.invoice_id.id or False,
            "accounting_move_id": self.accounting_move_id.id or False,
            "amount": self.amount or 0.0,
            "status": self.status,
            "notes": self.notes or "",
            "raw_context_json": self.raw_context_json or "",
        }

    def action_refresh_audit_hash(self):
        for action in self:
            payload = json.dumps(
                action._audit_hash_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            action.audit_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def action_request_approval(self):
        for action in self:
            action.write(
                {
                    "status": "pending_approval",
                    "requested_by_id": action.requested_by_id.id or self.env.user.id,
                    "requested_at": action.requested_at or fields.Datetime.now(),
                }
            )
            action.action_refresh_audit_hash()

    def action_approve(self):
        for action in self:
            action.write(
                {
                    "status": "approved",
                    "approval_user_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                    "rejection_reason": False,
                }
            )
            action.action_refresh_audit_hash()

    def action_reject(self):
        for action in self:
            action.write(
                {
                    "status": "rejected",
                    "approval_user_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                    "rejection_reason": action.rejection_reason
                    or _("Finance rejected this accounting action."),
                }
            )
            action.action_refresh_audit_hash()

    def action_mark_posted(self):
        for action in self:
            action.write(
                {
                    "status": "posted",
                    "posted_at": fields.Datetime.now(),
                }
            )
            action.action_refresh_audit_hash()

    def action_mark_blocked(self):
        for action in self:
            action.write(
                {
                    "status": "blocked",
                    "notes": action.notes
                    or _("Accounting action blocked until finance configuration is complete."),
                }
            )
            action.action_refresh_audit_hash()
