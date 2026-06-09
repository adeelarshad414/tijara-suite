def print_export(name, value):
    print("export %s=%s" % (name, value))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


company = env.company
required_logins = {
    "superadmin@demo.tijara-suite.local",
    "tenant-admin@demo.tijara-suite.local",
    "cashier@demo.tijara-suite.local",
    "inventory-manager@demo.tijara-suite.local",
    "accountant@demo.tijara-suite.local",
    "expense-manager@demo.tijara-suite.local",
    "salary-manager@demo.tijara-suite.local",
    "loyalty-manager@demo.tijara-suite.local",
    "vertical-manager@demo.tijara-suite.local",
    "promotion-manager@demo.tijara-suite.local",
    "analytics-manager@demo.tijara-suite.local",
    "restaurant@demo.tijara-suite.local",
    "public-display@demo.tijara-suite.local",
}
user_count = env["res.users"].sudo().search_count([("login", "in", list(required_logins))])
require(user_count == len(required_logins), "Not all enterprise demo users exist.")

required_verticals = {
    "superstore",
    "grocery",
    "bakery",
    "restaurant",
    "cloth",
    "cosmetics",
    "uniform",
    "garments",
    "shoes",
    "pharmacy",
    "fast_food",
    "cafe",
    "mobile_shop",
    "electronics",
}
products = env["product.template"].sudo().search([("default_code", "=like", "TIJARA-DEMO-%")])
seeded_verticals = set(products.mapped("tijara_vertical_tag"))
missing_verticals = required_verticals.difference(seeded_verticals)
require(not missing_verticals, "Missing demo verticals: %s" % ", ".join(sorted(missing_verticals)))

loyalty_customers = env["res.partner"].sudo().search_count(
    [("tijara_loyalty_opt_in", "=", True), ("tijara_loyalty_number", "!=", False)]
)
require(loyalty_customers >= 2, "Expected at least two seeded loyalty customers.")

expense_states = set(env["tijara.expense.request"].sudo().search([]).mapped("state"))
require({"draft", "submitted", "approved", "paid"}.issubset(expense_states), "Expense states are incomplete.")

salary_batch = env["tijara.salary.batch"].sudo().search([("name", "=", "Tijara Demo Salary Batch")], limit=1)
require(salary_batch and len(salary_batch.line_ids) >= 3, "Seeded salary batch is missing lines.")

receipt_scopes = set(
    env["tijara.receipt.profile"]
    .sudo()
    .search([("company_id", "=", company.id)])
    .mapped("template_scope")
)
require(
    {"pos_receipt", "customer_invoice", "refund_exchange", "quotation"}.issubset(receipt_scopes),
    "Invoice/receipt templates are incomplete.",
)

kiosk = env["tijara.kiosk.profile"].sudo().search([("name", "=", "Tijara Demo Kiosk Profile")], limit=1)
require(kiosk and kiosk.allow_delivery, "Demo kiosk delivery mode is not enabled.")

dashboard_codes = set(env["tijara.analytics.dashboard"].sudo().search([]).mapped("code"))
required_dashboards = {
    "owner_overview",
    "inventory_control",
    "pos_performance",
    "purchase_procurement",
    "customers_promotions",
    "backoffice_finance",
    "restaurant_cafe_operations",
    "vertical_retail_mix",
    "loyalty_customer_retention",
}
require(required_dashboards.issubset(dashboard_codes), "Dashboard catalog is incomplete.")

report_codes = set(env["tijara.analytics.report"].sudo().search([]).mapped("code"))
required_reports = {
    "daily_sales_summary",
    "inventory_health",
    "purchase_reorder_planning",
    "customer_promotion_performance",
    "backoffice_expense_salary_audit",
    "restaurant_cafe_charge_policy",
    "vertical_catalog_performance",
    "loyalty_customer_history",
    "display_queue_operations",
}
require(required_reports.issubset(report_codes), "Report catalog is incomplete.")

require(company.tijara_gst_enabled, "GST policy should be enabled in the demo company.")
require(company.tijara_delivery_charge_enabled, "Delivery charge policy should be enabled in the demo company.")
require(company.tijara_loyalty_enabled, "Loyalty policy should be enabled in the demo company.")
require(
    env.ref("tijara_base.tijara_web_login_branding", raise_if_not_found=False),
    "Tijara login branding view is missing.",
)

print_export("TIJARA_ENTERPRISE_SEED_STATUS", "ready")
print_export("TIJARA_ENTERPRISE_DEMO_USER_COUNT", user_count)
print_export("TIJARA_ENTERPRISE_VERTICAL_COUNT", len(seeded_verticals))
print_export("TIJARA_ENTERPRISE_DASHBOARD_COUNT", len(required_dashboards))
print_export("TIJARA_ENTERPRISE_REPORT_COUNT", len(required_reports))
print_export("TIJARA_ENTERPRISE_RECEIPT_TEMPLATE_SCOPES", ",".join(sorted(receipt_scopes)))
