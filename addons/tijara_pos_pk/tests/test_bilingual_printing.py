from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraBilingualPrinting(TransactionCase):
    def test_receipt_profile_language_modes_gate_print_text(self):
        profile_model = self.env["tijara.receipt.profile"]
        english = profile_model.create(
            {
                "name": "English Print Profile",
                "template_scope": "customer_invoice",
                "language_mode": "en",
                "company_id": self.env.company.id,
            }
        )
        urdu = profile_model.create(
            {
                "name": "Urdu Print Profile",
                "template_scope": "customer_invoice",
                "language_mode": "ur",
                "company_id": self.env.company.id,
            }
        )
        both = profile_model.create(
            {
                "name": "Bilingual Print Profile",
                "template_scope": "customer_invoice",
                "language_mode": "both",
                "company_id": self.env.company.id,
            }
        )

        self.assertTrue(english.tijara_show_english())
        self.assertFalse(english.tijara_show_urdu())
        self.assertFalse(urdu.tijara_show_english())
        self.assertTrue(urdu.tijara_show_urdu())
        self.assertEqual(both.tijara_bilingual_label("Invoice", "انوائس"), "Invoice / انوائس")

    def test_inventory_label_profile_supports_urdu_and_barcode(self):
        profile = self.env["tijara.receipt.profile"].create(
            {
                "name": "Bilingual Inventory Label Test",
                "template_scope": "inventory_label",
                "language_mode": "both",
                "printer_width": "58",
                "show_barcode": True,
                "show_qr": True,
                "company_id": self.env.company.id,
            }
        )
        product = self.env["product.template"].create(
            {
                "name": "Test Rice 5kg",
                "default_code": "TEST-RICE-5KG",
                "barcode": "6201111111111",
                "tijara_urdu_name": "چاول 5 کلو",
                "tijara_label_name": "Rice 5kg Label",
                "list_price": 2500.0,
                "tijara_inventory_label_profile_id": profile.id,
            }
        )

        self.assertEqual(product.tijara_get_inventory_label_profile(), profile)
        self.assertEqual(product.tijara_inventory_label_english_name(), "Rice 5kg Label")
        self.assertEqual(product.tijara_inventory_label_urdu_name(), "چاول 5 کلو")
        self.assertEqual(product.tijara_inventory_barcode_value(profile), "6201111111111")
        self.assertIn("6201111111111", product.tijara_inventory_barcode_url(profile))

        report = self.env.ref("tijara_pos_pk.action_report_tijara_inventory_label")
        try:
            html, _content_type = report._render_qweb_html([product.id])
        except TypeError:
            html, _content_type = self.env["ir.actions.report"]._render_qweb_html(
                report.report_name,
                [product.id],
            )
        html_text = html.decode("utf-8") if isinstance(html, bytes) else html
        self.assertIn("Rice 5kg Label", html_text)
        self.assertIn("چاول 5 کلو", html_text)
