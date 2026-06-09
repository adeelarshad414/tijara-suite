from odoo import Command, api, models


class TijaraEcommerceSeed(models.AbstractModel):
    _name = "tijara.ecommerce.seed"
    _description = "Tijara Ecommerce Demo Seed"

    @api.model
    def seed_demo(self, products=False):
        company = self.env.company
        channel = self._seed_channel(company)
        products = products or self.env["product.product"].sudo().search(
            [("default_code", "=like", "TIJARA-DEMO-%")]
        )
        self._publish_products(products)
        self._attach_promotions(channel, company)
        return True

    def _seed_channel(self, company):
        channel_model = self.env["tijara.ecommerce.channel"].sudo()
        website = self.env["website"].sudo().search(
            ["|", ("company_id", "=", company.id), ("company_id", "=", False)],
            limit=1,
        )
        warehouse = self.env["stock.warehouse"].sudo().search([("company_id", "=", company.id)], limit=1)
        values = {
            "name": "Tijara Demo Ecommerce Store",
            "code": "TIJARA-DEMO-WEB",
            "url_slug": "tijara-demo-web",
            "company_id": company.id,
            "website_id": website.id if website else False,
            "warehouse_id": warehouse.id if warehouse else False,
            "default_audience": "b2c",
            "allow_b2c": True,
            "allow_b2b": True,
            "allow_delivery": True,
            "allow_pickup": True,
            "allow_store_pickup": True,
            "allow_takeaway": True,
            "allow_cash": True,
            "allow_card": True,
            "allow_bank_transfer": True,
            "allow_cod": True,
            "allow_jazzcash": True,
            "allow_easypaisa": True,
            "auto_queue_pickup_delivery": True,
            "show_stock_qty": True,
            "low_stock_threshold": 10.0,
        }
        channel = channel_model.search([("code", "=", values["code"]), ("company_id", "=", company.id)], limit=1)
        if channel:
            channel.write(values)
            return channel
        return channel_model.create(values)

    def _publish_products(self, products):
        sequence = 10
        for product in products:
            template = product.product_tmpl_id
            values = {
                "tijara_ecommerce_published": True,
                "tijara_ecommerce_featured": sequence <= 50,
                "tijara_ecommerce_sequence": sequence,
                "tijara_ecommerce_short_description_en": "%s online catalog item" % (
                    (getattr(template, "tijara_vertical_tag", "") or "retail").replace("_", " ").title()
                ),
                "tijara_ecommerce_short_description_ur": getattr(template, "tijara_urdu_name", "") or "",
                "tijara_ecommerce_meta_keywords": "tijara ecommerce online %s %s"
                % (template.default_code or "", getattr(template, "tijara_vertical_tag", "") or ""),
            }
            if "is_published" in template._fields:
                values["is_published"] = True
            if "website_published" in template._fields:
                values["website_published"] = True
            template.write(values)
            sequence += 10

    def _attach_promotions(self, channel, company):
        promotions = self.env["tijara.promotion"].sudo().search(
            [("company_id", "=", company.id), ("active", "=", True)],
            limit=20,
        )
        if promotions:
            channel.write({"promotion_ids": [Command.set(promotions.ids)]})
