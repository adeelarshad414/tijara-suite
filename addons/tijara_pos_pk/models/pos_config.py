from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    tijara_receipt_profile_id = fields.Many2one(
        "tijara.receipt.profile",
        string="Tijara Receipt Template",
        domain="[('template_scope', '=', 'pos_receipt'), ('active', '=', True)]",
        help="Template used by Tijara POS receipt reports.",
    )
    tijara_receipt_printer_device_id = fields.Many2one(
        "tijara.hardware.device",
        string="Tijara Bridge Receipt Printer",
        domain=[
            ("device_type", "=", "receipt_printer"),
            ("connection_type", "=", "browser_bridge"),
            ("active", "=", True),
        ],
        help="Local hardware bridge receipt printer used by the browser POS print button.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        field_names = super()._load_pos_data_fields(config)
        odoo19_core_fields = [
            "id",
            "name",
            "display_name",
            "company_id",
            "currency_id",
            "journal_id",
            "invoice_journal_id",
            "picking_type_id",
            "stock_location_id",
            "payment_method_ids",
            "fast_payment_method_ids",
            "use_fast_payment",
            "cash_control",
            "cash_journal_id",
            "cash_rounding",
            "rounding_method",
            "only_round_cash_method",
            "use_pricelist",
            "pricelist_id",
            "available_pricelist_ids",
            "default_fiscal_position_id",
            "fiscal_position_ids",
            "tax_regime_selection",
            "manual_discount",
            "restrict_price_control",
            "module_pos_discount",
            "iface_discount",
            "discount_pc",
            "discount_product_id",
            "iface_tax_included",
            "iface_cashdrawer",
            "iface_print_auto",
            "iface_print_skip_screen",
            "iface_print_via_proxy",
            "iface_scan_via_proxy",
            "iface_electronic_scale",
            "iface_big_scrollbars",
            "iface_available_categ_ids",
            "iface_start_categ_id",
            "iface_group_by_categ",
            "limit_categories",
            "show_product_images",
            "show_category_images",
            "basic_receipt",
            "receipt_header",
            "receipt_footer",
            "printer_ids",
            "proxy_ip",
            "other_devices",
            "epson_printer_ip",
            "module_pos_restaurant",
            "module_pos_hr",
            "floor_ids",
            "default_screen",
            "iface_splitbill",
            "iface_printbill",
            "iface_tipproduct",
            "tip_product_id",
            "set_tip_after_payment",
            "use_presets",
            "default_preset_id",
            "trusted_config_ids",
            "ship_later",
            "auto_validate_terminal_payment",
            "access_token",
        ]
        tijara_fields = ["tijara_receipt_profile_id", "tijara_receipt_printer_device_id"]
        requested_fields = field_names + odoo19_core_fields + tijara_fields
        fields_to_load = []
        for field in requested_fields:
            if field in self._fields and field not in fields_to_load:
                fields_to_load.append(field)
        return fields_to_load
