import base64
import csv
import io
import os
import shlex


ROLE_GROUPS = {
    "platform_superadmin": [
        "base.group_user",
        "base.group_system",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "point_of_sale.group_pos_manager",
        "stock.group_stock_manager",
        "account.group_account_manager",
        "sales_team.group_sale_manager",
        "purchase.group_purchase_manager",
    ],
    "tenant_admin": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "point_of_sale.group_pos_manager",
        "stock.group_stock_manager",
        "account.group_account_manager",
        "sales_team.group_sale_manager",
        "purchase.group_purchase_manager",
    ],
    "cashier": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "point_of_sale.group_pos_user",
    ],
    "inventory_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "stock.group_stock_manager",
    ],
    "accountant": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "account.group_account_user",
        "account.group_account_manager",
    ],
    "expense_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "account.group_account_user",
    ],
    "salary_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "account.group_account_user",
    ],
    "loyalty_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "point_of_sale.group_pos_manager",
        "sales_team.group_sale_manager",
    ],
    "vertical_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "point_of_sale.group_pos_manager",
        "stock.group_stock_manager",
        "sales_team.group_sale_manager",
        "purchase.group_purchase_manager",
    ],
    "promotion_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "point_of_sale.group_pos_manager",
        "sales_team.group_sale_manager",
    ],
    "ecommerce_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "stock.group_stock_user",
        "sales_team.group_sale_manager",
    ],
    "ecommerce_customer": [
        "base.group_portal",
    ],
    "analytics_manager": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "tijara_base.group_tijara_manager",
        "account.group_account_manager",
        "stock.group_stock_manager",
        "sales_team.group_sale_manager",
        "purchase.group_purchase_manager",
    ],
    "restaurant_operator": [
        "base.group_user",
        "tijara_base.group_tijara_user",
        "point_of_sale.group_pos_user",
    ],
    "public_display": [
        "base.group_user",
        "tijara_base.group_tijara_user",
    ],
}

POS_PERSONAS = {
    "platform_superadmin",
    "tenant_admin",
    "cashier",
    "loyalty_manager",
    "promotion_manager",
    "restaurant_operator",
    "vertical_manager",
}


def ref(xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


def print_export(name, value):
    print("export %s=%s" % (name, shlex.quote(str(value or ""))))


def load_credentials():
    encoded = os.environ.get("TIJARA_DEMO_USERS_CSV_B64")
    if not encoded:
        raise ValueError("TIJARA_DEMO_USERS_CSV_B64 is required.")
    text = base64.b64decode(encoded).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"persona", "email", "password"}
    missing_header = required.difference(rows[0].keys() if rows else [])
    if missing_header:
        raise ValueError("Missing credential CSV columns: %s" % ", ".join(sorted(missing_header)))
    return [
        {
            "persona": (row.get("persona") or "").strip(),
            "email": (row.get("email") or "").strip(),
            "password": row.get("password") or "",
        }
        for row in rows
        if (row.get("persona") or "").strip() and (row.get("email") or "").strip()
    ]


def grant_groups(user, xmlids):
    groups = [group for group in (ref(xmlid) for xmlid in xmlids) if group]
    if not groups:
        return []
    if "base.group_portal" in xmlids:
        exclusive_groups = [
            group
            for group in (
                ref("base.group_user"),
                ref("base.group_public"),
            )
            if group
        ]
        if exclusive_groups and "group_ids" in user._fields:
            user.sudo().write({"group_ids": [(3, group.id) for group in exclusive_groups]})
        elif exclusive_groups and "groups_id" in user._fields:
            user.sudo().write({"groups_id": [(3, group.id) for group in exclusive_groups]})
    if "group_ids" in user._fields:
        user.sudo().write({"group_ids": [(4, group.id) for group in groups]})
    elif "groups_id" in user._fields:
        user.sudo().write({"groups_id": [(4, group.id) for group in groups]})
    else:
        for group in groups:
            if "user_ids" in group._fields:
                group.sudo().write({"user_ids": [(4, user.id)]})
            elif "users" in group._fields:
                group.sudo().write({"users": [(4, user.id)]})
    return groups


def ensure_user(row, company, pos_config=False):
    user_model = env["res.users"].sudo().with_context(
        no_reset_password=True,
        tracking_disable=True,
        mail_create_nosubscribe=True,
    )
    persona = row["persona"]
    values = {
        "name": persona.replace("_", " ").title(),
        "login": row["email"],
        "email": row["email"],
        "company_id": company.id,
        "company_ids": [(6, 0, [company.id])],
        "active": True,
    }
    user = user_model.search([("login", "=", row["email"])], limit=1)
    if user:
        user.write(values)
    else:
        user = user_model.create(values)
    groups = grant_groups(user, ROLE_GROUPS.get(persona, ["base.group_user"]))
    user.sudo().write({"password": row["password"]})
    if pos_config and persona in POS_PERSONAS and "pos_config_id" in user._fields:
        user.sudo().write({"pos_config_id": pos_config.id})
    return user, groups


company = env.company
env["tijara.localization.setup"].sudo().ensure_pakistan_defaults()

pos_config = env["pos.config"].sudo().search(
    [("company_id", "=", company.id), ("name", "=", "Tijara Demo POS")],
    limit=1,
)
if not pos_config:
    pos_config = env["pos.config"].sudo().search([("company_id", "=", company.id)], limit=1)

created = []
for credential in load_credentials():
    user, groups = ensure_user(credential, company, pos_config=pos_config)
    created.append((credential, user, groups))

env.cr.commit()

print_export("ODOO_DATABASE", env.cr.dbname)
print_export("TIJARA_DEMO_USERS_SOURCE", os.environ.get("TIJARA_DEMO_USERS_SOURCE", "docs/TEST_CREDENTIALS.csv"))
print_export("TIJARA_DEMO_USER_COUNT", len(created))
if pos_config:
    print_export("TIJARA_DEMO_POS_CONFIG_ID", pos_config.id)
    print_export("TIJARA_DEMO_POS_CONFIG_NAME", pos_config.display_name)

for credential, user, groups in created:
    key = credential["persona"].upper()
    print_export("TIJARA_DEMO_%s_LOGIN" % key, user.login)
    print("# %s groups: %s" % (credential["persona"], ", ".join(group.display_name for group in groups) or "none"))
