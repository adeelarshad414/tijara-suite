from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraEcommerceFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "tijara_business_type": "cafe",
                "tijara_gst_enabled": True,
                "tijara_service_charge_enabled": True,
                "tijara_service_charge_percent": 10.0,
                "tijara_delivery_charge_enabled": True,
                "tijara_delivery_charge_amount": 150.0,
                "tijara_food_payment_tax_enabled": True,
                "tijara_food_card_tax_percent": 5.0,
                "tijara_food_cash_tax_percent": 16.0,
                "tijara_loyalty_enabled": True,
                "tijara_loyalty_points_per_currency": 0.01,
            }
        )
        cls.env["tijara.localization.setup"].sudo().ensure_pakistan_defaults()
        cls.tax = cls.env["tijara.localization.setup"].sudo().get_standard_sale_tax(cls.company)
        product_values = {
            "name": "Tijara Ecommerce Test Product",
            "default_code": "TIJARA-ECOM-TEST",
            "barcode": "6299000000001",
            "type": "consu",
            "is_storable": True,
            "sale_ok": True,
            "purchase_ok": True,
            "list_price": 100.0,
            "standard_price": 70.0,
            "tijara_urdu_name": "ای کامرس ٹیسٹ پروڈکٹ",
            "tijara_tax_category": "standard",
            "tijara_vertical_tag": "grocery",
            "tijara_b2c_price": 120.0,
            "tijara_b2b_price": 95.0,
            "tijara_ecommerce_published": True,
            "tijara_ecommerce_featured": True,
        }
        if cls.tax:
            product_values["taxes_id"] = [Command.set([cls.tax.id])]
        cls.product_template = cls.env["product.template"].sudo().create(product_values)
        cls.product = cls.product_template.product_variant_id
        cls.channel = cls.env["tijara.ecommerce.channel"].sudo().create(
            {
                "name": "Tijara Test Web Store",
                "code": "TIJARA-TEST-WEB",
                "url_slug": "tijara-test-web",
                "company_id": cls.company.id,
                "default_audience": "b2c",
                "allow_b2c": True,
                "allow_b2b": True,
                "allow_delivery": True,
                "allow_pickup": True,
                "allow_store_pickup": True,
                "allow_cash": True,
                "allow_card": True,
                "allow_cod": True,
                "auto_queue_pickup_delivery": True,
            }
        )

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("tijara.saas.enforcement_enabled", "0")

    def test_catalog_returns_b2b_b2c_prices_and_urdu_product_name(self):
        payload = self.channel.tijara_catalog_payload(audience="b2b")
        product = next(row for row in payload["products"] if row["product_id"] == self.product.id)
        self.assertEqual(product["price"], 95.0)
        self.assertEqual(product["b2c_price"], 120.0)
        self.assertEqual(product["b2b_price"], 95.0)
        self.assertEqual(product["name_urdu"], "ای کامرس ٹیسٹ پروڈکٹ")
        self.assertIn("delivery", payload["fulfillment"]["methods"])
        self.assertIn("card", payload["payment"]["methods"])

    def test_checkout_creates_sale_order_with_charges_queue_and_loyalty(self):
        order = self.channel.tijara_create_order(
            {
                "audience": "b2b",
                "fulfillment_method": "delivery",
                "payment_method": "card",
                "customer": {
                    "name": "Online Wholesale Customer",
                    "mobile": "03001234567",
                    "email": "online-wholesale@example.com",
                    "delivery_address": "Test delivery address",
                    "loyalty_opt_in": True,
                },
                "lines": [{"product_id": self.product.id, "quantity": 2}],
            }
        )
        product_line = order.order_line.filtered(lambda line: line.product_id == self.product)
        self.assertEqual(order.tijara_ecommerce_channel_id, self.channel)
        self.assertEqual(order.tijara_ecommerce_audience, "b2b")
        self.assertEqual(product_line.price_unit, 95.0)
        self.assertAlmostEqual(order.tijara_amount_service_charge, 19.0)
        self.assertAlmostEqual(order.tijara_amount_delivery_charge, 150.0)
        self.assertAlmostEqual(order.tijara_amount_payment_tax, 17.95)
        self.assertTrue(order.tijara_pickup_code)
        self.assertTrue(order.tijara_queue_ticket_id)
        self.assertEqual(order.tijara_queue_ticket_id.source, "ecommerce")
        order.action_tijara_mark_ecommerce_paid()
        self.assertEqual(order.tijara_payment_status, "paid")
        self.assertGreater(order.partner_id.tijara_loyalty_points, 0)

    def test_saas_enforcement_blocks_without_ecommerce_feature(self):
        self.env["ir.config_parameter"].sudo().set_param("tijara.saas.enforcement_enabled", "1")
        self.env["tijara.saas.subscription"].sudo().search([("company_id", "=", self.company.id)]).unlink()
        with self.assertRaises(UserError):
            self.channel.tijara_catalog_payload(audience="b2c")
        self.env["tijara.saas.subscription"].sudo().create(
            {
                "name": "Tijara Ecommerce Test Subscription",
                "tenant_name": self.company.name,
                "database_name": "tijara_test_ecommerce",
                "company_id": self.company.id,
                "customer_id": self.env["res.partner"].create({"name": "Tijara Ecommerce Billing"}).id,
                "plan_id": self.env.ref("tijara_saas_control.plan_enterprise").id,
                "state": "active",
                "start_date": fields.Date.context_today(self.env.user),
            }
        )
        payload = self.channel.tijara_catalog_payload(audience="b2c")
        self.assertEqual(payload["status"], "ok")
