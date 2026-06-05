import os

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tijara_payment_accounting_journal_id = fields.Many2one(
        "account.journal",
        string="Tijara Payment Accounting Journal",
        help="General journal used for draft PSP settlement, refund, chargeback, and write-off entries.",
    )
    tijara_payment_clearing_account_id = fields.Many2one(
        "account.account",
        string="Tijara PSP Clearing Account",
        help="Clearing account used while provider payouts, fees, refunds, and disputes are reconciled.",
    )
    tijara_payment_counterpart_account_id = fields.Many2one(
        "account.account",
        string="Tijara Payment Counterpart Account",
        help="Bank, suspense, or receivable account balanced against provider payout clearing entries.",
    )
    tijara_provider_fee_account_id = fields.Many2one(
        "account.account",
        string="Tijara Provider Fee Expense Account",
    )
    tijara_refund_account_id = fields.Many2one(
        "account.account",
        string="Tijara Refund/Credit Note Account",
    )
    tijara_chargeback_receivable_account_id = fields.Many2one(
        "account.account",
        string="Tijara Chargeback Receivable Account",
    )
    tijara_chargeback_fee_account_id = fields.Many2one(
        "account.account",
        string="Tijara Chargeback Fee Expense Account",
    )
    tijara_writeoff_account_id = fields.Many2one(
        "account.account",
        string="Tijara Write-Off Expense Account",
    )

    def tijara_saas_enforcement_enabled(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "tijara.saas.enforcement_enabled",
            os.environ.get("TIJARA_SAAS_ENFORCEMENT_ENABLED", "0"),
        )
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def tijara_active_subscription(self):
        self.ensure_one()
        return self.env["tijara.saas.subscription"].sudo().search(
            [
                ("company_id", "=", self.id),
                ("state", "in", ("trial", "active")),
            ],
            order="start_date desc, id desc",
            limit=1,
        )

    def tijara_has_saas_feature(self, feature_code):
        self.ensure_one()
        if not self.tijara_saas_enforcement_enabled():
            return True
        subscription = self.tijara_active_subscription()
        return bool(subscription and subscription.has_feature(feature_code))
