import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    finance_approval_status = fields.Selection(
        [
            ("missing", "Missing Actions"),
            ("pending", "Pending Finance"),
            ("approved", "Finance Approved"),
            ("rejected", "Rejected"),
            ("blocked", "Blocked"),
            ("not_required", "Not Required"),
        ],
        default="missing",
        required=True,
    )
    finance_approved_by_id = fields.Many2one("res.users")
    finance_approved_at = fields.Datetime()
    accounting_action_ids = fields.One2many(
        "tijara.saas.payment.accounting.action",
        "dispute_case_id",
        string="Accounting Actions",
    )
    accounting_action_count = fields.Integer(compute="_compute_accounting_action_count")

    def _compute_accounting_action_count(self):
        for case in self:
            case.accounting_action_count = len(case.accounting_action_ids)

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
            case.finance_approval_status = "not_required"

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
            case.action_generate_accounting_actions()

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
            case.action_generate_accounting_actions()

    def action_close(self):
        self.write({"state": "closed", "resolved_at": fields.Datetime.now()})

    def _refresh_finance_approval_status(self):
        for case in self:
            actions = case.accounting_action_ids
            if case.state == "won" and not actions:
                case.finance_approval_status = "not_required"
                continue
            if not actions:
                case.finance_approval_status = "missing"
                continue
            statuses = set(actions.mapped("status"))
            if "rejected" in statuses:
                case.finance_approval_status = "rejected"
            elif "blocked" in statuses:
                case.finance_approval_status = "blocked"
            elif statuses.issubset({"approved", "posted"}):
                case.finance_approval_status = "approved"
            else:
                case.finance_approval_status = "pending"

    def _accounting_action_specs(self):
        self.ensure_one()
        amount = abs(self.amount or 0.0)
        fee = abs(self.provider_fee_amount or 0.0)
        context = {
            "case": self.name,
            "case_type": self.case_type,
            "provider_reference": self.provider_reference or "",
            "transaction_id": self.transaction_id or "",
            "amount": self.amount or 0.0,
            "provider_fee_amount": self.provider_fee_amount or 0.0,
            "state": self.state,
            "accounting_action": self.accounting_action,
        }
        if self.case_type == "refund":
            action_type = "refund_payment" if self.state == "refunded" else "refund_credit_note"
            return [
                {
                    "action_type": action_type,
                    "amount": amount,
                    "notes": _("Prepare refund accounting for case %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            ]
        specs = [
            {
                "action_type": "chargeback_receivable",
                "amount": amount,
                "notes": _("Track chargeback reversal for case %s.") % self.name,
                "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
            }
        ]
        if fee:
            specs.append(
                {
                    "action_type": "chargeback_fee",
                    "amount": fee,
                    "notes": _("Recognize chargeback provider fee for case %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        if self.state == "lost":
            specs.append(
                {
                    "action_type": "write_off",
                    "amount": amount,
                    "notes": _("Prepare write-off review for lost chargeback case %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        return specs

    def _ensure_accounting_action(self, spec):
        self.ensure_one()
        action_model = self.env["tijara.saas.payment.accounting.action"]
        existing = action_model.search(
            [
                ("dispute_case_id", "=", self.id),
                ("action_type", "=", spec["action_type"]),
            ],
            limit=1,
        )
        values = {
            "dispute_case_id": self.id,
            "settlement_batch_id": self.settlement_line_id.batch_id.id if self.settlement_line_id else False,
            "settlement_line_id": self.settlement_line_id.id if self.settlement_line_id else False,
            "webhook_event_id": self.webhook_event_id.id if self.webhook_event_id else False,
            "subscription_id": self.subscription_id.id if self.subscription_id else False,
            "invoice_id": self.invoice_id.id if self.invoice_id else False,
            "provider": self.provider,
            "company_id": self.company_id.id,
            "amount": spec["amount"],
            "notes": spec.get("notes"),
            "raw_context_json": spec.get("raw_context_json"),
        }
        if existing:
            if existing.status in ("draft", "pending_approval"):
                existing.write(values)
            action = existing
        else:
            action = action_model.create(dict(values, action_type=spec["action_type"]))
        if action.status == "draft":
            action.action_request_approval()
        return action

    def action_generate_accounting_actions(self):
        actions = self.env["tijara.saas.payment.accounting.action"]
        for case in self:
            for spec in case._accounting_action_specs():
                actions |= case._ensure_accounting_action(spec)
            case._refresh_finance_approval_status()
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Accounting Actions"),
            "res_model": "tijara.saas.payment.accounting.action",
            "view_mode": "list,form",
            "domain": [("id", "in", actions.ids)],
        }

    def action_approve_finance_actions(self):
        for case in self:
            if not case.accounting_action_ids:
                case.action_generate_accounting_actions()
            pending = case.accounting_action_ids.filtered(lambda action: action.status in ("draft", "pending_approval"))
            pending.action_approve()
            case.write(
                {
                    "finance_approved_by_id": self.env.user.id,
                    "finance_approved_at": fields.Datetime.now(),
                }
            )
            case._refresh_finance_approval_status()

    def action_create_draft_accounting_moves(self):
        actions = self.mapped("accounting_action_ids").filtered(lambda action: action.status == "approved")
        if not actions:
            raise UserError(_("No approved finance accounting actions are ready for draft move creation."))
        actions.action_create_draft_accounting_move()
        moves = actions.mapped("accounting_move_id")
        return {
            "type": "ir.actions.act_window",
            "name": _("Draft Accounting Moves"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }
