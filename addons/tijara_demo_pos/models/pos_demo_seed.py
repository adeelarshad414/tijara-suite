from odoo import Command, api, fields, models


class TijaraPosDemoSeed(models.AbstractModel):
    _name = "tijara.demo.pos.seed"
    _description = "Tijara POS Demo Seed"

    @api.model
    def seed_demo(self):
        company = self.env.company
        setup = self.env["tijara.localization.setup"].sudo()
        setup.ensure_pakistan_defaults()
        standard_sale_tax = setup.get_standard_sale_tax(company)
        category = self._ensure_pos_category("Tijara Demo")
        products = self._seed_products(category, standard_sale_tax)
        customers = self._seed_customers(company)
        screens = self._seed_display_surfaces(company)
        self._seed_promotion(company, products)
        config = self._seed_pos_config(company, screens)
        self._seed_kiosk_profile_pos_sync(company, screens, config)
        self._seed_queue_ticket(company, customers["retail"])
        self._seed_stock(products)
        self._ensure_open_session(config)
        return True

    def _ensure_pos_category(self, name):
        category = self.env["pos.category"].sudo().search([("name", "=", name)], limit=1)
        if category:
            return category
        return self.env["pos.category"].sudo().create({"name": name})

    def _seed_products(self, pos_category, standard_sale_tax=False):
        specs = [
            {
                "name": "Tijara Demo Basmati Rice 5kg",
                "urdu": "باسمتی چاول 5 کلو",
                "sku": "TIJARA-DEMO-RICE",
                "barcode": "6200000000011",
                "price": 3250.0,
                "cost": 2825.0,
                "b2b": 3050.0,
                "stock": 75.0,
                "tax_category": "standard",
                "unit": "Bag",
            },
            {
                "name": "Tijara Demo Fresh Bread",
                "urdu": "تازہ ڈبل روٹی",
                "sku": "TIJARA-DEMO-BREAD",
                "barcode": "6200000000028",
                "price": 220.0,
                "cost": 145.0,
                "b2b": 195.0,
                "stock": 35.0,
                "tax_category": "standard",
                "unit": "Piece",
            },
            {
                "name": "Tijara Demo Chicken Karahi",
                "urdu": "چکن کڑاہی",
                "sku": "TIJARA-DEMO-KARAHI",
                "barcode": "6200000000035",
                "price": 1450.0,
                "cost": 980.0,
                "b2b": 1325.0,
                "stock": 20.0,
                "tax_category": "standard",
                "unit": "Serving",
            },
            {
                "name": "Tijara Demo Cotton Fabric",
                "urdu": "کاٹن کپڑا",
                "sku": "TIJARA-DEMO-FABRIC",
                "barcode": "6200000000042",
                "price": 650.0,
                "cost": 430.0,
                "b2b": 575.0,
                "stock": 120.0,
                "tax_category": "standard",
                "unit": "Meter",
            },
        ]

        products = self.env["product.product"].sudo()
        for spec in specs:
            template = self.env["product.template"].sudo().search(
                [("default_code", "=", spec["sku"])],
                limit=1,
            )
            values = {
                "name": spec["name"],
                "default_code": spec["sku"],
                "barcode": spec["barcode"],
                "list_price": spec["price"],
                "standard_price": spec["cost"],
                "type": "consu",
                "is_storable": True,
                "sale_ok": True,
                "purchase_ok": True,
                "available_in_pos": True,
                "pos_categ_ids": [Command.link(pos_category.id)],
                "supplier_taxes_id": [Command.clear()],
                "tijara_urdu_name": spec["urdu"],
                "tijara_local_sku": spec["sku"],
                "tijara_barcode_alias": spec["barcode"],
                "tijara_tax_category": spec["tax_category"],
                "tijara_retail_unit": spec["unit"],
                "tijara_quick_sale": True,
                "tijara_min_stock_alert": 10.0,
                "tijara_reorder_multiple": 5.0,
                "tijara_b2c_price": spec["price"],
                "tijara_b2b_price": spec["b2b"],
                "tijara_b2b_min_qty": 5.0,
                "tijara_allow_refund": True,
                "tijara_allow_exchange": True,
            }
            if spec["tax_category"] == "standard" and standard_sale_tax:
                values["taxes_id"] = [Command.set([standard_sale_tax.id])]
            if template:
                template.write(values)
            else:
                template = self.env["product.template"].sudo().create(values)
            products |= template.product_variant_id
        return products

    def _seed_customers(self, company):
        partner_model = self.env["res.partner"].sudo()
        retail = self._ensure_partner(
            partner_model,
            {
                "name": "Tijara Demo Walk-in Customer",
                "ref": "TIJARA-DEMO-B2C",
                "company_id": company.id,
                "tijara_urdu_name": "عام گاہک",
                "tijara_customer_type": "walk_in",
                "tijara_is_walk_in": True,
            },
        )
        wholesale = self._ensure_partner(
            partner_model,
            {
                "name": "Tijara Demo Wholesale Customer",
                "ref": "TIJARA-DEMO-B2B",
                "company_id": company.id,
                "tijara_urdu_name": "ہول سیل گاہک",
                "tijara_customer_type": "wholesale",
                "tijara_ntn": "1234567",
                "tijara_credit_limit": 250000.0,
            },
        )
        return {"retail": retail, "wholesale": wholesale}

    def _ensure_partner(self, model, values):
        partner = model.search([("ref", "=", values["ref"])], limit=1)
        if partner:
            partner.write(values)
            return partner
        return model.create(values)

    def _seed_display_surfaces(self, company):
        screen_model = self.env["tijara.display.screen"].sudo()
        screens = {}
        for display_type, label in [
            ("customer_display", "Customer Display"),
            ("queue_display", "Queue Display"),
            ("menu_board", "Menu Board"),
            ("deals_board", "Deals Board"),
            ("kiosk", "Kiosk"),
        ]:
            code = f"TIJARA-DEMO-{display_type.upper()}"
            values = {
                "name": f"Tijara Demo {label}",
                "code": code,
                "company_id": company.id,
                "display_type": display_type,
                "language_mode": "both",
                "price_mode": "both",
                "url_slug": code.lower().replace("_", "-"),
            }
            screen = screen_model.search([("code", "=", code)], limit=1)
            if screen:
                screen.write(values)
            else:
                screen = screen_model.create(values)
            screens[display_type] = screen

        kiosk_model = self.env["tijara.kiosk.profile"].sudo()
        kiosk_values = {
            "name": "Tijara Demo Kiosk Profile",
            "company_id": company.id,
            "screen_id": screens["kiosk"].id,
            "default_order_type": "takeaway",
            "allow_dine_in": True,
            "allow_takeaway": True,
            "allow_pickup": True,
            "allow_b2c": True,
            "allow_b2b": True,
            "allow_cash": True,
            "allow_card": True,
        }
        kiosk = kiosk_model.search([("name", "=", kiosk_values["name"])], limit=1)
        if kiosk:
            kiosk.write(kiosk_values)
        else:
            kiosk_model.create(kiosk_values)

        return screens

    def _seed_promotion(self, company, products):
        model = self.env["tijara.promotion"].sudo()
        values = {
            "name": "Tijara Demo Weekend Deal",
            "code": "TIJARA-DEMO-WEEKEND",
            "company_id": company.id,
            "promotion_type": "discount",
            "applies_to": "both",
            "discount_percent": 5.0,
            "start_at": fields.Datetime.now(),
            "product_ids": [Command.set(products.ids)],
            "title_english": "Weekend Deal",
            "title_urdu": "ویک اینڈ ڈیل",
            "display_description": "Demo promotion for POS, kiosk, and display testing.",
            "show_on_kiosk": True,
            "show_on_menu_board": True,
            "show_on_deals_board": True,
            "show_on_customer_display": True,
        }
        promotion = model.search([("code", "=", values["code"])], limit=1)
        if promotion:
            promotion.write(values)
        else:
            model.create(values)

    def _seed_pos_config(self, company, screens):
        model = self.env["pos.config"].sudo()
        discount_product = self.env.ref(
            "pos_discount.product_product_consumable",
            raise_if_not_found=False,
        )
        values = {
            "name": "Tijara Demo POS",
            "company_id": company.id,
            "tijara_allow_b2c": True,
            "tijara_allow_b2b": True,
            "tijara_default_audience": "b2c",
            "tijara_show_audience_toggle": True,
            "tijara_queue_enabled": True,
            "tijara_kiosk_enabled": True,
            "tijara_customer_display_enabled": True,
            "tijara_menu_board_id": screens["menu_board"].id,
            "tijara_deals_board_id": screens["deals_board"].id,
            "tijara_customer_display_id": screens["customer_display"].id,
            "tijara_queue_display_id": screens["queue_display"].id,
            "tijara_bill_discount_enabled": True,
            "tijara_bill_discount_default_mode": "percent",
            "tijara_bill_discount_max_percent": 25.0,
            "tijara_bill_discount_requires_manager": True,
            "module_pos_discount": True,
            "iface_discount": True,
        }
        if discount_product:
            values["discount_product_id"] = discount_product.id

        config = model.search([("name", "=", values["name"])], limit=1)
        if config:
            config.write(values)
        else:
            config = model.create(values)
        return config

    def _seed_kiosk_profile_pos_sync(self, company, screens, config):
        payment_method = config.payment_method_ids[:1]
        values = {
            "auto_create_pos_order": True,
            "pos_config_id": config.id,
            "payment_capture_mode": "pay_at_counter",
            "cash_payment_method_id": payment_method.id if payment_method else False,
            "card_payment_method_id": payment_method.id if payment_method else False,
        }
        kiosk = self.env["tijara.kiosk.profile"].sudo().search(
            [
                ("company_id", "=", company.id),
                ("screen_id", "=", screens["kiosk"].id),
            ],
            limit=1,
        )
        if kiosk:
            kiosk.write(values)

    def _seed_queue_ticket(self, company, customer):
        model = self.env["tijara.queue.ticket"].sudo()
        values = {
            "name": "New",
            "source": "kiosk",
            "order_type": "pickup",
            "audience": "b2c",
            "customer_id": customer.id,
            "pickup_code": "PK-100",
            "company_id": company.id,
            "state": "waiting",
            "notes": "Demo queue ticket for display testing.",
        }
        ticket = model.search([("pickup_code", "=", values["pickup_code"])], limit=1)
        if ticket:
            ticket.write(values)
        else:
            ticket = model.create(values)
        ticket.action_assign_number()

    def _seed_stock(self, products):
        warehouse = self.env["stock.warehouse"].sudo().search(
            [("company_id", "=", self.env.company.id)],
            limit=1,
        )
        location = warehouse.lot_stock_id
        if not location:
            return
        quant_model = self.env["stock.quant"].sudo()
        target_qty = {
            "TIJARA-DEMO-RICE": 75.0,
            "TIJARA-DEMO-BREAD": 35.0,
            "TIJARA-DEMO-KARAHI": 20.0,
            "TIJARA-DEMO-FABRIC": 120.0,
        }
        for product in products:
            target = target_qty.get(product.default_code)
            if target is None:
                continue
            current = quant_model._get_available_quantity(product, location)
            delta = target - current
            if delta:
                quant_model._update_available_quantity(product, location, delta)

    def _ensure_open_session(self, config):
        session_model = self.env["pos.session"].sudo()
        open_session = session_model.search(
            [
                ("config_id", "=", config.id),
                ("state", "not in", ["closed", "closing_control"]),
            ],
            limit=1,
        )
        if not open_session:
            session_model.create({"config_id": config.id})
