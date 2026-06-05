import hashlib
import json

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


class TijaraSaasPaymentSettlementBatch(models.Model):
    _name = "tijara.saas.payment.settlement.batch"
    _description = "Tijara SaaS Payment Settlement Batch"
    _order = "settlement_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    provider = fields.Selection(PAYMENT_PROVIDERS, required=True, default="manual")
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
        string="Statement JSON",
        help="Paste provider settlement JSON. Accepted shapes: a JSON list, or an object with lines, transactions, or data.",
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
            raise UserError(_("Paste a provider settlement statement JSON payload before importing."))
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
            or ""
        ).lower()
        status = str(payload.get("status") or payload.get("payment_status") or "").lower()
        combined = "%s %s" % (event_type, status)
        if "chargeback" in combined or "dispute" in combined:
            return "chargeback"
        if "refund" in combined or "reversal" in combined or "reversed" in combined:
            return "refund"
        if "settlement" in combined or "payout" in combined:
            return "settlement"
        if event_type in {"payment", "paid", "sale", "capture", "captured"} or status in {"paid", "success", "succeeded", "completed"}:
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

    def _line_values_from_payload(self, payload, sequence):
        self.ensure_one()
        event_ref = (
            payload.get("event_reference")
            or payload.get("event_id")
            or payload.get("id")
            or payload.get("pp_TxnRefNo")
            or payload.get("transactionId")
            or payload.get("transaction_id")
            or payload.get("reference")
            or ""
        )
        transaction_id = (
            payload.get("transaction_id")
            or payload.get("transactionId")
            or payload.get("payment_intent")
            or payload.get("charge")
            or payload.get("pp_RetreivalReferenceNo")
            or payload.get("pp_TxnRefNo")
            or event_ref
            or ""
        )
        gross = self._line_amount(
            payload,
            ["gross_amount", "amount", "amount_total", "pp_Amount", "transactionAmount"],
        )
        fee = self._line_amount(
            payload,
            ["provider_fee_amount", "fee_amount", "fee", "pp_FeeAmount", "serviceCharges"],
        )
        if payload.get("net_amount") is not None:
            net = self._line_amount(payload, ["net_amount"])
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
            "provider_reference": str(payload.get("provider_reference") or payload.get("reference") or ""),
            "database_name": payload.get("database_name") or payload.get("pp_BillReference") or "",
            "invoice_ref": payload.get("invoice_ref") or payload.get("invoice_name") or payload.get("orderId") or "",
            "external_payment_reference": payload.get("external_payment_reference") or payload.get("reference") or event_ref or "",
            "payment_event_type": event_type,
            "provider_status": str(payload.get("status") or payload.get("payment_status") or payload.get("transactionStatus") or ""),
            "gross_amount": gross,
            "fee_amount": fee,
            "net_amount": net,
            "settlement_date": payload.get("settlement_date") or self.settlement_date,
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

    def action_mark_reconciled(self):
        for batch in self:
            if not batch.line_ids:
                raise UserError(_("Import settlement lines before marking the batch reconciled."))
            if batch.mismatch_line_count:
                raise UserError(_("Resolve mismatched settlement lines before marking the batch reconciled."))
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
