from odoo import Command, api, models


class TijaraEcommerceSeed(models.AbstractModel):
    _name = "tijara.ecommerce.seed"
    _description = "Tijara Ecommerce Demo Seed"

    @api.model
    def seed_demo(self, products=False):
        company = self.env.company
        channel = self._seed_channel(company)
        providers = self._seed_delivery_providers(company)
        default_provider = providers.filtered(lambda provider: provider.code == "TIJARA-INHOUSE")[:1] or providers[:1]
        channel.write(
            {
                "delivery_provider_ids": [Command.set(providers.ids)],
                "default_delivery_provider_id": default_provider.id,
            }
        )
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

    def _seed_delivery_providers(self, company):
        provider_model = self.env["tijara.ecommerce.delivery.provider"].sudo()
        base_values = {
            "company_id": company.id,
            "dry_run": True,
            "adapter_mode": "dry_run",
            "supports_delivery": True,
            "supports_courier": True,
            "supports_cod": True,
            "supports_cancel": True,
            "supports_labels": True,
            "supports_manifests": True,
            "supports_webhooks": True,
            "create_endpoint": "/shipments",
            "cancel_endpoint": "/shipments/{provider_reference}/cancel",
            "status_endpoint": "/shipments/{tracking_number}",
            "label_endpoint": "/shipments/{tracking_number}/label",
            "manifest_endpoint": "/manifests",
            "label_format": "pdf",
            "webhook_signature_mode": "dry_run",
            "webhook_signature_header": "X-Tijara-Delivery-Signature",
            "webhook_reference_field": "tracking_number",
            "webhook_status_field": "status",
            "webhook_eta_field": "eta",
            "contact_phone": "0300-0000000",
            "webhook_secret_ref": "secret://tijara/demo/ecommerce-delivery-webhook",
        }
        provider_specs = [
            {
                "name": "Tijara In-House Delivery",
                "code": "TIJARA-INHOUSE",
                "adapter_profile": "in_house_rider",
                "provider_type": "in_house",
                "service_level": "same_day",
                "auto_assign": True,
                "rider_name": "Demo Rider One",
                "rider_mobile": "0300-1111111",
                "tracking_url_template": "https://tracking.example.test/tijara/{tracking_number}",
                "notes": "Dry-run in-house rider profile for public repository demos and assumed certification evidence.",
            },
            {
                "name": "TCS Pakistan Sandbox",
                "code": "TIJARA-TCS",
                "adapter_profile": "tcs",
                "auto_assign": False,
                "contact_phone": "021-111-123456",
                "notes": "Assumed TCS Pakistan courier fixture. Replace endpoints, credentials, payload mapping, and certification evidence before production.",
            },
            {
                "name": "Leopards Courier Sandbox",
                "code": "TIJARA-LEOPARDS",
                "adapter_profile": "leopards",
                "auto_assign": False,
                "contact_phone": "021-111-300-786",
                "notes": "Assumed Leopards courier fixture for demo delivery reconciliation and SLA practice.",
            },
            {
                "name": "PostEx Sandbox",
                "code": "TIJARA-POSTEX",
                "adapter_profile": "postex",
                "auto_assign": False,
                "contact_phone": "042-111-767-839",
                "notes": "Assumed PostEx COD courier fixture for provider fee and settlement testing.",
            },
            {
                "name": "M&P Sandbox",
                "code": "TIJARA-MNP",
                "adapter_profile": "mnp",
                "auto_assign": False,
                "contact_phone": "021-111-202-202",
                "notes": "Assumed M&P courier fixture.",
            },
            {
                "name": "BlueEx Sandbox",
                "code": "TIJARA-BLUEEX",
                "adapter_profile": "blue_ex",
                "auto_assign": False,
                "notes": "Assumed BlueEx courier fixture.",
            },
            {
                "name": "Trax Sandbox",
                "code": "TIJARA-TRAX",
                "adapter_profile": "trax",
                "auto_assign": False,
                "notes": "Assumed Trax courier fixture.",
            },
            {
                "name": "Rider Sandbox",
                "code": "TIJARA-RIDER",
                "adapter_profile": "rider",
                "auto_assign": False,
                "notes": "Assumed Rider same-day delivery fixture.",
            },
            {
                "name": "Call Courier Sandbox",
                "code": "TIJARA-CALL-COURIER",
                "adapter_profile": "call_courier",
                "auto_assign": False,
                "notes": "Assumed Call Courier fixture.",
            },
        ]
        providers = provider_model.browse()
        for spec in provider_specs:
            values = dict(base_values, **spec)
            provider = provider_model.search([("code", "=", values["code"]), ("company_id", "=", company.id)], limit=1)
            if provider:
                provider.write(values)
            else:
                provider = provider_model.create(values)
            providers |= provider
        return providers

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
