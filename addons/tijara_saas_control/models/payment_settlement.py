import csv
import hashlib
import io
import json
from datetime import UTC, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


PAYMENT_PROVIDERS = [
    ("manual", "Manual / Bank"),
    ("jazzcash", "JazzCash"),
    ("easypaisa", "Easypaisa"),
    ("stripe", "Stripe"),
    ("other", "Other"),
]

PAYMENT_EVENT_TYPES = [
    ("payment", "Payment"),
    ("settlement", "Settlement"),
    ("refund", "Refund"),
    ("chargeback", "Chargeback"),
    ("unknown", "Unknown"),
]

SETTLEMENT_PARSER_PROFILES = [
    ("auto", "Auto / Generic"),
    ("jazzcash_merchant_v1", "JazzCash Merchant Statement v1"),
    ("easypaisa_merchant_v1", "Easypaisa Merchant Statement v1"),
    ("stripe_balance_v1", "Stripe Balance Transaction v1"),
    ("manual_bank_v1", "Manual Bank Statement v1"),
]


class TijaraSaasPaymentSettlementBatch(models.Model):
    _name = "tijara.saas.payment.settlement.batch"
    _description = "Tijara SaaS Payment Settlement Batch"
    _order = "settlement_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    provider = fields.Selection(PAYMENT_PROVIDERS, required=True, default="manual")
    parser_profile = fields.Selection(
        SETTLEMENT_PARSER_PROFILES,
        default="auto",
        required=True,
        help="Provider-specific parser profile used to normalize statement fields.",
    )
    statement_format = fields.Selection(
        [
            ("json", "JSON"),
            ("csv", "CSV"),
        ],
        default="json",
        required=True,
    )
    provider_batch_reference = fields.Char(required=True)
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
    settlement_date = fields.Date(default=fields.Date.context_today)
    imported_by_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    imported_at = fields.Datetime()
    raw_statement_json = fields.Text(
        string="Statement Payload",
        help="Paste provider settlement JSON or CSV. JSON accepts a list, or an object with lines, transactions, or data.",
    )
    line_ids = fields.One2many(
        "tijara.saas.payment.settlement.line",
        "batch_id",
        string="Settlement Lines",
    )
    line_count = fields.Integer(compute="_compute_totals", store=True)
    matched_line_count = fields.Integer(compute="_compute_totals", store=True)
    mismatch_line_count = fields.Integer(compute="_compute_totals", store=True)
    dispute_line_count = fields.Integer(compute="_compute_totals", store=True)
    actual_gross_amount = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    actual_fee_amount = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    actual_net_amount = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    expected_gross_amount = fields.Monetary(currency_field="currency_id")
    expected_fee_amount = fields.Monetary(currency_field="currency_id")
    expected_net_amount = fields.Monetary(currency_field="currency_id")
    gross_delta = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    fee_delta = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    net_delta = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    reconciliation_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("imported", "Imported"),
            ("matched", "Matched"),
            ("mismatch", "Mismatch"),
            ("reconciled", "Reconciled"),
            ("closed", "Closed"),
        ],
        default="draft",
        required=True,
    )
    reconciled_at = fields.Datetime()
    reconciliation_note = fields.Text()
    statement_hash = fields.Char(copy=False, index=True)
    finance_approval_required = fields.Boolean(default=True)
    finance_approval_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("missing", "Missing Actions"),
            ("pending", "Pending Finance"),
            ("approved", "Finance Approved"),
            ("rejected", "Rejected"),
            ("blocked", "Blocked"),
        ],
        default="missing",
        required=True,
    )
    finance_approved_by_id = fields.Many2one("res.users")
    finance_approved_at = fields.Datetime()
    accounting_action_ids = fields.One2many(
        "tijara.saas.payment.accounting.action",
        "settlement_batch_id",
        string="Accounting Actions",
    )
    accounting_action_count = fields.Integer(compute="_compute_accounting_action_count")

    @api.depends(
        "line_ids.gross_amount",
        "line_ids.fee_amount",
        "line_ids.net_amount",
        "line_ids.reconciliation_status",
        "line_ids.payment_event_type",
        "expected_gross_amount",
        "expected_fee_amount",
        "expected_net_amount",
    )
    def _compute_totals(self):
        for batch in self:
            lines = batch.line_ids
            gross = sum(lines.mapped("gross_amount"))
            fee = sum(lines.mapped("fee_amount"))
            net = sum(lines.mapped("net_amount"))
            batch.line_count = len(lines)
            batch.matched_line_count = len(
                lines.filtered(lambda line: line.reconciliation_status in ("matched", "reconciled"))
            )
            batch.mismatch_line_count = len(
                lines.filtered(lambda line: line.reconciliation_status == "mismatch")
            )
            batch.dispute_line_count = len(
                lines.filtered(lambda line: line.payment_event_type in ("refund", "chargeback"))
            )
            batch.actual_gross_amount = gross
            batch.actual_fee_amount = fee
            batch.actual_net_amount = net
            batch.gross_delta = (batch.expected_gross_amount or 0.0) - gross
            batch.fee_delta = (batch.expected_fee_amount or 0.0) - fee
            batch.net_delta = (batch.expected_net_amount or 0.0) - net

    def _compute_accounting_action_count(self):
        for batch in self:
            batch.accounting_action_count = len(batch.accounting_action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for batch in records:
            if batch.name == "New":
                batch.name = "SET-%05d" % batch.id
        return records

    @api.model
    def _payload_float(self, value):
        try:
            if isinstance(value, str):
                value = (
                    value.replace(",", "")
                    .replace("PKR", "")
                    .replace("Rs.", "")
                    .replace("Rs", "")
                    .strip()
                )
                if value.startswith("(") and value.endswith(")"):
                    value = "-%s" % value[1:-1]
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @api.model
    def _hash_payload(self, payload):
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _statement_lines(self):
        self.ensure_one()
        if not self.raw_statement_json:
            raise UserError(_("Paste a provider settlement statement payload before importing."))
        if self.statement_format == "csv":
            reader = csv.DictReader(io.StringIO(self.raw_statement_json.strip()))
            lines = [dict(line) for line in reader]
            payload = {
                "format": "csv",
                "provider": self.provider,
                "parser_profile": self.parser_profile,
                "lines": lines,
            }
        else:
            try:
                payload = json.loads(self.raw_statement_json)
            except json.JSONDecodeError as error:
                raise UserError(_("Settlement statement JSON is invalid: %s") % error) from error
            if isinstance(payload, list):
                lines = payload
            elif isinstance(payload, dict):
                lines = payload.get("lines") or payload.get("transactions") or payload.get("data")
            else:
                lines = []
        if not isinstance(lines, list) or not lines:
            raise UserError(_("Settlement statement must contain a non-empty list of lines."))
        if not all(isinstance(line, dict) for line in lines):
            raise UserError(_("Every settlement statement line must be a JSON object."))
        return payload, lines

    def _line_event_type(self, payload):
        event_type = str(
            payload.get("payment_event_type")
            or payload.get("event_type")
            or payload.get("type")
            or payload.get("transaction_type")
            or payload.get("pp_TxnType")
            or payload.get("reporting_category")
            or payload.get("source_type")
            or payload.get("debit_credit")
            or ""
        ).lower()
        status = str(
            payload.get("status")
            or payload.get("payment_status")
            or payload.get("transactionStatus")
            or payload.get("pp_ResponseMessage")
            or ""
        ).lower()
        combined = "%s %s" % (event_type, status)
        if "chargeback" in combined or "dispute" in combined:
            return "chargeback"
        if "refund" in combined or "reversal" in combined or "reversed" in combined:
            return "refund"
        if "settlement" in combined or "payout" in combined:
            return "settlement"
        if event_type in {"charge", "payment", "paid", "sale", "capture", "captured", "credit"} or status in {"paid", "success", "succeeded", "completed", "settled"}:
            return "payment"
        return "unknown"

    def _line_amount(self, payload, keys, stripe_cents=True):
        for key in keys:
            if payload.get(key) is None:
                continue
            value = self._payload_float(payload.get(key))
            if self.provider == "stripe" and stripe_cents:
                return value / 100.0
            return value
        return 0.0

    def _line_date(self, payload):
        for key in [
            "settlement_date",
            "value_date",
            "posting_date",
            "available_on",
            "created",
            "pp_TxnDateTime",
            "transactionDate",
        ]:
            value = payload.get(key)
            if value in (None, ""):
                continue
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit() and len(value) >= 9):
                return datetime.fromtimestamp(int(value), UTC).date()
            try:
                return fields.Date.to_date(value)
            except (TypeError, ValueError):
                continue
        return self.settlement_date

    def _line_values_from_payload(self, payload, sequence):
        self.ensure_one()
        event_ref = (
            payload.get("event_reference")
            or payload.get("event_id")
            or payload.get("id")
            or payload.get("balance_transaction")
            or payload.get("pp_TxnRefNo")
            or payload.get("transactionId")
            or payload.get("transaction_id")
            or payload.get("bank_reference")
            or payload.get("deposit_reference")
            or payload.get("settlement_reference")
            or payload.get("reference")
            or ""
        )
        transaction_id = (
            payload.get("transaction_id")
            or payload.get("transactionId")
            or payload.get("payment_intent")
            or payload.get("charge")
            or payload.get("source")
            or payload.get("pp_RetreivalReferenceNo")
            or payload.get("pp_TxnRefNo")
            or payload.get("rrn")
            or payload.get("bank_trace")
            or event_ref
            or ""
        )
        gross = self._line_amount(
            payload,
            ["gross_amount", "amount", "amount_total", "pp_Amount", "transactionAmount", "deposit_amount", "credit_amount", "debit_amount"],
        )
        fee = self._line_amount(
            payload,
            ["provider_fee_amount", "fee_amount", "fee", "pp_FeeAmount", "serviceCharges", "bank_fee", "charges"],
        )
        if payload.get("net_amount") is not None or payload.get("net") is not None or payload.get("settled_amount") is not None:
            net = self._line_amount(payload, ["net_amount", "net", "settled_amount"])
        else:
            net = gross - fee
        event_type = self._line_event_type(payload)
        signed_payload = dict(payload, _provider=self.provider, _event_reference=event_ref)
        return {
            "batch_id": self.id,
            "sequence": sequence,
            "provider": self.provider,
            "company_id": self.company_id.id,
            "provider_event_reference": str(event_ref or ""),
            "provider_transaction_id": str(transaction_id or ""),
            "provider_reference": str(
                payload.get("provider_reference")
                or payload.get("orderId")
                or payload.get("bank_reference")
                or payload.get("reference")
                or ""
            ),
            "database_name": payload.get("database_name")
            or payload.get("metadata_database_name")
            or payload.get("tenant_database")
            or payload.get("database")
            or payload.get("pp_BillReference")
            or payload.get("accountNum")
            or "",
            "invoice_ref": payload.get("invoice_ref")
            or payload.get("invoice_name")
            or payload.get("invoice")
            or payload.get("invoice_number")
            or payload.get("orderId")
            or payload.get("pp_BillReference")
            or "",
            "external_payment_reference": payload.get("external_payment_reference")
            or payload.get("orderId")
            or payload.get("pp_TxnRefNo")
            or payload.get("source")
            or payload.get("reference")
            or event_ref
            or "",
            "payment_event_type": event_type,
            "provider_status": str(
                payload.get("status")
                or payload.get("payment_status")
                or payload.get("transactionStatus")
                or payload.get("pp_ResponseMessage")
                or payload.get("description")
                or ""
            ),
            "gross_amount": gross,
            "fee_amount": fee,
            "net_amount": net,
            "settlement_date": self._line_date(payload),
            "raw_line_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            "line_hash": self._hash_payload(signed_payload),
        }

    def action_import_statement_payload(self):
        for batch in self:
            statement_payload, lines = batch._statement_lines()
            if batch.line_ids:
                batch.line_ids.unlink()
            line_values = [
                batch._line_values_from_payload(line, sequence)
                for sequence, line in enumerate(lines, start=1)
            ]
            self.env["tijara.saas.payment.settlement.line"].create(line_values)
            batch.write(
                {
                    "statement_hash": batch._hash_payload(statement_payload),
                    "imported_at": fields.Datetime.now(),
                    "imported_by_id": self.env.user.id,
                    "reconciliation_status": "imported",
                }
            )
            batch.action_match_lines()

    def action_match_lines(self):
        for batch in self:
            batch.line_ids.action_match_records()
            if not batch.line_ids:
                batch.reconciliation_status = "draft"
            elif batch.mismatch_line_count:
                batch.reconciliation_status = "mismatch"
            elif batch.matched_line_count == batch.line_count:
                batch.reconciliation_status = "matched"
            else:
                batch.reconciliation_status = "imported"

    def action_create_dispute_cases(self):
        for batch in self:
            batch.line_ids.filtered(
                lambda line: line.payment_event_type in ("refund", "chargeback")
            ).action_create_dispute_case()

    def _refresh_finance_approval_status(self):
        for batch in self:
            if not batch.finance_approval_required:
                batch.finance_approval_status = "not_required"
                continue
            actions = batch.accounting_action_ids
            if not actions:
                batch.finance_approval_status = "missing"
                continue
            statuses = set(actions.mapped("status"))
            if "rejected" in statuses:
                batch.finance_approval_status = "rejected"
            elif "blocked" in statuses:
                batch.finance_approval_status = "blocked"
            elif statuses.issubset({"approved", "posted"}):
                batch.finance_approval_status = "approved"
            else:
                batch.finance_approval_status = "pending"

    def action_generate_accounting_actions(self):
        action_model = self.env["tijara.saas.payment.accounting.action"]
        generated = action_model
        for batch in self:
            for line in batch.line_ids:
                generated |= line._generate_accounting_action_records()
            batch._refresh_finance_approval_status()
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Accounting Actions"),
            "res_model": "tijara.saas.payment.accounting.action",
            "view_mode": "list,form",
            "domain": [("id", "in", generated.ids)],
        }

    def action_approve_finance_actions(self):
        for batch in self:
            if not batch.accounting_action_ids:
                batch.action_generate_accounting_actions()
            pending = batch.accounting_action_ids.filtered(lambda action: action.status in ("draft", "pending_approval"))
            pending.action_approve()
            batch.write(
                {
                    "finance_approved_by_id": self.env.user.id,
                    "finance_approved_at": fields.Datetime.now(),
                }
            )
            batch._refresh_finance_approval_status()

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

    def action_mark_reconciled(self):
        for batch in self:
            if not batch.line_ids:
                raise UserError(_("Import settlement lines before marking the batch reconciled."))
            if batch.mismatch_line_count:
                raise UserError(_("Resolve mismatched settlement lines before marking the batch reconciled."))
            batch._refresh_finance_approval_status()
            if batch.finance_approval_required and batch.finance_approval_status != "approved":
                raise UserError(_("Generate and approve finance accounting actions before marking the settlement reconciled."))
            batch.line_ids.filtered(lambda line: line.reconciliation_status == "matched").write(
                {
                    "reconciliation_status": "reconciled",
                    "reconciled_at": fields.Datetime.now(),
                }
            )
            batch.write(
                {
                    "reconciliation_status": "reconciled",
                    "reconciled_at": fields.Datetime.now(),
                    "reconciliation_note": _("Settlement batch reconciled by %s.") % self.env.user.display_name,
                }
            )

    def action_close(self):
        self.write({"reconciliation_status": "closed"})


