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
            if country and not company.country_id:
                values["country_id"] = country.id
            if company.currency_id != pkr and not self._company_has_posted_entries(company):
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
            self._set_company_default_sale_tax(company, tax)
            if "taxes_id" in product_model._fields:
                self._assign_gst_to_standard_products(company, tax)
        return True

    def _ensure_gst_sales_tax(self, company):
        tax_model = self.env["account.tax"].sudo().with_context(active_test=False)
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
        if "price_include_override" in tax_model._fields:
            values["price_include_override"] = "tax_excluded"
        elif "price_include" in tax_model._fields:
            values["price_include"] = False
        if "include_base_amount" in tax_model._fields:
            values["include_base_amount"] = False
        if tax:
            tax.write(values)
            return tax
        return tax_model.create(values)

    def _set_company_default_sale_tax(self, company, tax):
        if "account_sale_tax_id" in company._fields and company.account_sale_tax_id != tax:
            company.write({"account_sale_tax_id": tax.id})

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
