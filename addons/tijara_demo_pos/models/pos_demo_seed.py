from odoo import Command, api, fields, models


class TijaraPosDemoSeed(models.AbstractModel):
    _name = "tijara.demo.pos.seed"
    _description = "Tijara POS Demo Seed"

    @api.model
    def seed_demo(self):
        company = self.env.company
        self._seed_company_policy(company)
        setup = self.env["tijara.localization.setup"].sudo()
        setup.ensure_pakistan_defaults()
        standard_sale_tax = setup.get_standard_sale_tax(company)
        category = self._ensure_pos_category("Tijara Demo")
        products = self._seed_products(category, standard_sale_tax)
        customers = self._seed_customers(company)
        screens = self._seed_display_surfaces(company)
        receipt_profiles = self._seed_receipt_invoice_templates(company)
        self._assign_inventory_label_profile(products, receipt_profiles.get("inventory_label"))
        self._seed_promotion(company, products)
        self._seed_display_content(company, screens, products)
        self.env["tijara.ecommerce.seed"].sudo().seed_demo(products)
        config = self._seed_pos_config(company, screens, receipt_profiles)
        self._seed_kiosk_profile_pos_sync(company, screens, config)
        self._seed_queue_ticket(company, customers["retail"])
        self._seed_backoffice_operations(company, customers)
        self._seed_stock(products)
        self._ensure_open_session(config)
        return True

    def _seed_company_policy(self, company):
        company.write(
            {
                "tijara_business_type": "superstore",
                "tijara_gst_enabled": True,
                "tijara_delivery_charge_enabled": True,
                "tijara_delivery_charge_amount": 150.0,
                "tijara_service_charge_enabled": True,
                "tijara_service_charge_percent": 7.5,
                "tijara_food_payment_tax_enabled": True,
                "tijara_food_card_tax_percent": 5.0,
                "tijara_food_cash_tax_percent": 16.0,
                "tijara_loyalty_enabled": True,
                "tijara_loyalty_points_per_currency": 0.01,
            }
        )

    def _ensure_pos_category(self, name):
        category = self.env["pos.category"].sudo().search([("name", "=", name)], limit=1)
        if category:
            return category
        return self.env["pos.category"].sudo().create({"name": name})

    def _seed_products(self, pos_category, standard_sale_tax=False):
        specs = [
            {
                "name": "Tijara Demo Daily Essentials Basket",
                "urdu": "ڈیلی ایسنشلز باسکٹ",
                "sku": "TIJARA-DEMO-ESSENTIALS",
                "barcode": "6200000000004",
                "price": 2450.0,
                "cost": 1980.0,
                "b2b": 2280.0,
                "stock": 42.0,
                "tax_category": "standard",
                "unit": "Bundle",
                "vertical": "superstore",
            },
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
                "vertical": "grocery",
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
                "vertical": "bakery",
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
                "vertical": "restaurant",
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
                "vertical": "cloth",
            },
            {
                "name": "Tijara Demo Matte Lipstick",
                "urdu": "میٹ لپ اسٹک",
                "sku": "TIJARA-DEMO-LIPSTICK",
                "barcode": "6200000000059",
                "price": 950.0,
                "cost": 610.0,
                "b2b": 825.0,
                "stock": 45.0,
                "tax_category": "standard",
                "unit": "Piece",
                "vertical": "cosmetics",
            },
            {
                "name": "Tijara Demo School Uniform Shirt",
                "urdu": "اسکول یونیفارم شرٹ",
                "sku": "TIJARA-DEMO-UNIFORM",
                "barcode": "6200000000066",
                "price": 1450.0,
                "cost": 930.0,
                "b2b": 1250.0,
                "stock": 60.0,
                "tax_category": "standard",
                "unit": "Piece",
                "vertical": "uniform",
            },
            {
                "name": "Tijara Demo Denim Jeans",
                "urdu": "ڈینم جینز",
                "sku": "TIJARA-DEMO-JEANS",
                "barcode": "6200000000073",
                "price": 3200.0,
                "cost": 2150.0,
                "b2b": 2850.0,
                "stock": 40.0,
                "tax_category": "standard",
                "unit": "Piece",
                "vertical": "garments",
            },
            {
                "name": "Tijara Demo Running Shoes",
                "urdu": "رننگ شوز",
                "sku": "TIJARA-DEMO-SHOES",
                "barcode": "6200000000080",
                "price": 5800.0,
                "cost": 3900.0,
                "b2b": 5200.0,
                "stock": 24.0,
                "tax_category": "standard",
                "unit": "Pair",
                "vertical": "shoes",
            },
            {
                "name": "Tijara Demo Paracetamol 500mg",
                "urdu": "پیراسیٹامول 500mg",
                "sku": "TIJARA-DEMO-PARACETAMOL",
                "barcode": "6200000000097",
                "price": 120.0,
                "cost": 82.0,
                "b2b": 105.0,
                "stock": 200.0,
                "tax_category": "standard",
                "unit": "Strip",
                "vertical": "pharmacy",
            },
            {
                "name": "Tijara Demo Zinger Burger",
                "urdu": "زنگر برگر",
                "sku": "TIJARA-DEMO-ZINGER",
                "barcode": "6200000000103",
                "price": 690.0,
                "cost": 410.0,
                "b2b": 650.0,
                "stock": 30.0,
                "tax_category": "standard",
                "unit": "Meal",
                "vertical": "fast_food",
            },
            {
                "name": "Tijara Demo Cappuccino",
                "urdu": "کپوچینو",
                "sku": "TIJARA-DEMO-CAPPUCCINO",
                "barcode": "6200000000110",
                "price": 520.0,
                "cost": 260.0,
                "b2b": 495.0,
                "stock": 50.0,
                "tax_category": "standard",
                "unit": "Cup",
                "vertical": "cafe",
            },
            {
                "name": "Tijara Demo Mobile Charger",
                "urdu": "موبائل چارجر",
                "sku": "TIJARA-DEMO-CHARGER",
                "barcode": "6200000000127",
                "price": 1850.0,
                "cost": 1220.0,
                "b2b": 1625.0,
                "stock": 55.0,
                "tax_category": "standard",
                "unit": "Piece",
                "vertical": "mobile_shop",
            },
            {
                "name": "Tijara Demo Smartphone",
                "urdu": "اسمارٹ فون",
                "sku": "TIJARA-DEMO-PHONE",
                "barcode": "6200000000141",
                "price": 68500.0,
                "cost": 61000.0,
                "b2b": 66000.0,
                "stock": 18.0,
                "tax_category": "standard",
                "unit": "Piece",
                "vertical": "mobile_shop",
            },
            {
                "name": "Tijara Demo LED Bulb 12W",
                "urdu": "ایل ای ڈی بلب 12W",
                "sku": "TIJARA-DEMO-LED",
                "barcode": "6200000000134",
                "price": 450.0,
                "cost": 280.0,
                "b2b": 390.0,
                "stock": 85.0,
                "tax_category": "standard",
                "unit": "Piece",
                "vertical": "electronics",
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
                "tijara_vertical_tag": spec["vertical"],
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
                "tijara_loyalty_opt_in": True,
                "tijara_loyalty_number": "LOY-WALKIN-001",
                "tijara_loyalty_tier": "standard",
                "tijara_loyalty_points": 125.0,
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
                "tijara_loyalty_opt_in": True,
                "tijara_loyalty_number": "LOY-B2B-001",
                "tijara_loyalty_tier": "gold",
                "tijara_loyalty_points": 2400.0,
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
            "allow_delivery": True,
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

    def _seed_receipt_invoice_templates(self, company):
        model = self.env["tijara.receipt.profile"].sudo()
        specs = [
            {
                "name": "Tijara Demo 80mm POS Receipt",
                "template_scope": "pos_receipt",
                "template_layout": "detailed",
                "language_mode": "both",
                "printer_width": "80",
                "receipt_title_english": "Tijara Sales Receipt",
                "receipt_title_urdu": "تجارہ سیلز رسید",
                "header_english": "Demo receipt for cashier, refund, exchange, GST, loyalty, and FBR readiness testing.",
                "header_urdu": "کیشئر، ری فنڈ، ایکسچینج، جی ایس ٹی، لائلٹی اور ایف بی آر ٹیسٹنگ کے لیے ڈیمو رسید۔",
                "footer_english": "Thank you for shopping with us.",
                "footer_urdu": "خریداری کا شکریہ۔",
                "terms_english": "Refunds and exchanges require the invoice barcode/QR and manager approval where configured.",
                "terms_urdu": "ری فنڈ اور ایکسچینج کے لیے انوائس بارکوڈ/کیو آر اور جہاں لازم ہو منیجر منظوری درکار ہے۔",
            },
            {
                "name": "Tijara Demo A4 Customer Invoice",
                "template_scope": "customer_invoice",
                "template_layout": "detailed",
                "language_mode": "both",
                "printer_width": "a4",
                "receipt_title_english": "Tijara Customer Invoice",
                "receipt_title_urdu": "تجارہ کسٹمر انوائس",
                "header_english": "A4 invoice template for B2B/B2C sales, customer details, GST, barcode, and QR testing.",
                "header_urdu": "بی ٹو بی/بی ٹو سی سیلز، کسٹمر تفصیل، جی ایس ٹی، بارکوڈ اور کیو آر ٹیسٹنگ کے لیے A4 انوائس۔",
                "footer_english": "This public-demo template is safe to customize per tenant.",
                "footer_urdu": "یہ پبلک ڈیمو ٹیمپلیٹ ہر ٹیننٹ کے لیے محفوظ طریقے سے تبدیل کیا جا سکتا ہے۔",
                "terms_english": "Payment, delivery, and return terms are configurable by tenant.",
                "terms_urdu": "ادائیگی، ڈیلیوری اور واپسی کی شرائط ہر ٹیننٹ کے مطابق سیٹ ہو سکتی ہیں۔",
            },
            {
                "name": "Tijara Demo Refund Exchange Slip",
                "template_scope": "refund_exchange",
                "template_layout": "standard",
                "language_mode": "both",
                "printer_width": "80",
                "receipt_title_english": "Refund / Exchange Slip",
                "receipt_title_urdu": "ری فنڈ / ایکسچینج سلپ",
                "header_english": "Refund and exchange evidence linked to invoice barcode scanning.",
                "header_urdu": "انوائس بارکوڈ اسکیننگ سے منسلک ری فنڈ اور ایکسچینج ثبوت۔",
                "footer_english": "Keep this slip with the original invoice.",
                "footer_urdu": "یہ سلپ اصل انوائس کے ساتھ رکھیں۔",
                "terms_english": "Returned items must follow tenant policy and approval controls.",
                "terms_urdu": "واپس کی گئی اشیا ٹیننٹ پالیسی اور منظوری کنٹرولز کے مطابق ہوں۔",
            },
            {
                "name": "Tijara Demo Quotation",
                "template_scope": "quotation",
                "template_layout": "standard",
                "language_mode": "both",
                "printer_width": "a4",
                "receipt_title_english": "Tijara Quotation",
                "receipt_title_urdu": "تجارہ کوٹیشن",
                "header_english": "Quotation template for B2B customers and wholesale pricing.",
                "header_urdu": "بی ٹو بی کسٹمرز اور ہول سیل قیمتوں کے لیے کوٹیشن ٹیمپلیٹ۔",
                "footer_english": "Prices and availability are subject to confirmation.",
                "footer_urdu": "قیمتیں اور دستیابی تصدیق سے مشروط ہیں۔",
                "terms_english": "Quotation validity and tax settings are tenant configurable.",
                "terms_urdu": "کوٹیشن مدت اور ٹیکس سیٹنگز ٹیننٹ کے مطابق قابل ترتیب ہیں۔",
            },
            {
                "name": "Tijara Demo Bilingual Inventory Label",
                "template_scope": "inventory_label",
                "template_layout": "compact",
                "language_mode": "both",
                "printer_width": "58",
                "receipt_title_english": "Inventory Label",
                "receipt_title_urdu": "انوینٹری لیبل",
                "header_english": "Bilingual product label for stock, shelf, barcode, and counter lookup.",
                "header_urdu": "اسٹاک، شیلف، بارکوڈ اور کاؤنٹر تلاش کے لیے دو زبانی پروڈکٹ لیبل۔",
                "footer_english": "Scan for inventory or POS lookup.",
                "footer_urdu": "انوینٹری یا POS تلاش کے لیے اسکین کریں۔",
                "terms_english": "Price, GST, and shelf placement follow tenant configuration.",
                "terms_urdu": "قیمت، جی ایس ٹی اور شیلف جگہ ٹیننٹ کنفیگریشن کے مطابق ہے۔",
            },
        ]
        profiles = {}
        for spec in specs:
            values = {
                **spec,
                "company_id": company.id,
                "active": True,
                "show_qr": True,
                "show_barcode": True,
                "show_customer": True,
                "show_cashier": True,
                "show_tax_breakdown": True,
                "show_discount_breakdown": True,
                "show_payment_summary": True,
                "show_company_ntn_strn": True,
                "show_return_policy": True,
                "barcode_source": "tijara_invoice_barcode",
                "internal_notes": "Seeded public-demo template for enterprise workflow QA.",
            }
            profile = model.search(
                [
                    ("company_id", "=", company.id),
                    ("template_scope", "=", spec["template_scope"]),
                    ("name", "=", spec["name"]),
                ],
                limit=1,
            )
            if profile:
                profile.write(values)
            else:
                profile = model.create(values)
            profiles[spec["template_scope"]] = profile
        return profiles

    def _assign_inventory_label_profile(self, products, profile):
        if not profile:
            return
        for product in products:
            product.product_tmpl_id.write({"tijara_inventory_label_profile_id": profile.id})

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

    def _seed_display_content(self, company, screens, products):
        model = self.env["tijara.display.content"].sudo()
        sequence = 10
        menu_screens = [
            screens["kiosk"].id,
            screens["menu_board"].id,
            screens["deals_board"].id,
        ]
        for product in products:
            tmpl = product.product_tmpl_id
            vertical = getattr(tmpl, "tijara_vertical_tag", "") or "superstore"
            content_type = "menu_item" if vertical in {"bakery", "cafe", "fast_food", "restaurant"} else "product"
            values = {
                "name": product.display_name,
                "sequence": sequence,
                "company_id": company.id,
                "content_type": content_type,
                "title_english": product.display_name,
                "title_urdu": getattr(tmpl, "tijara_urdu_name", "") or "",
                "subtitle_english": "%s workflow demo" % vertical.replace("_", " ").title(),
                "subtitle_urdu": "",
                "product_id": product.id,
                "b2c_price": getattr(tmpl, "tijara_b2c_price", 0.0) or product.lst_price,
                "b2b_price": getattr(tmpl, "tijara_b2b_price", 0.0) or product.lst_price,
                "screen_ids": [Command.set(menu_screens)],
            }
            content = model.search(
                [
                    ("company_id", "=", company.id),
                    ("product_id", "=", product.id),
                ],
                limit=1,
            )
            if content:
                content.write(values)
            else:
                model.create(values)
            sequence += 10

    def _seed_pos_config(self, company, screens, receipt_profiles=None):
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
        receipt_profile = (receipt_profiles or {}).get("pos_receipt")
        if receipt_profile and "tijara_receipt_profile_id" in model._fields:
            values["tijara_receipt_profile_id"] = receipt_profile.id

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

    def _seed_employee_partner(self, company, ref, name, role):
        partner_model = self.env["res.partner"].sudo()
        return self._ensure_partner(
            partner_model,
            {
                "name": name,
                "ref": ref,
                "company_id": company.id,
                "tijara_customer_type": "supplier",
                "comment": "Demo employee for %s payroll/back-office workflow." % role,
            },
        )

    def _seed_backoffice_operations(self, company, customers):
        vendor = self._ensure_partner(
            self.env["res.partner"].sudo(),
            {
                "name": "Tijara Demo Utility Vendor",
                "ref": "TIJARA-DEMO-UTILITY",
                "company_id": company.id,
                "tijara_customer_type": "supplier",
            },
        )
        expense_model = self.env["tijara.expense.request"].sudo()
        expenses = [
            {
                "receipt_reference": "EXP-DEMO-UTILITY",
                "category": "utilities",
                "partner_id": vendor.id,
                "amount": 18500.0,
                "tax_amount": 3330.0,
                "payment_method": "bank",
                "notes": "Demo electricity and utilities expense for back-office workflow.",
                "state": "paid",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
                "paid_at": fields.Datetime.now(),
            },
            {
                "receipt_reference": "EXP-DEMO-DELIVERY",
                "category": "delivery",
                "partner_id": customers["retail"].id,
                "amount": 2500.0,
                "tax_amount": 0.0,
                "payment_method": "cash",
                "notes": "Demo delivery rider settlement expense.",
                "state": "submitted",
            },
            {
                "receipt_reference": "EXP-DEMO-MAINTENANCE",
                "category": "maintenance",
                "partner_id": vendor.id,
                "amount": 7200.0,
                "tax_amount": 1296.0,
                "payment_method": "cash",
                "notes": "Approved demo maintenance expense awaiting payment.",
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            },
            {
                "receipt_reference": "EXP-DEMO-MARKETING",
                "category": "marketing",
                "partner_id": vendor.id,
                "amount": 12000.0,
                "tax_amount": 0.0,
                "payment_method": "mobile",
                "notes": "Draft demo promotion spend for submit/approve testing.",
                "state": "draft",
            },
        ]
        for values in expenses:
            values.update({"company_id": company.id})
            expense = expense_model.search(
                [("receipt_reference", "=", values["receipt_reference"])],
                limit=1,
            )
            if expense:
                expense.write(values)
            else:
                expense_model.create(values)

        employees = [
            self._seed_employee_partner(company, "EMP-DEMO-CASHIER", "Tijara Demo Cashier", "cashier"),
            self._seed_employee_partner(company, "EMP-DEMO-CHEF", "Tijara Demo Chef", "chef"),
            self._seed_employee_partner(company, "EMP-DEMO-STOCK", "Tijara Demo Stock Officer", "inventory"),
        ]
        batch_model = self.env["tijara.salary.batch"].sudo()
        batch = batch_model.search([("name", "=", "Tijara Demo Salary Batch")], limit=1)
        values = {
            "name": "Tijara Demo Salary Batch",
            "company_id": company.id,
            "period_start": fields.Date.today().replace(day=1),
            "period_end": fields.Date.today(),
            "state": "approved",
            "line_ids": [
                Command.create(
                    {
                        "employee_id": employees[0].id,
                        "role": "Cashier",
                        "gross_amount": 65000.0,
                        "deduction_amount": 1500.0,
                        "bonus_amount": 2500.0,
                    }
                ),
                Command.create(
                    {
                        "employee_id": employees[1].id,
                        "role": "Chef / Kitchen",
                        "gross_amount": 85000.0,
                        "deduction_amount": 0.0,
                        "bonus_amount": 5000.0,
                    }
                ),
                Command.create(
                    {
                        "employee_id": employees[2].id,
                        "role": "Inventory",
                        "gross_amount": 70000.0,
                        "deduction_amount": 1000.0,
                        "bonus_amount": 1500.0,
                    }
                ),
            ],
        }
        if batch:
            batch.line_ids.unlink()
            batch.write(values)
        else:
            batch_model.create(values)

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
            "TIJARA-DEMO-ESSENTIALS": 42.0,
            "TIJARA-DEMO-RICE": 75.0,
            "TIJARA-DEMO-BREAD": 35.0,
            "TIJARA-DEMO-KARAHI": 20.0,
            "TIJARA-DEMO-FABRIC": 120.0,
            "TIJARA-DEMO-LIPSTICK": 45.0,
            "TIJARA-DEMO-UNIFORM": 60.0,
            "TIJARA-DEMO-JEANS": 40.0,
            "TIJARA-DEMO-SHOES": 24.0,
            "TIJARA-DEMO-PARACETAMOL": 200.0,
            "TIJARA-DEMO-ZINGER": 30.0,
            "TIJARA-DEMO-CAPPUCCINO": 50.0,
            "TIJARA-DEMO-CHARGER": 55.0,
            "TIJARA-DEMO-PHONE": 18.0,
            "TIJARA-DEMO-LED": 85.0,
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
