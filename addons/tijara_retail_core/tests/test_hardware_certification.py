from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraHardwareCertification(TransactionCase):
    def test_execution_checks_gate_physical_certification(self):
        device = self.env["tijara.hardware.device"].create(
            {
                "name": "Test Receipt Printer",
                "code": "TEST-PRINTER-001",
                "company_id": self.env.company.id,
                "device_type": "receipt_printer",
                "connection_type": "browser_bridge",
                "integration_role": "receipt_output",
                "printer_language": "escpos",
                "bridge_endpoint": "http://127.0.0.1:9199",
            }
        )
        certification = self.env["tijara.hardware.certification"].create(
            {
                "device_id": device.id,
                "profile_name": "Receipt Printer Pilot Profile",
                "certification_type": "physical",
            }
        )

        certification.action_prepare_execution_checks()

        self.assertEqual(certification.check_count, 1)
        check = certification.check_ids
        self.assertEqual(check.operation, "print_receipt")

        with self.assertRaises(UserError):
            certification.action_mark_passed()

        check.write({"observed_result": "Manual staging evidence accepted."})
        check.action_mark_passed_manual()
        certification.receipt_print_ok = True
        certification.physical_signature = "QA Operator"
        certification.action_mark_passed()

        self.assertEqual(certification.result, "passed")
        self.assertEqual(certification.passed_check_count, 1)
        self.assertTrue(check.evidence_hash)
        self.assertTrue(certification.evidence_hash)
