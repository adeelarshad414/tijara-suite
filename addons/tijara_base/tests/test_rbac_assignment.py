from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTijaraRbacAssignment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.ali = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Ali Counter Operator",
                "login": "ali.rbac@example.test",
                "email": "ali.rbac@example.test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

    def test_tenant_admin_can_apply_multiple_business_roles_to_one_user(self):
        cashier = self.env.ref("tijara_base.business_role_cashier")
        inventory = self.env.ref("tijara_base.business_role_inventory_manager")
        assignment = self.env["tijara.user.role.assignment"].create(
            {
                "company_id": self.company.id,
                "user_id": self.ali.id,
                "role_ids": [(6, 0, [cashier.id, inventory.id])],
            }
        )

        assignment.action_apply_roles()

        self.assertEqual(assignment.state, "applied")
        self.assertIn(cashier, assignment.role_ids)
        self.assertIn(inventory, assignment.role_ids)
        self.assertIn(self.env.ref("base.group_user"), self.ali.group_ids)
        self.assertIn(self.env.ref("tijara_base.group_tijara_user"), self.ali.group_ids)

    def test_blocked_technical_group_cannot_be_granted_through_business_role(self):
        blocked = self.env["tijara.business.role"].create(
            {
                "name": "Blocked System Role",
                "code": "blocked_system_role",
                "category": "owner",
                "technical_group_xmlids": "base.group_system",
            }
        )
        assignment = self.env["tijara.user.role.assignment"].create(
            {
                "company_id": self.company.id,
                "user_id": self.ali.id,
                "role_ids": [(6, 0, [blocked.id])],
            }
        )

        with self.assertRaises(UserError):
            assignment.action_apply_roles()

        self.assertNotIn(self.env.ref("base.group_system"), self.ali.group_ids)
