from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class TijaraBusinessRole(models.Model):
    _name = "tijara.business.role"
    _description = "Tijara Business Role"
    _order = "sequence, name"

    _ALLOWED_TENANT_GROUP_XMLIDS = {
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "point_of_sale.group_pos_user",
        "point_of_sale.group_pos_manager",
        "stock.group_stock_user",
        "stock.group_stock_manager",
        "sales_team.group_sale_salesman",
        "sales_team.group_sale_manager",
        "purchase.group_purchase_user",
        "purchase.group_purchase_manager",
        "account.group_account_readonly",
        "account.group_account_invoice",
        "account.group_account_user",
        "account.group_account_manager",
        "hr_expense.group_hr_expense_user",
        "hr_expense.group_hr_expense_team_approver",
        "website.group_website_designer",
        "website.group_website_restricted_editor",
    }
    _PROTECTED_COMMON_GROUP_XMLIDS = {
        "base.group_user",
        "tijara_base.group_tijara_user",
    }

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Selection(
        [
            ("owner", "Owner / Admin"),
            ("pos", "POS"),
            ("inventory", "Inventory"),
            ("finance", "Finance"),
            ("restaurant", "Restaurant"),
            ("ecommerce", "Ecommerce"),
            ("marketing", "Marketing"),
            ("analytics", "Analytics"),
            ("operations", "Operations"),
        ],
        default="operations",
        required=True,
    )
    tenant_assignable = fields.Boolean(
        string="Tenant Admin Can Assign",
        default=True,
        help="Allow a business owner or tenant admin to assign this role to users.",
    )
    description = fields.Text(translate=True)
    technical_group_xmlids = fields.Text(
        string="Technical Group XML IDs",
        help="One Odoo group XML ID per line. Missing optional module groups are ignored and shown as pending.",
    )
    group_ids = fields.Many2many(
        "res.groups",
        "tijara_business_role_group_rel",
        "role_id",
        "group_id",
        string="Additional Technical Groups",
        help="Optional advanced mapping. Only allow-listed groups are applied by tenant admin assignments.",
    )
    resolved_group_ids = fields.Many2many(
        "res.groups",
        compute="_compute_role_resolution",
        string="Resolved Groups",
    )
    missing_group_xmlids = fields.Text(
        compute="_compute_role_resolution",
        string="Missing Optional Groups",
    )
    blocked_group_xmlids = fields.Text(
        compute="_compute_role_resolution",
        string="Blocked Groups",
    )

    _code_unique = models.Constraint(
        "unique (code)",
        "Business role code must be unique.",
    )

    @api.depends("technical_group_xmlids", "group_ids")
    def _compute_role_resolution(self):
        for role in self:
            groups, missing, blocked = role._resolve_groups()
            role.resolved_group_ids = [(6, 0, groups.ids)]
            role.missing_group_xmlids = "\n".join(missing)
            role.blocked_group_xmlids = "\n".join(blocked)

    def _xmlid_lines(self):
        self.ensure_one()
        lines = []
        for raw_line in (self.technical_group_xmlids or "").replace(",", "\n").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        return lines

    def _group_external_ids(self, groups):
        if not groups:
            return {}
        data = self.env["ir.model.data"].sudo().search(
            [
                ("model", "=", "res.groups"),
                ("res_id", "in", groups.ids),
            ]
        )
        result = {}
        for item in data:
            result[item.res_id] = "%s.%s" % (item.module, item.name)
        return result

    def _resolve_groups(self):
        groups = self.env["res.groups"]
        missing = []
        blocked = []
        group_xmlids = self._group_external_ids(self.group_ids)

        for group in self.group_ids:
            xmlid = group_xmlids.get(group.id)
            if xmlid in self._ALLOWED_TENANT_GROUP_XMLIDS:
                groups |= group
            else:
                blocked.append(xmlid or group.display_name)

        for xmlid in self._xmlid_lines():
            if xmlid not in self._ALLOWED_TENANT_GROUP_XMLIDS:
                blocked.append(xmlid)
                continue
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if not record:
                missing.append(xmlid)
                continue
            if record._name != "res.groups":
                blocked.append(xmlid)
                continue
            groups |= record
        return groups, missing, blocked

    def _collect_assignment_groups(self):
        groups = self.env["res.groups"]
        missing = []
        blocked = []
        for role in self:
            role_groups, role_missing, role_blocked = role._resolve_groups()
            groups |= role_groups
            missing.extend(role_missing)
            blocked.extend(role_blocked)
        return groups, sorted(set(missing)), sorted(set(blocked))

    def _protected_common_groups(self):
        groups = self.env["res.groups"]
        for xmlid in self._PROTECTED_COMMON_GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups


