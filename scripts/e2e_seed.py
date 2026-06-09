import os
import shlex

company = env.company
env["ir.config_parameter"].sudo().set_param("tijara.saas.enforcement_enabled", "1")
localization_setup = env["tijara.localization.setup"].sudo()
localization_setup.ensure_pakistan_defaults()
standard_sale_tax = localization_setup.get_standard_sale_tax(company)
standard_sale_tax_commands = [(6, 0, [standard_sale_tax.id])] if standard_sale_tax else []


def ref(xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


def grant_groups(user, xmlids):
    groups = [group for group in (ref(xmlid) for xmlid in xmlids) if group]
    if not groups:
        return []
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


def print_export(name, value):
    print("export %s=%s" % (name, shlex.quote(str(value or ""))))

enterprise_plan = env.ref("tijara_saas_control.plan_enterprise")
customer = env["res.partner"].sudo().search([("name", "=", "Tijara E2E Billing Customer")], limit=1)
if not customer:
    customer = env["res.partner"].sudo().create({"name": "Tijara E2E Billing Customer"})

subscription = env["tijara.saas.subscription"].sudo().search(
    [
        ("company_id", "=", company.id),
        ("database_name", "=", env.cr.dbname),
        ("state", "in", ("trial", "active")),
    ],
    limit=1,
)
if not subscription:
    env["tijara.saas.subscription"].sudo().create(
        {
            "name": "Tijara E2E Enterprise Subscription",
            "tenant_name": company.name,
            "database_name": env.cr.dbname,
            "customer_id": customer.id,
            "company_id": company.id,
            "plan_id": enterprise_plan.id,
            "state": "active",
        }
    )
else:
    subscription.write({"plan_id": enterprise_plan.id, "state": "active"})


def screen(slug, name, display_type, price_mode="b2c"):
    record = env["tijara.display.screen"].sudo().search(
        [("company_id", "=", company.id), ("url_slug", "=", slug)],
        limit=1,
    )
    values = {
        "name": name,
        "code": slug,
        "url_slug": slug,
        "display_type": display_type,
        "company_id": company.id,
        "price_mode": price_mode,
        "refresh_seconds": 5,
        "active": True,
    }
    if record:
        record.write(values)
    else:
        record = env["tijara.display.screen"].sudo().create(values)
    return record


menu_screen = screen("tijara-e2e-menu", "Tijara E2E Menu", "menu_board")
kiosk_screen = screen("tijara-e2e-kiosk", "Tijara E2E Kiosk", "kiosk")
customer_display = screen("tijara-e2e-customer", "Tijara E2E Customer Display", "customer_display")

product = env["product.product"].sudo().search([("default_code", "=", "TJ-E2E-BUN")], limit=1)
product_values = {
    "available_in_pos": True,
    "sale_ok": True,
    "lst_price": 120,
    "tijara_b2c_price": 120,
    "tijara_b2b_price": 100,
}
if standard_sale_tax_commands:
    product_values["taxes_id"] = standard_sale_tax_commands
if not product:
    product_values.update(
        {
            "name": "E2E Bakery Bun",
            "default_code": "TJ-E2E-BUN",
            "barcode": "2000000000011",
        }
    )
    product = env["product.product"].sudo().create(product_values)
else:
    product.write(product_values)

content = env["tijara.display.content"].sudo().search(
    [("company_id", "=", company.id), ("name", "=", "E2E Bakery Bun")],
    limit=1,
)
content_values = {
    "name": "E2E Bakery Bun",
    "content_type": "menu_item",
    "title_english": "E2E Bakery Bun",
    "subtitle_english": "Seeded browser checkout item",
    "product_id": product.id,
    "b2c_price": 120,
    "b2b_price": 100,
    "company_id": company.id,
    "screen_ids": [(6, 0, [menu_screen.id, kiosk_screen.id])],
}
if content:
    content.write(content_values)
else:
    env["tijara.display.content"].sudo().create(content_values)

profile = env["tijara.kiosk.profile"].sudo().search([("screen_id", "=", kiosk_screen.id)], limit=1)
profile_values = {
    "name": "Tijara E2E Kiosk Profile",
    "screen_id": kiosk_screen.id,
    "company_id": company.id,
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
if profile:
    profile.write(profile_values)
else:
    env["tijara.kiosk.profile"].sudo().create(profile_values)

refund_reason = env["tijara.refund.reason"].sudo().search([("code", "=", "E2E")], limit=1)
if not refund_reason:
    refund_reason = env["tijara.refund.reason"].sudo().create(
        {
            "name": "E2E Refund Scan",
            "code": "E2E",
            "requires_manager_approval": False,
        }
    )

state = env["tijara.customer.display.state"].sudo().search(
    [("screen_id", "=", customer_display.id), ("active", "=", True)],
    limit=1,
)
state_values = {
    "name": "Tijara E2E Customer Display State",
    "screen_id": customer_display.id,
    "status": "building",
    "order_reference": "E2E-POS-001",
    "customer_name": "Walk In",
    "amount_subtotal": 120,
    "discount_amount": 0,
    "tax_amount": 21.6 if standard_sale_tax else 0,
    "amount_total": 141.6 if standard_sale_tax else 120,
    "line_ids": [
        (5, 0, 0),
        (
            0,
            0,
            {
                "product_id": product.id,
                "name": "E2E Bakery Bun",
                "quantity": 1,
                "price_unit": 120,
                "price_subtotal": 120,
            },
        ),
    ],
}
if state:
    state.write(state_values)
else:
    env["tijara.customer.display.state"].sudo().create(state_values)

e2e_login = os.environ.get("TIJARA_E2E_LOGIN", "tijara-e2e@example.test")
e2e_password = os.environ.get("TIJARA_E2E_PASSWORD")
e2e_user = env["res.users"]
e2e_groups = []
if e2e_password:
    e2e_user = env["res.users"].sudo().search([("login", "=", e2e_login)], limit=1)
    user_values = {
        "name": "Tijara E2E POS User",
        "login": e2e_login,
        "email": e2e_login,
        "company_id": company.id,
        "company_ids": [(6, 0, [company.id])],
    }
    if e2e_user:
        e2e_user.write(user_values)
    else:
        e2e_user = env["res.users"].sudo().create(user_values)
    e2e_groups = grant_groups(
        e2e_user,
        [
            "base.group_user",
            "point_of_sale.group_pos_user",
            "point_of_sale.group_pos_manager",
            "tijara_base.group_tijara_user",
            "tijara_base.group_tijara_manager",
        ],
    )
    e2e_user.sudo().write({"password": e2e_password})

env.cr.commit()

pos_config = env["pos.config"].sudo().search([("company_id", "=", company.id)], limit=1)
if e2e_user and pos_config and "pos_config_id" in e2e_user._fields:
    e2e_user.sudo().write({"pos_config_id": pos_config.id})
    env.cr.commit()

payment_method = pos_config.payment_method_ids[:1] if pos_config else env["pos.payment.method"]
e2e_pos_order = env["pos.order"]
if pos_config and payment_method:
    try:
        replay_result = env["tijara.offline.pos.queue"].sudo().tijara_capture_from_browser(
            {
                "source_app": "manual",
                "source_device_id": "tijara-e2e-seed",
                "source_order_uid": "tijara-e2e-report-order-%s" % env.cr.dbname,
                "pos_config_id": pos_config.id,
                "order_reference": "Tijara E2E Report Order",
                "audience": "b2c",
                "order_type": "takeaway",
                "payment_status": "paid",
                "amount_total": 141.6 if standard_sale_tax else 120,
                "amount_paid": 141.6 if standard_sale_tax else 120,
                "payment_method_id": payment_method.id,
                "payments": [
                    {
                        "amount": 141.6 if standard_sale_tax else 120,
                        "payment_method_id": payment_method.id,
                        "payment_reference": "TJ-E2E-REPORT",
                        "payment_status": "paid",
                    }
                ],
                "lines": [
                    {
                        "product_id": product.id,
                        "name": "E2E Bakery Bun",
                        "qty": 1,
                        "price_unit": 120,
                    }
                ],
            },
            replay=True,
        )
        e2e_pos_order = env["pos.order"].sudo().browse(
            replay_result.get("pos_order_id") or 0
        ).exists()
        env.cr.commit()
    except Exception as error:
        print("# Tijara E2E report POS order seed skipped: %s" % error)

print_export("ODOO_DATABASE", env.cr.dbname)
print_export("TIJARA_DISPLAY_SLUG", "tijara-e2e-menu")
print_export("TIJARA_KIOSK_SLUG", "tijara-e2e-kiosk")
print_export("TIJARA_CUSTOMER_DISPLAY_SLUG", "tijara-e2e-customer")
print_export("TIJARA_E2E_PRODUCT_ID", product.id)
print_export("TIJARA_E2E_PRODUCT_NAME", product.display_name)
print_export("TIJARA_E2E_CURRENCY", company.currency_id.name)
if standard_sale_tax:
    print_export("TIJARA_E2E_GST_TAX_ID", standard_sale_tax.id)
    print_export("TIJARA_E2E_GST_RATE", standard_sale_tax.amount)
print_export("TIJARA_E2E_REFUND_REASON_ID", refund_reason.id)
print_export("TIJARA_REFUND_ACTION_URL", "/odoo/action-tijara_retail_core.action_tijara_exchange_request")
print_export("TIJARA_OFFLINE_QUEUE_ACTION_URL", "/odoo/action-tijara_pos_experience.action_tijara_offline_pos_review")
if e2e_password:
    print_export("ODOO_USERNAME", e2e_login)
    if e2e_groups:
        print("# E2E user groups: %s" % ", ".join(group.display_name for group in e2e_groups))
if pos_config:
    print_export("TIJARA_POS_CONFIG_ID", pos_config.id)
    if payment_method:
        print_export("TIJARA_E2E_PAYMENT_METHOD_ID", payment_method.id)
        print_export("TIJARA_E2E_PAYMENT_METHOD_NAME", payment_method.display_name)
if e2e_pos_order:
    print_export("TIJARA_E2E_POS_ORDER_ID", e2e_pos_order.id)
    print_export(
        "TIJARA_REPORT_ORDER_URL",
        "/report/html/tijara_pos_pk.report_tijara_pos_receipt/%s" % e2e_pos_order.id,
    )
    print_export("TIJARA_E2E_REFUND_BARCODE", e2e_pos_order.tijara_invoice_barcode)
