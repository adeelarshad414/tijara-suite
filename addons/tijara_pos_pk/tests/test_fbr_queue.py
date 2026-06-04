import json

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraFbrQueue(TransactionCase):
    def test_dry_run_submission_assigns_fbr_number_and_qr_payload(self):
        queue = self.env["tijara.fbr.invoice.queue"].create(
            {
                "invoice_ref": "POS-FBR-TEST-001",
                "payload": json.dumps({"invoice_ref": "POS-FBR-TEST-001", "total": 1200}),
                "adapter_mode": "dry_run",
                "company_id": self.env.company.id,
                "state": "queued",
            }
        )

        queue.action_submit_to_fbr_adapter()

        self.assertEqual(queue.state, "submitted")
        self.assertTrue(queue.fbr_invoice_number.startswith("DRY-FBR-"))
        self.assertIn(queue.fbr_invoice_number, queue.qr_payload)
        self.assertIn("accepted", queue.response)
        self.assertEqual(queue.compliance_status, "sandbox_passed")
        self.assertTrue(queue.signed_payload_hash)

    def test_live_submission_requires_endpoint_and_secret(self):
        queue = self.env["tijara.fbr.invoice.queue"].create(
            {
                "invoice_ref": "POS-FBR-LIVE-MISSING-ENDPOINT",
                "payload": json.dumps({"invoice_ref": "POS-FBR-LIVE-MISSING-ENDPOINT"}),
                "adapter_mode": "live",
                "company_id": self.env.company.id,
                "state": "queued",
            }
        )

        queue.action_submit_to_fbr_adapter()

        queue.invalidate_recordset(["state", "error_message"])
        self.assertEqual(queue.state, "failed")
        self.assertIn("endpoint", queue.error_message.lower())
        self.assertEqual(queue.compliance_status, "failed")