class TijaraUserRoleAssignment(models.Model):
    _name = "tijara.user.role.assignment"
    _description = "Tijara User Role Assignment"
    _order = "write_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one("res.users", required=True, string="User")
    role_ids = fields.Many2many(
        "tijara.business.role",
        "tijara_user_role_assignment_role_rel",
        "assignment_id",
        "role_id",
        string="Business Roles",
        domain="[('tenant_assignable', '=', True), ('active', '=', True)]",
    )
    resolved_group_ids = fields.Many2many(
        "res.groups",
        compute="_compute_role_resolution",
        string="Groups To Apply",
    )
    missing_group_xmlids = fields.Text(
        compute="_compute_role_resolution",
        string="Missing Optional Groups",
    )
    blocked_group_xmlids = fields.Text(
        compute="_compute_role_resolution",
        string="Blocked Groups",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("applied", "Applied"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    applied_by_id = fields.Many2one("res.users", readonly=True)
    applied_at = fields.Datetime(readonly=True)
    notes = fields.Text()

    _user_company_active_unique = models.Constraint(
        "unique (user_id, company_id, active)",
        "Only one active role assignment is allowed per user and company.",
    )

    @api.depends("user_id", "company_id")
    def _compute_name(self):
        for assignment in self:
            if assignment.user_id and assignment.company_id:
                assignment.name = "%s - %s" % (
                    assignment.user_id.display_name,
                    assignment.company_id.display_name,
                )
            else:
                assignment.name = _("New Role Assignment")

    @api.depends("role_ids", "role_ids.technical_group_xmlids", "role_ids.group_ids")
    def _compute_role_resolution(self):
        for assignment in self:
            groups, missing, blocked = assignment.role_ids._collect_assignment_groups()
            assignment.resolved_group_ids = [(6, 0, groups.ids)]
            assignment.missing_group_xmlids = "\n".join(missing)
            assignment.blocked_group_xmlids = "\n".join(blocked)

    def _check_can_manage_roles(self):
        if self.env.user.has_group("base.group_system"):
            return
        if self.env.user.has_group("tijara_base.group_tijara_manager"):
            return
        raise AccessError(_("Only a tenant admin or system administrator can manage user role assignments."))

    def _check_tenant_scope(self):
        if self.env.user.has_group("base.group_system"):
            return
        allowed_companies = self.env.user.company_ids
        for assignment in self:
            if assignment.company_id not in allowed_companies:
                raise AccessError(_("You can only assign roles inside your own tenant company."))
            if assignment.user_id.company_ids and not (assignment.user_id.company_ids & allowed_companies):
                raise AccessError(_("You can only assign roles to users in your tenant company."))

    def _all_tenant_assignable_groups(self):
        role_model = self.env["tijara.business.role"]
        roles = role_model.search([("tenant_assignable", "=", True), ("active", "=", True)])
        groups, _missing, _blocked = roles._collect_assignment_groups()
        return groups

    def action_apply_roles(self):
        self._check_can_manage_roles()
        self._check_tenant_scope()
        role_model = self.env["tijara.business.role"]
        protected_groups = role_model._protected_common_groups()
        assignable_groups = self._all_tenant_assignable_groups()
        for assignment in self:
            if assignment.blocked_group_xmlids:
                raise UserError(
                    _(
                        "This assignment contains blocked technical groups. Remove them before applying roles:\n%s"
                    )
                    % assignment.blocked_group_xmlids
                )
            selected_groups, _missing, _blocked = assignment.role_ids._collect_assignment_groups()
            removable_groups = assignable_groups - selected_groups - protected_groups
            commands = []
            for group in selected_groups:
                if group not in assignment.user_id.group_ids:
                    commands.append((4, group.id))
            for group in removable_groups:
                if group in assignment.user_id.group_ids:
                    commands.append((3, group.id))
            values = {}
            if assignment.company_id not in assignment.user_id.company_ids:
                values["company_ids"] = [(4, assignment.company_id.id)]
            if not assignment.user_id.company_id:
                values["company_id"] = assignment.company_id.id
            if commands:
                values["group_ids"] = commands
            if values:
                assignment.user_id.sudo().write(values)
            assignment.write(
                {
                    "state": "applied",
                    "applied_by_id": self.env.user.id,
                    "applied_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reset_to_draft(self):
        self._check_can_manage_roles()
        self.write({"state": "draft"})
        return True

    def action_cancel(self):
        self._check_can_manage_roles()
        self.write({"state": "cancelled"})
        return True


class ResUsers(models.Model):
    _inherit = "res.users"

    tijara_role_assignment_ids = fields.One2many(
        "tijara.user.role.assignment",
        "user_id",
        string="Tijara Role Assignments",
    )
