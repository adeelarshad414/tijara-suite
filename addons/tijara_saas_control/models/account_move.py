from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    tijara_saas_subscription_id = fields.Many2one(
        "tijara.saas.subscription",
        string="Tijara SaaS Subscription",
        index=True,
        copy=False,
    )

