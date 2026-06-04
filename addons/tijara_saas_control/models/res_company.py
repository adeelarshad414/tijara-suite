import os

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

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
