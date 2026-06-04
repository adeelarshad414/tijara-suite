from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TijaraSaasSubscription(models.Model):
    _name = "tijara.saas.subscription"
    _description = "Tijara SaaS Subscription"
    _order = "start_date desc, id desc"

    name = fields.Char(required=True)
    tenant_name = fields.Char(required=True)
    database_name = fields.Char(required=True)
    plan_id = fields.Many2one("tijara.saas.plan", required=True)
    feature_ids = fields.Many2many(
        "tijara.saas.feature",
        "tijara_saas_subscription_feature_rel",
        "subscription_id",
        "feature_id",
        string="Extra Features",
    )
    effective_feature_ids = fields.Many2many(
        "tijara.saas.feature",
        compute="_compute_effective_feature_ids",
        string="Effective Features",
    )
    customer_id = fields.Many2one("res.partner", string="Billing Customer")
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
    start_date = fields.Date(default=fields.Date.context_today)
    next_invoice_date = fields.Date()
    billing_cycle = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("annual", "Annual"),
        ],
        default="monthly",
        required=True,
    )
    billing_amount = fields.Monetary(
        currency_field="currency_id",
        help="Optional override. When empty, the plan monthly or annual price is used.",
    )
    billing_product_id = fields.Many2one(
        "product.product",
        string="Billing Product",
        default=lambda self: self.env.ref(
            "tijara_saas_control.product_tijara_saas_subscription",
            raise_if_not_found=False,
        ),
    )
    last_invoice_date = fields.Date()
    last_invoice_id = fields.Many2one("account.move", string="Last Invoice")
    invoice_ids = fields.One2many(
        "account.move",
        "tijara_saas_subscription_id",
        string="Subscription Invoices",
    )
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    payment_provider = fields.Selection(
        [
            ("manual", "Manual / Bank"),
            ("jazzcash", "JazzCash"),
            ("easypaisa", "Easypaisa"),
            ("stripe", "Stripe"),
            ("other", "Other"),
        ],
        default="manual",
    )
    payment_status = fields.Selection(
        [
            ("not_invoiced", "Not Invoiced"),
            ("invoiced", "Invoiced"),
            ("paid", "Paid"),
            ("past_due", "Past Due"),
            ("failed", "Failed"),
        ],
        default="not_invoiced",
        required=True,
    )
    external_payment_reference = fields.Char()
    paid_at = fields.Datetime()
    dunning_level = fields.Integer(default=0)
    grace_until = fields.Date()
    last_dunning_at = fields.Datetime()
    suspension_reason = fields.Text()
    user_limit_override = fields.Integer()
    branch_limit_override = fields.Integer()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("trial", "Trial"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()
    current_user_count = fields.Integer(compute="_compute_usage_counts")
    current_branch_count = fields.Integer(compute="_compute_usage_counts")
    limit_status = fields.Selection(
        [
            ("ok", "Within Limits"),
            ("warning", "Near Limit"),
            ("exceeded", "Exceeded"),
        ],
        compute="_compute_usage_counts",
    )

    @api.depends("plan_id.feature_ids", "feature_ids")
    def _compute_effective_feature_ids(self):
        for subscription in self:
            subscription.effective_feature_ids = (
                subscription.plan_id.feature_ids | subscription.feature_ids
            )

    def _compute_usage_counts(self):
        for subscription in self:
            user_count = self.env["res.users"].sudo().search_count(
                [("company_ids", "in", subscription.company_id.id), ("share", "=", False)]
            )
            branch_count = 1
            user_limit = subscription.user_limit_override or subscription.plan_id.user_limit
            branch_limit = subscription.branch_limit_override or subscription.plan_id.branch_limit
            limit_status = "ok"
            if (user_limit and user_count > user_limit) or (branch_limit and branch_count > branch_limit):
                limit_status = "exceeded"
            elif (user_limit and user_count >= user_limit * 0.9) or (
                branch_limit and branch_count >= branch_limit * 0.9
            ):
                limit_status = "warning"
            subscription.current_user_count = user_count
            subscription.current_branch_count = branch_count
            subscription.limit_status = limit_status

    def _compute_invoice_count(self):
        for subscription in self:
            subscription.invoice_count = len(subscription.invoice_ids)

    def has_feature(self, feature_code):
        self.ensure_one()
        return feature_code in self.effective_feature_ids.mapped("code")

    def action_check_plan_limits(self):
        for subscription in self:
            subscription.notes = (
                "%s\nPlan limit check: users=%s, branches=%s, status=%s"
                % (
                    subscription.notes or "",
                    subscription.current_user_count,
                    subscription.current_branch_count,
                    subscription.limit_status,
                )
            ).strip()

    def _tijara_subscription_price(self):
        self.ensure_one()
        if self.billing_amount:
            return self.billing_amount
        if self.billing_cycle == "annual":
            return self.plan_id.annual_price or self.plan_id.monthly_price * 12
        return self.plan_id.monthly_price

    def _tijara_next_invoice_date(self, invoice_date):
        self.ensure_one()
        invoice_date = fields.Date.to_date(invoice_date)
        delta = relativedelta(years=1) if self.billing_cycle == "annual" else relativedelta(months=1)
        return invoice_date + delta

    def _tijara_sales_journal(self):
        self.ensure_one()
        journal = self.env["account.journal"].sudo().search(
            [("company_id", "=", self.company_id.id), ("type", "=", "sale")],
            limit=1,
        )
        if not journal:
            raise UserError(_("Configure a sales journal before generating SaaS invoices."))
        return journal

    def action_generate_subscription_invoice(self):
        invoices = self.env["account.move"]
        today = fields.Date.context_today(self)
        for subscription in self:
            if not subscription.customer_id:
                raise UserError(_("Set a billing customer before generating a subscription invoice."))
            price = subscription._tijara_subscription_price()
            if price <= 0:
                raise UserError(_("Set a subscription price before generating an invoice."))
            journal = subscription._tijara_sales_journal()
            product = subscription.billing_product_id
            line_values = {
                "name": "%s - %s SaaS subscription"
                % (subscription.name, dict(subscription._fields["billing_cycle"].selection)[subscription.billing_cycle]),
                "quantity": 1,
                "price_unit": price,
            }
            if product:
                line_values["product_id"] = product.id
            invoice = (
                self.env["account.move"]
                .with_company(subscription.company_id)
                .create(
                    {
                        "move_type": "out_invoice",
                        "partner_id": subscription.customer_id.id,
                        "company_id": subscription.company_id.id,
                        "journal_id": journal.id,
                        "invoice_date": today,
                        "invoice_origin": subscription.name,
                        "ref": subscription.database_name,
                        "tijara_saas_subscription_id": subscription.id,
                        "invoice_line_ids": [(0, 0, line_values)],
                    }
                )
            )
            subscription.write(
                {
                    "last_invoice_id": invoice.id,
                    "last_invoice_date": today,
                    "next_invoice_date": subscription._tijara_next_invoice_date(today),
                    "payment_status": "invoiced",
                    "state": "active" if subscription.state in ("draft", "trial") else subscription.state,
                }
            )
            invoices |= invoice
        return {
            "type": "ir.actions.act_window",
            "name": _("Subscription Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
        }

    def action_sync_billing_status(self):
        today = fields.Date.context_today(self)
        for subscription in self:
            invoice = subscription.last_invoice_id
            status = subscription.payment_status
            if invoice:
                if invoice.payment_state in ("paid", "in_payment"):
                    status = "paid"
                elif subscription.next_invoice_date and subscription.next_invoice_date < today:
                    status = "past_due"
                else:
                    status = "invoiced"
            elif subscription.next_invoice_date and subscription.next_invoice_date < today:
                status = "past_due"
            subscription.payment_status = status
            if status == "past_due" and subscription.state == "active":
                subscription.state = "past_due"

    def _tijara_dunning_grace_days(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "tijara.saas.dunning_grace_days",
            "7",
        )
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 7

    def action_run_dunning(self):
        today = fields.Date.context_today(self)
        grace_days = self._tijara_dunning_grace_days()
        for subscription in self:
            subscription.action_sync_billing_status()
            if subscription.payment_status != "past_due":
                continue
            grace_until = subscription.grace_until
            if not grace_until:
                base_date = subscription.next_invoice_date or today
                grace_until = fields.Date.to_date(base_date) + relativedelta(days=grace_days)
                subscription.write(
                    {
                        "state": "past_due",
                        "dunning_level": max(subscription.dunning_level, 1),
                        "grace_until": grace_until,
                        "last_dunning_at": fields.Datetime.now(),
                    }
                )
            elif grace_until < today:
                subscription.write(
                    {
                        "state": "suspended",
                        "dunning_level": max(subscription.dunning_level + 1, 3),
                        "last_dunning_at": fields.Datetime.now(),
                        "suspension_reason": _(
                            "Subscription suspended after unpaid invoice grace period ended on %s."
                        )
                        % grace_until,
                    }
                )
            else:
                subscription.write(
                    {
                        "state": "past_due",
                        "dunning_level": max(subscription.dunning_level + 1, 2),
                        "last_dunning_at": fields.Datetime.now(),
                    }
                )

    def action_mark_paid_external(self):
        for subscription in self:
            if not subscription.last_invoice_id:
                raise UserError(_("Generate an invoice before recording an external payment."))
            subscription.write(
                {
                    "payment_status": "paid",
                    "paid_at": fields.Datetime.now(),
                    "state": "active",
                    "dunning_level": 0,
                    "grace_until": False,
                    "suspension_reason": False,
                }
            )

    def action_start_trial(self):
        self.write({"state": "trial"})

    def action_activate(self):
        self.write({"state": "active"})

    def action_suspend(self):
        self.write({"state": "suspended"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
