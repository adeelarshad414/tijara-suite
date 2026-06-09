from odoo import api, fields, models


class TijaraExpenseRequest(models.Model):
    _name = "tijara.expense.request"
    _description = "Tijara Back Office Expense"
    _order = "expense_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    expense_date = fields.Date(default=fields.Date.context_today, required=True)
    requested_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    partner_id = fields.Many2one("res.partner", string="Vendor / Employee")
    category = fields.Selection(
        [
            ("rent", "Rent"),
            ("utilities", "Utilities"),
            ("salary", "Salary Advance"),
            ("transport", "Transport"),
            ("delivery", "Delivery"),
            ("maintenance", "Maintenance"),
            ("marketing", "Marketing"),
            ("other", "Other"),
        ],
        default="other",
        required=True,
    )
    payment_method = fields.Selection(
        [("cash", "Cash"), ("card", "Card"), ("bank", "Bank"), ("mobile", "Mobile Wallet")],
        default="cash",
        required=True,
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    tax_amount = fields.Monetary(currency_field="currency_id")
    total_amount = fields.Monetary(
        compute="_compute_total_amount",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    receipt_reference = fields.Char()
    notes = fields.Text()
    approved_by_id = fields.Many2one("res.users", copy=False)
    approved_at = fields.Datetime(copy=False)
    paid_at = fields.Datetime(copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    @api.depends("amount", "tax_amount")
    def _compute_total_amount(self):
        for expense in self:
            expense.total_amount = expense.amount + expense.tax_amount

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for expense in records:
            if expense.name == "New":
                expense.name = self.env["ir.sequence"].next_by_code("tijara.expense.request") or "New"
        return records

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_approve(self):
        self.write(
            {
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            }
        )

    def action_mark_paid(self):
        self.write({"state": "paid", "paid_at": fields.Datetime.now()})

    def action_cancel(self):
        self.write({"state": "cancelled"})


class TijaraSalaryBatch(models.Model):
    _name = "tijara.salary.batch"
    _description = "Tijara Salary Batch"
    _order = "period_start desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    line_ids = fields.One2many("tijara.salary.line", "batch_id")
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    gross_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    deduction_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    bonus_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    net_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    approved_by_id = fields.Many2one("res.users", copy=False)
    approved_at = fields.Datetime(copy=False)
    paid_at = fields.Datetime(copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()

    @api.depends("line_ids.gross_amount", "line_ids.deduction_amount", "line_ids.bonus_amount", "line_ids.net_amount")
    def _compute_totals(self):
        for batch in self:
            batch.gross_total = sum(batch.line_ids.mapped("gross_amount"))
            batch.deduction_total = sum(batch.line_ids.mapped("deduction_amount"))
            batch.bonus_total = sum(batch.line_ids.mapped("bonus_amount"))
            batch.net_total = sum(batch.line_ids.mapped("net_amount"))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for batch in records:
            if batch.name == "New":
                batch.name = self.env["ir.sequence"].next_by_code("tijara.salary.batch") or "New"
        return records

    def action_approve(self):
        self.write(
            {
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            }
        )

    def action_mark_paid(self):
        self.write({"state": "paid", "paid_at": fields.Datetime.now()})

    def action_cancel(self):
        self.write({"state": "cancelled"})


class TijaraSalaryLine(models.Model):
    _name = "tijara.salary.line"
    _description = "Tijara Salary Line"
    _order = "batch_id, employee_id, id"

    batch_id = fields.Many2one(
        "tijara.salary.batch",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one("res.partner", required=True)
    role = fields.Char()
    gross_amount = fields.Monetary(required=True, currency_field="currency_id")
    deduction_amount = fields.Monetary(currency_field="currency_id")
    bonus_amount = fields.Monetary(currency_field="currency_id")
    net_amount = fields.Monetary(
        compute="_compute_net_amount",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="batch_id.currency_id",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="batch_id.company_id",
        store=True,
    )
    notes = fields.Char()

    @api.depends("gross_amount", "deduction_amount", "bonus_amount")
    def _compute_net_amount(self):
        for line in self:
            line.net_amount = line.gross_amount - line.deduction_amount + line.bonus_amount
