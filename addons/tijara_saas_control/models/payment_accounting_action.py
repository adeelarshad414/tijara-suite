import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    refund_payment_id = fields.Many2one("account.payment", string="Refund Payment")
    draft_move_created_by_id = fields.Many2one("res.users")
    draft_move_created_at = fields.Datetime()
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
            "refund_payment_id": self.refund_payment_id.id or False,
            "amount": self.amount or 0.0,
            "status": self.status,
            "notes": self.notes or "",
            "raw_context_json": self.raw_context_json or "",
        }

    def _accounting_move_source_ref(self):
        self.ensure_one()
        references = [
            self.settlement_batch_id.name,
            self.settlement_line_id.provider_event_reference,
            self.settlement_line_id.provider_transaction_id,
            self.dispute_case_id.provider_reference,
            self.webhook_event_id.event_reference,
            self.subscription_id.database_name,
        ]
        return " / ".join(reference for reference in references if reference)

    def _ensure_approved_refund_action(self, action_type):
        self.ensure_one()
        if self.action_type != action_type:
            raise UserError(_("Accounting action %s is not a %s action.") % (self.name, action_type))
        if self.status != "approved":
            raise UserError(_("Approve accounting action %s before creating refund documents.") % self.name)
        amount = self.company_id.currency_id.round(abs(self.amount or 0.0))
        if not amount:
            raise UserError(_("Accounting action %s must have a non-zero amount.") % self.name)
        return amount

    def _refund_partner(self):
        self.ensure_one()
        partner = self.invoice_id.partner_id or self.subscription_id.customer_id
        if not partner:
            raise UserError(_("Set a customer on the source invoice or subscription before creating refund documents."))
        return partner

    def _refund_sales_journal(self):
        self.ensure_one()
        if self.invoice_id and self.invoice_id.journal_id:
            return self.invoice_id.journal_id
        if self.subscription_id:
            return self.subscription_id._tijara_sales_journal()
        journal = self.env["account.journal"].sudo().search(
            [("company_id", "=", self.company_id.id), ("type", "=", "sale")],
            limit=1,
        )
        if not journal:
            raise UserError(_("Configure a sales journal before creating refund credit notes."))
        return journal

    def _prepare_refund_credit_note_line(self, amount):
        self.ensure_one()
        source_line = self.invoice_id.invoice_line_ids[:1]
        line_values = {
            "name": _("Refund for %s") % (self.invoice_id.name or self.invoice_id.ref or self.name),
            "quantity": 1,
            "price_unit": amount,
        }
        if source_line:
            line_values.update(
                {
                    "name": _("Refund for %s") % source_line.name,
                    "product_id": source_line.product_id.id if source_line.product_id else False,
                    "account_id": source_line.account_id.id if source_line.account_id else False,
                    "tax_ids": [(6, 0, source_line.tax_ids.ids)],
                }
            )
        elif self.subscription_id.billing_product_id:
            line_values["product_id"] = self.subscription_id.billing_product_id.id
        if not line_values.get("account_id") and self.company_id.tijara_refund_account_id:
            line_values["account_id"] = self.company_id.tijara_refund_account_id.id
        return line_values

    def _create_refund_credit_note(self):
        self.ensure_one()
        amount = self._ensure_approved_refund_action("refund_credit_note")
        partner = self._refund_partner()
        journal = self._refund_sales_journal()
        move_values = {
            "move_type": "out_refund",
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "journal_id": journal.id,
            "invoice_date": fields.Date.context_today(self),
            "invoice_origin": self.invoice_id.name or self.subscription_id.name or self.name,
            "ref": "%s - %s" % (self.name, _("Refund credit note")),
            "invoice_line_ids": [(0, 0, self._prepare_refund_credit_note_line(amount))],
        }
        if self.subscription_id:
            move_values["tijara_saas_subscription_id"] = self.subscription_id.id
        if self.invoice_id and "reversed_entry_id" in self.env["account.move"]._fields:
            move_values["reversed_entry_id"] = self.invoice_id.id
        credit_note = self.env["account.move"].with_company(self.company_id).create(move_values)
        self.write(
            {
                "accounting_move_id": credit_note.id,
                "draft_move_created_by_id": self.env.user.id,
                "draft_move_created_at": fields.Datetime.now(),
            }
        )
        self.action_refresh_audit_hash()
        return credit_note

    def _create_refund_payment(self):
        self.ensure_one()
        amount = self._ensure_approved_refund_action("refund_payment")
        partner = self._refund_partner()
        journal = self.company_id.tijara_refund_payment_journal_id
        if not journal:
            raise UserError(_("Configure a Tijara refund payment journal before creating refund payments."))
        if not self._refund_payment_outstanding_account(journal):
            raise UserError(
                _(
                    "Configure an outstanding payments account on refund journal %s before creating refund payments."
                )
                % journal.display_name
            )
        payment_model = self.env["account.payment"].with_company(self.company_id)
        destination_account = self._refund_payment_destination_account(partner)
        payment_values = {
            "payment_type": "outbound",
            "partner_type": "customer",
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "amount": amount,
            "currency_id": self.company_id.currency_id.id,
            "date": fields.Date.context_today(self),
            "journal_id": journal.id,
        }
        if "destination_account_id" in payment_model._fields:
            payment_values["destination_account_id"] = destination_account.id
        payment_reference = "%s - %s" % (self.name, _("Customer refund payment"))
        if "memo" in payment_model._fields:
            payment_values["memo"] = payment_reference
        elif "ref" in payment_model._fields:
            payment_values["ref"] = payment_reference
        elif "payment_reference" in payment_model._fields:
            payment_values["payment_reference"] = payment_reference
        method_line = (
            journal.outbound_payment_method_line_ids[:1]
            if "outbound_payment_method_line_ids" in journal._fields
            else self.env["account.payment.method.line"]
        )
        if "payment_method_line_id" in payment_model._fields and method_line:
            payment_values["payment_method_line_id"] = method_line.id
        payment = payment_model.create(payment_values)
        move = payment.move_id if "move_id" in payment._fields else self.env["account.move"]
        self.write(
            {
                "refund_payment_id": payment.id,
                "accounting_move_id": move.id if move else False,
                "draft_move_created_by_id": self.env.user.id,
                "draft_move_created_at": fields.Datetime.now(),
            }
        )
        self.action_refresh_audit_hash()
        return payment

    def _refund_payment_destination_account(self, partner):
        self.ensure_one()
        company_partner = partner.with_company(self.company_id)
        destination_account = company_partner.property_account_receivable_id
        if not destination_account:
            raise UserError(
                _("Configure a customer receivable account for %s before creating refund payments.")
                % partner.display_name
            )
        return destination_account

    def _refund_payment_outstanding_account(self, journal):
        self.ensure_one()
        if "outbound_payment_method_line_ids" in journal._fields:
            method_lines = journal.outbound_payment_method_line_ids
            if method_lines and "payment_account_id" in method_lines._fields:
                payment_account = method_lines.filtered("payment_account_id")[:1].payment_account_id
                if payment_account:
                    return payment_account
        company = self.company_id
        for field_name in (
            "account_journal_payment_credit_account_id",
            "account_journal_payment_debit_account_id",
        ):
            if field_name in company._fields and company[field_name]:
                return company[field_name]
        return self.env["account.account"]

    def _configured_accounting_route(self):
        self.ensure_one()
        company = self.company_id
        routes = {
            "payout_clearing": {
                "label": _("Provider payout clearing"),
                "debit": "tijara_payment_counterpart_account_id",
                "debit_label": _("Payment counterpart account"),
                "credit": "tijara_payment_clearing_account_id",
                "credit_label": _("PSP clearing account"),
            },
            "provider_fee": {
                "label": _("Provider fee expense"),
                "debit": "tijara_provider_fee_account_id",
                "debit_label": _("Provider fee expense account"),
                "credit": "tijara_payment_clearing_account_id",
                "credit_label": _("PSP clearing account"),
            },
            "refund_credit_note": {
                "label": _("Refund or credit-note clearing"),
                "debit": "tijara_refund_account_id",
                "debit_label": _("Refund/credit note account"),
                "credit": "tijara_payment_clearing_account_id",
                "credit_label": _("PSP clearing account"),
            },
            "refund_payment": {
                "label": _("Refund payment clearing"),
                "debit": "tijara_refund_account_id",
                "debit_label": _("Refund/credit note account"),
                "credit": "tijara_payment_clearing_account_id",
                "credit_label": _("PSP clearing account"),
            },
            "chargeback_receivable": {
                "label": _("Chargeback receivable"),
                "debit": "tijara_chargeback_receivable_account_id",
                "debit_label": _("Chargeback receivable account"),
                "credit": "tijara_payment_clearing_account_id",
                "credit_label": _("PSP clearing account"),
            },
            "chargeback_fee": {
                "label": _("Chargeback fee expense"),
                "debit": "tijara_chargeback_fee_account_id",
                "debit_label": _("Chargeback fee expense account"),
                "credit": "tijara_payment_clearing_account_id",
                "credit_label": _("PSP clearing account"),
            },
            "write_off": {
                "label": _("Chargeback write-off"),
                "debit": "tijara_writeoff_account_id",
                "debit_label": _("Write-off expense account"),
                "credit": "tijara_chargeback_receivable_account_id",
                "credit_label": _("Chargeback receivable account"),
            },
        }
        if self.action_type == "manual_review":
            raise UserError(_("Manual-review accounting actions must be resolved by finance before posting."))
        route = routes.get(self.action_type)
        if not route:
            raise UserError(_("No accounting route is configured for action type %s.") % self.action_type)

        missing = []
        journal = company.tijara_payment_accounting_journal_id
        if not journal:
            missing.append(_("Payment accounting journal"))
        debit_account = company[route["debit"]]
        if not debit_account:
            missing.append(route["debit_label"])
        credit_account = company[route["credit"]]
        if not credit_account:
            missing.append(route["credit_label"])
        if missing:
            raise UserError(
                _("Configure Tijara finance accounting before creating a draft move for %(action)s: %(missing)s")
                % {
                    "action": self.name,
                    "missing": ", ".join(missing),
                }
            )
        return route, journal, debit_account, credit_account

    def _prepare_accounting_move_values(self):
        self.ensure_one()
        if self.status != "approved":
            raise UserError(_("Approve accounting action %s before creating a draft accounting move.") % self.name)
        amount = self.company_id.currency_id.round(abs(self.amount or 0.0))
        if not amount:
            raise UserError(_("Accounting action %s must have a non-zero amount.") % self.name)
        route, journal, debit_account, credit_account = self._configured_accounting_route()
        source_ref = self._accounting_move_source_ref()
        line_name = "%s - %s" % (self.name, route["label"])
        if source_ref:
            line_name = "%s (%s)" % (line_name, source_ref)
        partner = self.invoice_id.partner_id or self.subscription_id.customer_id
        debit_line = {
            "name": line_name,
            "account_id": debit_account.id,
            "debit": amount,
            "credit": 0.0,
        }
        credit_line = {
            "name": line_name,
            "account_id": credit_account.id,
            "debit": 0.0,
            "credit": amount,
        }
        if partner:
            debit_line["partner_id"] = partner.id
            credit_line["partner_id"] = partner.id
        return {
            "move_type": "entry",
            "journal_id": journal.id,
            "company_id": self.company_id.id,
            "date": fields.Date.context_today(self),
            "ref": "%s - %s" % (self.name, route["label"]),
            "line_ids": [
                (0, 0, debit_line),
                (0, 0, credit_line),
            ],
        }

    def action_create_draft_accounting_move(self):
        moves = self.env["account.move"]
        payments = self.env["account.payment"]
        for action in self:
            if action.accounting_move_id:
                moves |= action.accounting_move_id
                continue
            if action.action_type == "refund_credit_note":
                moves |= action._create_refund_credit_note()
                continue
            if action.action_type == "refund_payment":
                payment = action._create_refund_payment()
                if action.accounting_move_id:
                    moves |= action.accounting_move_id
                elif "move_id" in payment._fields and payment.move_id:
                    moves |= payment.move_id
                else:
                    payments |= payment
                continue
            move = (
                self.env["account.move"]
                .with_company(action.company_id)
                .create(action._prepare_accounting_move_values())
            )
            action.write(
                {
                    "accounting_move_id": move.id,
                    "draft_move_created_by_id": self.env.user.id,
                    "draft_move_created_at": fields.Datetime.now(),
                }
            )
            action.action_refresh_audit_hash()
            moves |= move
        if not moves and payments:
            return {
                "type": "ir.actions.act_window",
                "name": _("Draft Refund Payments"),
                "res_model": "account.payment",
                "view_mode": "list,form",
                "domain": [("id", "in", payments.ids)],
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Draft Accounting Moves"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }

    def action_post_accounting_move(self):
        moves = self.env["account.move"]
        for action in self:
            if action.status != "approved":
                raise UserError(_("Approve accounting action %s before posting its accounting move.") % action.name)
            if not action.accounting_move_id and not action.refund_payment_id:
                action.action_create_draft_accounting_move()
            if not action.accounting_move_id and action.refund_payment_id and "move_id" in action.refund_payment_id._fields:
                action.accounting_move_id = action.refund_payment_id.move_id.id
            if action.refund_payment_id:
                if action.refund_payment_id.state != "posted":
                    action.refund_payment_id.action_post()
                if "move_id" in action.refund_payment_id._fields and action.refund_payment_id.move_id:
                    action.accounting_move_id = action.refund_payment_id.move_id.id
            elif action.accounting_move_id.state != "posted":
                action.accounting_move_id.action_post()
            action.action_mark_posted()
            if action.accounting_move_id:
                moves |= action.accounting_move_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Posted Accounting Moves"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
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
