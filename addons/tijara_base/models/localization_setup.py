from odoo import Command, api, models


class TijaraLocalizationSetup(models.AbstractModel):
    _name = "tijara.localization.setup"
    _description = "Tijara Pakistan Localization Setup"

    @api.model
    def ensure_pakistan_defaults(self):
        pkr = self._ensure_pkr_currency()
        self._ensure_company_pakistan_defaults(pkr)
        self._ensure_pakistan_gst_defaults()
        return True

    @api.model
    def get_standard_sale_tax(self, company=None):
        if "account.tax" not in self.env.registry:
            return False
        company = company or self.env.company
        if not getattr(company, "tijara_gst_enabled", True):
            return False
        return self._ensure_gst_sales_tax(company)

    def _ensure_pkr_currency(self):
        currency_model = self.env["res.currency"].sudo().with_context(active_test=False)
        pkr = currency_model.search([("name", "=", "PKR")], limit=1)
        values = {
            "active": True,
            "symbol": "Rs.",
            "position": "before",
            "rounding": 0.01,
            "decimal_places": 2,
        }
        if pkr:
            pkr.write(values)
            return pkr
        values["name"] = "PKR"
        return currency_model.create(values)

    def _ensure_company_pakistan_defaults(self, pkr):
        country = self.env.ref("base.pk", raise_if_not_found=False)
        companies = self.env["res.company"].sudo().search([])
        for company in companies:
            values = {}
            has_posted_entries = self._company_has_posted_entries(company)
            if country and company.country_id != country and not has_posted_entries:
                values["country_id"] = country.id
            if company.currency_id != pkr and not has_posted_entries:
                values["currency_id"] = pkr.id
            if values:
                company.write(values)

    def _company_has_posted_entries(self, company):
        if "account.move" not in self.env.registry:
            return False
        return bool(
            self.env["account.move"]
            .sudo()
            .search([("company_id", "=", company.id), ("state", "=", "posted")], limit=1)
        )

    def _ensure_pakistan_gst_defaults(self):
        if "account.tax" not in self.env.registry:
            return False
        companies = self.env["res.company"].sudo().search([])
        product_model = self.env["product.template"].sudo()
        for company in companies:
            tax = self._ensure_gst_sales_tax(company)
            if not getattr(company, "tijara_gst_enabled", True):
                self._unset_company_default_sale_tax(company, tax)
                continue
            self._set_company_default_sale_tax(company, tax)
            if "taxes_id" in product_model._fields:
                self._assign_gst_to_standard_products(company, tax)
        return True

    def _ensure_gst_sales_tax(self, company):
        tax_model = self.env["account.tax"].sudo().with_context(active_test=False)
        country = company.country_id or self.env.ref("base.pk", raise_if_not_found=False)
        tax = tax_model.search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
                ("amount_type", "=", "percent"),
                ("amount", "=", 18.0),
                ("name", "=", "GST 18% Sales (PK)"),
            ],
            limit=1,
        )
        values = {
            "name": "GST 18% Sales (PK)",
            "amount": 18.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": company.id,
            "active": True,
        }
        if "country_id" in tax_model._fields and country:
            values["country_id"] = country.id
        if "tax_group_id" in tax_model._fields:
            values["tax_group_id"] = self._ensure_gst_tax_group(company, country=country).id
        if "price_include_override" in tax_model._fields:
            values["price_include_override"] = "tax_excluded"
        elif "price_include" in tax_model._fields:
            values["price_include"] = False
        if "include_base_amount" in tax_model._fields:
            values["include_base_amount"] = False
        if tax:
            changed_values = self._get_changed_tax_values(tax, values)
            if changed_values and not self._tax_used_by_pos_order(tax):
                tax.write(changed_values)
            return tax
        return tax_model.create(values)

    def _tax_used_by_pos_order(self, tax):
        if "pos.order.line" not in self.env.registry:
            return False
        return bool(
            self.env["pos.order.line"]
            .sudo()
            .search([("tax_ids", "in", tax.ids)], limit=1)
        )

    def _ensure_gst_tax_group(self, company, country=False):
        group_model = self.env["account.tax.group"].sudo()
        country = country or company.country_id or self.env.ref("base.pk", raise_if_not_found=False)
        domain = [("name", "=", "GST")]
        values = {"name": "GST"}
        if "country_id" in group_model._fields and country:
            domain.append(("country_id", "=", country.id))
            values["country_id"] = country.id
        if "company_id" in group_model._fields:
            domain.append(("company_id", "=", company.id))
            values["company_id"] = company.id
        if "sequence" in group_model._fields:
            values["sequence"] = 18
        if "pos_receipt_label" in group_model._fields:
            values["pos_receipt_label"] = "GST"
        group = group_model.search(domain, limit=1)
        if group:
            changed_values = self._get_changed_tax_values(group, values)
            if changed_values:
                group.write(changed_values)
            return group
        return group_model.create(values)

    def _get_changed_tax_values(self, tax, values):
        changed_values = {}
        for field_name, expected_value in values.items():
            current_value = tax[field_name]
            if tax._fields[field_name].type == "many2one":
                current_value = current_value.id or False
            if tax._fields[field_name].type in ("float", "monetary"):
                if abs((current_value or 0.0) - expected_value) > 0.000001:
                    changed_values[field_name] = expected_value
                continue
            if current_value != expected_value:
                changed_values[field_name] = expected_value
        return changed_values

    def _set_company_default_sale_tax(self, company, tax):
        if "account_sale_tax_id" in company._fields and company.account_sale_tax_id != tax:
            company.write({"account_sale_tax_id": tax.id})

    def _unset_company_default_sale_tax(self, company, tax):
        if "account_sale_tax_id" in company._fields and company.account_sale_tax_id == tax:
            company.write({"account_sale_tax_id": False})

    def _assign_gst_to_standard_products(self, company, tax):
        products = self.env["product.template"].sudo().search(
            [
                ("sale_ok", "=", True),
                ("tijara_tax_category", "=", "standard"),
            ]
        )
        for product in products:
            company_taxes = product.taxes_id.filtered(
                lambda record: not record.company_id or record.company_id == company
            )
            if not company_taxes:
                product.write({"taxes_id": [Command.link(tax.id)]})