class TijaraSaasPaymentSettlementLine(models.Model):
    _name = "tijara.saas.payment.settlement.line"
    _description = "Tijara SaaS Payment Settlement Line"
    _order = "batch_id, sequence, id"

    name = fields.Char(default="New", required=True, copy=False)
    batch_id = fields.Many2one(
        "tijara.saas.payment.settlement.batch",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    provider = fields.Selection(PAYMENT_PROVIDERS, required=True, default="manual")
    company_id = fields.Many2one("res.company", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    provider_event_reference = fields.Char(index=True)
    provider_transaction_id = fields.Char(index=True)
    provider_reference = fields.Char()
    database_name = fields.Char()
    invoice_ref = fields.Char()
    external_payment_reference = fields.Char()
    payment_event_type = fields.Selection(PAYMENT_EVENT_TYPES, default="unknown", required=True)
    provider_status = fields.Char()
    gross_amount = fields.Monetary(currency_field="currency_id")
    fee_amount = fields.Monetary(currency_field="currency_id")
    net_amount = fields.Monetary(currency_field="currency_id")
    settlement_date = fields.Date()
    webhook_event_id = fields.Many2one("tijara.saas.payment.webhook.event")
    subscription_id = fields.Many2one("tijara.saas.subscription")
    invoice_id = fields.Many2one("account.move")
    dispute_case_id = fields.Many2one("tijara.saas.payment.dispute")
    accounting_action_ids = fields.One2many(
        "tijara.saas.payment.accounting.action",
        "settlement_line_id",
        string="Accounting Actions",
    )
    accounting_action_count = fields.Integer(compute="_compute_accounting_action_count")
    reconciliation_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("matched", "Matched"),
            ("mismatch", "Mismatch"),
            ("reconciled", "Reconciled"),
        ],
        default="pending",
        required=True,
    )
    reconciled_at = fields.Datetime()
    reconciliation_note = fields.Text()
    raw_line_json = fields.Text()
    line_hash = fields.Char(copy=False, index=True)

    def _compute_accounting_action_count(self):
        for line in self:
            line.accounting_action_count = len(line.accounting_action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            if line.name == "New":
                line.name = "SETL-%05d" % line.id
        return records

    def _match_webhook_event(self):
        self.ensure_one()
        event_model = self.env["tijara.saas.payment.webhook.event"].sudo()
        domain = [("provider", "=", self.provider)]
        if self.provider_event_reference:
            event = event_model.search(
                domain + [("event_reference", "=", self.provider_event_reference)],
                limit=1,
            )
            if event:
                return event
        if self.provider_transaction_id:
            return event_model.search(
                domain + [("transaction_id", "=", self.provider_transaction_id)],
                limit=1,
            )
        return event_model

    def _match_subscription(self):
        self.ensure_one()
        subscription_model = self.env["tijara.saas.subscription"].sudo()
        if self.database_name:
            subscription = subscription_model.search(
                [("database_name", "=", self.database_name)],
                limit=1,
            )
            if subscription:
                return subscription
        if self.external_payment_reference:
            return subscription_model.search(
                [("external_payment_reference", "=", self.external_payment_reference)],
                limit=1,
            )
        return subscription_model

    def _match_invoice(self):
        self.ensure_one()
        if not self.invoice_ref:
            return self.env["account.move"]
        return self.env["account.move"].sudo().search(
            [
                "|",
                ("name", "=", self.invoice_ref),
                ("ref", "=", self.invoice_ref),
            ],
            limit=1,
        )

    def action_match_records(self):
        for line in self:
            event = line._match_webhook_event()
            invoice = event.invoice_id or line._match_invoice()
            subscription = (
                event.subscription_id
                or invoice.tijara_saas_subscription_id
                or line._match_subscription()
            )
            values = {
                "webhook_event_id": event.id if event else False,
                "invoice_id": invoice.id if invoice else False,
                "subscription_id": subscription.id if subscription else False,
            }
            if event or subscription or invoice:
                values.update(
                    {
                        "reconciliation_status": "matched",
                        "reconciliation_note": _("Matched settlement line to available Tijara billing records."),
                    }
                )
            else:
                values.update(
                    {
                        "reconciliation_status": "mismatch",
                        "reconciliation_note": _("No matching webhook, subscription, or invoice was found."),
                    }
                )
            line.write(values)

    def action_mark_mismatch(self):
        self.write(
            {
                "reconciliation_status": "mismatch",
                "reconciliation_note": _("Marked mismatch by %s.") % self.env.user.display_name,
            }
        )

    def action_mark_reconciled(self):
        self.write(
            {
                "reconciliation_status": "reconciled",
                "reconciled_at": fields.Datetime.now(),
                "reconciliation_note": _("Settlement line reconciled by %s.") % self.env.user.display_name,
            }
        )

    def _accounting_action_specs(self):
        self.ensure_one()
        specs = []
        absolute_gross = abs(self.gross_amount or 0.0)
        absolute_fee = abs(self.fee_amount or 0.0)
        absolute_net = abs(self.net_amount or 0.0)
        context = {
            "line": self.name,
            "batch": self.batch_id.name,
            "provider_event_reference": self.provider_event_reference or "",
            "provider_transaction_id": self.provider_transaction_id or "",
            "payment_event_type": self.payment_event_type,
            "gross_amount": self.gross_amount or 0.0,
            "fee_amount": self.fee_amount or 0.0,
            "net_amount": self.net_amount or 0.0,
        }
        if absolute_fee:
            specs.append(
                {
                    "action_type": "provider_fee",
                    "amount": absolute_fee,
                    "notes": _("Recognize PSP/provider fee from settlement line %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        if self.payment_event_type in ("payment", "settlement"):
            specs.append(
                {
                    "action_type": "payout_clearing",
                    "amount": absolute_net or absolute_gross,
                    "notes": _("Clear provider payout or external payment against settlement line %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        elif self.payment_event_type == "refund":
            specs.append(
                {
                    "action_type": "refund_credit_note",
                    "amount": absolute_gross,
                    "notes": _("Prepare refund credit note for settlement line %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        elif self.payment_event_type == "chargeback":
            specs.append(
                {
                    "action_type": "chargeback_receivable",
                    "amount": absolute_gross,
                    "notes": _("Track chargeback receivable or reversal for settlement line %s.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        else:
            specs.append(
                {
                    "action_type": "manual_review",
                    "amount": absolute_net or absolute_gross,
                    "notes": _("Review unknown settlement line %s before finance closeout.") % self.name,
                    "raw_context_json": json.dumps(context, ensure_ascii=False, sort_keys=True),
                }
            )
        return specs

    def _ensure_accounting_action(self, spec):
        self.ensure_one()
        action_model = self.env["tijara.saas.payment.accounting.action"]
        existing = action_model.search(
            [
                ("settlement_line_id", "=", self.id),
                ("action_type", "=", spec["action_type"]),
            ],
            limit=1,
        )
        values = {
            "settlement_batch_id": self.batch_id.id,
            "settlement_line_id": self.id,
            "webhook_event_id": self.webhook_event_id.id if self.webhook_event_id else False,
            "dispute_case_id": self.dispute_case_id.id if self.dispute_case_id else False,
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

    def _generate_accounting_action_records(self):
        actions = self.env["tijara.saas.payment.accounting.action"]
        for line in self:
            for spec in line._accounting_action_specs():
                actions |= line._ensure_accounting_action(spec)
            line.batch_id._refresh_finance_approval_status()
        return actions

    def action_generate_accounting_actions(self):
        actions = self._generate_accounting_action_records()
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Accounting Actions"),
            "res_model": "tijara.saas.payment.accounting.action",
            "view_mode": "list,form",
            "domain": [("id", "in", actions.ids)],
        }

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

    def action_create_dispute_case(self):
        dispute_model = self.env["tijara.saas.payment.dispute"].sudo()
        for line in self:
            if line.payment_event_type not in ("refund", "chargeback"):
                continue
            existing = dispute_model.search(
                [("settlement_line_id", "=", line.id)],
                limit=1,
            )
            if existing:
                line.dispute_case_id = existing.id
                continue
            case = dispute_model.create(
                {
                    "name": "New",
                    "case_type": line.payment_event_type,
                    "provider": line.provider,
                    "company_id": line.company_id.id,
                    "subscription_id": line.subscription_id.id if line.subscription_id else False,
                    "invoice_id": line.invoice_id.id if line.invoice_id else False,
                    "webhook_event_id": line.webhook_event_id.id if line.webhook_event_id else False,
                    "settlement_line_id": line.id,
                    "provider_reference": line.provider_event_reference or line.provider_transaction_id,
                    "transaction_id": line.provider_transaction_id,
                    "amount": abs(line.gross_amount or 0.0),
                    "provider_fee_amount": abs(line.fee_amount or 0.0),
                    "reason": line.provider_status or line.reconciliation_note or "",
                    "due_date": fields.Date.context_today(self),
                }
            )
            line.dispute_case_id = case.id
            case.action_open()
