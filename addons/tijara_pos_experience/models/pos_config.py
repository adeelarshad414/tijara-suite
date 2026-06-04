from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


SAAS_FEATURE_FIELDS = {
    "tijara_allow_b2b": ("b2b_sales", "B2B sales"),
    "tijara_queue_enabled": ("queue_system", "queue system"),
    "tijara_customer_display_enabled": ("customer_display", "customer display"),
    "tijara_customer_display_id": ("customer_display", "customer display"),
    "tijara_queue_display_id": ("queue_system", "queue display"),
    "tijara_menu_board_id": ("promotion_display", "menu board"),
    "tijara_deals_board_id": ("promotion_display", "deals board"),
    "tijara_kiosk_enabled": ("pos_experience", "kiosk"),
}


class PosConfig(models.Model):
    _inherit = "pos.config"

    tijara_allow_b2c = fields.Boolean(string="Allow B2C Sales", default=True)
    tijara_allow_b2b = fields.Boolean(string="Allow B2B Sales")
    tijara_default_audience = fields.Selection(
        [("b2c", "B2C"), ("b2b", "B2B")],
        string="Default Sale Type",
        default="b2c",
    )
    tijara_show_audience_toggle = fields.Boolean(
        string="Show B2B/B2C Toggle",
        default=True,
    )
    tijara_queue_enabled = fields.Boolean(string="Enable Queue System")
    tijara_kiosk_enabled = fields.Boolean(string="Enable Kiosk")
    tijara_customer_display_enabled = fields.Boolean(
        string="Enable POS Customer Display"
    )
    tijara_menu_board_id = fields.Many2one(
        "tijara.display.screen",
        string="Menu Board",
        domain=[("display_type", "=", "menu_board")],
    )
    tijara_deals_board_id = fields.Many2one(
        "tijara.display.screen",
        string="Deals Board",
        domain=[("display_type", "=", "deals_board")],
    )
    tijara_customer_display_id = fields.Many2one(
        "tijara.display.screen",
        string="Customer Display",
        domain=[("display_type", "=", "customer_display")],
    )
    tijara_queue_display_id = fields.Many2one(
        "tijara.display.screen",
        string="Queue Display",
        domain=[("display_type", "=", "queue_display")],
    )
    tijara_bill_discount_enabled = fields.Boolean(
        string="Enable Overall Bill Discount",
        default=True,
        help="Allow cashiers to apply one discount to the full bill.",
    )
    tijara_bill_discount_default_mode = fields.Selection(
        [("percent", "Percentage"), ("amount", "Amount")],
        string="Default Bill Discount Entry",
        default="percent",
    )
    tijara_bill_discount_max_percent = fields.Float(
        string="Max Bill Discount %",
        default=100.0,
    )
    tijara_bill_discount_requires_manager = fields.Boolean(
        string="Manager Approval for Bill Discount",
        help="Foundation flag for future POS approval enforcement.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_tijara_bill_discount_flags()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "tijara_bill_discount_enabled" in vals:
            self._sync_tijara_bill_discount_flags()
        return result

    @api.onchange("tijara_bill_discount_enabled")
    def _onchange_tijara_bill_discount_enabled(self):
        for config in self:
            config.module_pos_discount = config.tijara_bill_discount_enabled
            config.iface_discount = config.tijara_bill_discount_enabled

    @api.constrains(
        "tijara_allow_b2b",
        "tijara_default_audience",
        "tijara_queue_enabled",
        "tijara_kiosk_enabled",
        "tijara_customer_display_enabled",
        "tijara_menu_board_id",
        "tijara_deals_board_id",
        "tijara_customer_display_id",
        "tijara_queue_display_id",
    )
    def _check_tijara_saas_entitlements(self):
        for config in self:
            if config.tijara_default_audience == "b2b" and not config.tijara_allow_b2b:
                raise ValidationError(_("Default sale type cannot be B2B when B2B sales are disabled."))
            missing = config._tijara_missing_saas_features()
            if missing:
                raise ValidationError(
                    _(
                        "This POS configuration uses SaaS features not enabled for the tenant: %s."
                    )
                    % ", ".join(missing)
                )

    def _tijara_missing_saas_features(self):
        self.ensure_one()
        missing = []
        company = self.company_id or self.env.company
        for field_name, (feature_code, label) in SAAS_FEATURE_FIELDS.items():
            value = self[field_name]
            if value and not company.tijara_has_saas_feature(feature_code):
                missing.append("%s (%s)" % (label, feature_code))
        return missing

    def _sync_tijara_bill_discount_flags(self):
        discount_product = self.env.ref(
            "pos_discount.product_product_consumable",
            raise_if_not_found=False,
        )
        for config in self:
            values = {
                "module_pos_discount": bool(config.tijara_bill_discount_enabled),
                "iface_discount": bool(config.tijara_bill_discount_enabled),
            }
            if config.tijara_bill_discount_enabled:
                if discount_product and not config.discount_product_id:
                    values["discount_product_id"] = discount_product.id
            config.with_context(tijara_skip_discount_flag_sync=True).write(values)

    @api.model
    def _sync_all_tijara_bill_discount_flags(self):
        self.search([])._sync_tijara_bill_discount_flags()
