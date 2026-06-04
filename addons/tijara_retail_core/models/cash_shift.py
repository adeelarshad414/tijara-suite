from odoo import api, fields, models


class TijaraCashShift(models.Model):
    _name = "tijara.cash.shift"
    _description = "Tijara Cash Shift"
    _order = "opened_at desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    cashier_id = fields.Many2one(
        "res.users",
        string="Cashier",
        required=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    opening_balance = fields.Float(string="Opening Balance")
    expected_closing_balance = fields.Float(string="Expected Closing Balance")
    actual_closing_balance = fields.Float(string="Actual Closing Balance")
    variance = fields.Float(string="Variance", compute="_compute_variance", store=True)
    opened_at = fields.Datetime(default=fields.Datetime.now, required=True)
    closed_at = fields.Datetime()
    note = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("open", "Open"), ("closed", "Closed")],
        default="draft",
        required=True,
    )

    @api.depends("actual_closing_balance", "expected_closing_balance")
    def _compute_variance(self):
        for shift in self:
            shift.variance = (
                shift.actual_closing_balance - shift.expected_closing_balance
            )

    def action_open(self):
        for shift in self:
            if shift.name == "New":
                shift.name = self.env["ir.sequence"].next_by_code(
                    "tijara.cash.shift"
                ) or "New"
            shift.state = "open"

    def action_close(self):
        for shift in self:
            shift.closed_at = fields.Datetime.now()
            shift.state = "closed"
