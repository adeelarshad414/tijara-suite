from urllib.parse import quote

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tijara_inventory_label_profile_id = fields.Many2one(
        "tijara.receipt.profile",
        string="Inventory Label Template",
        domain="[('template_scope', '=', 'inventory_label'), ('active', '=', True)]",
        help="Optional English, Urdu, or bilingual label template for product and inventory printing.",
    )

    def action_tijara_print_inventory_label(self):
        return self.env.ref("tijara_pos_pk.action_report_tijara_inventory_label").report_action(self)

    def tijara_get_inventory_label_profile(self):
        self.ensure_one()
        if self.tijara_inventory_label_profile_id:
            return self.tijara_inventory_label_profile_id
        return self.env["tijara.receipt.profile"].sudo().search(
            [
                ("company_id", "=", self.env.company.id),
                ("template_scope", "=", "inventory_label"),
                ("active", "=", True),
            ],
            limit=1,
        )

    def tijara_inventory_label_english_name(self):
        self.ensure_one()
        return self.tijara_label_name or self.display_name or self.name or ""

    def tijara_inventory_label_urdu_name(self):
        self.ensure_one()
        return self.tijara_urdu_name or ""

    def tijara_tax_category_label(self):
        self.ensure_one()
        selection = dict(self._fields["tijara_tax_category"].selection)
        return selection.get(self.tijara_tax_category, self.tijara_tax_category or "")

    def tijara_inventory_barcode_value(self, profile=False):
        self.ensure_one()
        profile = profile or self.tijara_get_inventory_label_profile()
        if profile and profile.barcode_source == "custom":
            return profile.custom_barcode_value or ""
        if profile and profile.barcode_source == "order_name":
            return self.default_code or self.display_name or str(self.id)
        return self.barcode or self.tijara_barcode_alias or self.default_code or str(self.id)

    def tijara_inventory_barcode_url(self, profile=False, barcode_type="Code128", width=480, height=100):
        value = self.tijara_inventory_barcode_value(profile)
        if not value:
            return False
        return f"/report/barcode/{barcode_type}/{quote(str(value))}?width={width}&height={height}"
