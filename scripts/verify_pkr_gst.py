import shlex


def print_export(name, value):
    print("export %s=%s" % (name, shlex.quote(str(value or ""))))


def fail(message):
    raise Exception(message)


company = env.company
setup = env["tijara.localization.setup"].sudo()
setup.ensure_pakistan_defaults()
tax = setup.get_standard_sale_tax(company)

currency = company.currency_id
print_export("ODOO_DATABASE", env.cr.dbname)
print_export("TIJARA_COMPANY_NAME", company.display_name)
print_export("TIJARA_COMPANY_CURRENCY", currency.name)
print_export("TIJARA_COMPANY_CURRENCY_SYMBOL", currency.symbol)
print_export("TIJARA_COMPANY_COUNTRY", company.country_id.code or "")

if currency.name != "PKR":
    fail("Expected company currency PKR, found %s." % currency.name)

if not tax:
    fail("Expected GST 18%% sales tax, found none.")

print_export("TIJARA_GST_TAX_ID", tax.id)
print_export("TIJARA_GST_TAX_NAME", tax.name)
print_export("TIJARA_GST_TAX_AMOUNT", tax.amount)
print_export("TIJARA_GST_TAX_USE", tax.type_tax_use)
print_export("TIJARA_GST_TAX_AMOUNT_TYPE", tax.amount_type)

if tax.amount != 18.0:
    fail("Expected GST tax amount 18.0, found %s." % tax.amount)
if tax.amount_type != "percent":
    fail("Expected GST tax amount_type percent, found %s." % tax.amount_type)
if tax.type_tax_use != "sale":
    fail("Expected GST tax use sale, found %s." % tax.type_tax_use)

standard_products = env["product.template"].sudo().search(
    [
        ("sale_ok", "=", True),
        ("tijara_tax_category", "=", "standard"),
    ],
    limit=20,
)
taxed_products = standard_products.filtered(lambda product: tax in product.taxes_id)
print_export("TIJARA_STANDARD_PRODUCT_COUNT_CHECKED", len(standard_products))
print_export("TIJARA_STANDARD_PRODUCT_GST_COUNT", len(taxed_products))
if standard_products and not taxed_products:
    fail("Standard sale products exist but none are mapped to GST 18%%.")

demo_product = env["product.template"].sudo().search(
    [("default_code", "=", "TIJARA-DEMO-RICE")],
    limit=1,
)
if demo_product:
    print_export("TIJARA_DEMO_PRODUCT", demo_product.display_name)
    print_export("TIJARA_DEMO_PRODUCT_PRICE", demo_product.list_price)
    print_export("TIJARA_DEMO_PRODUCT_TAXES", ",".join(demo_product.taxes_id.mapped("name")))
    if tax not in demo_product.taxes_id:
        fail("Demo product TIJARA-DEMO-RICE is not mapped to GST 18%%.")

env.cr.commit()
print_export("TIJARA_PKR_GST_STATUS", "verified")
