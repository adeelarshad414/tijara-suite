# Retail Operations, Hardware, and Data Exchange

This guide tracks the open-source operational foundation for invoice templates,
barcode/QR return scanning, scanner/printer setup, and bulk import/export.

## Invoice and Receipt Templates

Managers can configure invoice, receipt, refund/exchange, quotation, and
inventory-label templates from:

```text
Tijara > Configuration > Retail Configuration > Invoice and Receipt Templates
```

Template records support:

- Template scope: POS receipt, customer invoice, refund/exchange, quotation, or
  inventory label.
- Layout: compact, standard, detailed, or custom HTML.
- Language mode: English, Urdu, or bilingual.
- Printer width: 58 mm, 80 mm, A4, or custom dimensions.
- Printer device assignment from the Tijara hardware registry.
- Barcode source: Tijara invoice barcode, order/invoice number, FBR invoice
  number, or a custom value.
- Display flags for logo, customer, cashier, tax breakdown, discount breakdown,
  payment summary, company NTN/STRN, QR, barcode, and return policy.
- English and Urdu titles, headers, footers, terms, and return policy text.
- Custom HTML body and custom CSS for future report/POS rendering.

Current implementation stores and exposes these settings in Odoo backend views
and CSV import/export. The configured profile renders through backend QWeb
PDF/HTML reports for customer invoices, POS orders, and inventory product
labels. English-only, Urdu-only, and bilingual modes are enforced in the report
body, including title/header/footer/policy text and product line names where an
Urdu product name is configured. The live browser POS receipt screen consumes
the configured POS receipt profile during cashier checkout and respects the
same header/footer language mode. A POS configuration can also select a local
bridge receipt printer; when that printer is configured, the browser POS print
action submits the rendered receipt HTML/text payload to Odoo, Odoo signs the
bridge request, and the POS order stores the bridge print status, job id,
response JSON, and printed timestamp. The remaining receipt work is deeper
thermal print payload replacement and advanced control over the standard Odoo
line, tax, and payment summary layout.

Template actions:

- Use the `Tijara Invoice` button on customer invoices and credit notes.
- Use the `Tijara Receipt` button on POS orders.
- Use the `Tijara Inventory Label` report/action on product templates to print
  product barcode/QR labels in English, Urdu, or bilingual mode.
- Assign a default POS receipt template on the POS configuration.
- Assign an inventory label template on the product form when a product needs a
  specific Urdu/bilingual label profile.
- Assign a local bridge receipt printer on the POS configuration when the
  browser POS print button should submit receipts through the bridge.
- Optionally assign a specific customer invoice template on the invoice form.

Custom HTML supports simple escaped tokens:

- `{{ document_number }}`
- `{{ document_date }}`
- `{{ customer_name }}`
- `{{ cashier_name }}`
- `{{ company_name }}`
- `{{ amount_total }}`
- `{{ amount_tax }}`
- `{{ barcode_value }}`
- `{{ fbr_invoice_number }}` for POS orders
- `{{ sale_type }}`, `{{ service_mode }}`, and `{{ pickup_code }}` on the
  browser POS receipt screen

## Scanner and Printer Registry

Hardware is configured from:

```text
Tijara > Configuration > Retail Configuration > Hardware Devices
```

Supported registry categories include receipt printers, label printers, barcode
scanners, QR scanners, cash drawers, weighing scales, customer displays, and
fiscal devices.

Connection metadata supports USB, network, serial, Bluetooth, browser bridge,
keyboard-wedge scanners, and CUPS/system printers. Printer settings include
ESC/POS, ZPL, PDF, browser print, CUPS, paper width, DPI, barcode/QR support,
duplex support, and cash-drawer auto-open. Scanner settings include
keyboard-wedge, serial, network, and browser-bridge modes.

The Test Configuration action validates required connection settings and marks a
device as ready. Browser-bridge devices can also run `Bridge Health` and `Send
Bridge Test Job`, which call the local bridge with signed requests and store the
last bridge job id, operation, HTTP status, and JSON result.

The local bridge foundation lives in `hardware-bridge/` and supports dry-run
routes for receipt printing, label printing, cash-drawer open, customer-display
output, scale read, scanner events, and generic tests. Receipt print dry-runs can
produce an ESC/POS byte stream from the rendered receipt text and store it as
base64 inside the bridge job file for audit/testing. Adapter foundations now
cover ESC/POS receipt bytes, ZPL label bytes, CUPS/raw TCP/file delivery,
cash-drawer pulse bytes, scale readings, scanner-event JSON, and
customer-display JSON. Production rollout still requires target-hardware
validation and support runbooks for each device model.

## Return Scanning

Refund/exchange requests can scan or enter an invoice barcode/QR value from:

```text
Tijara > Retail Operations > Refunds and Exchanges
```

The scan action accepts plain values and these prefixes:

- `TJINV:` for Tijara POS invoice barcode values.
- `POS:` for POS order references.
- `INV:` for customer invoice names, payment references, or refs.
- `FBR:` for FBR invoice numbers when available.

When a match is found, the request stores the matched POS order or customer
invoice, fills the customer and original reference, and creates return lines
from the original sale/invoice lines. When no match is found, the request keeps
the scan status and message for cashier follow-up.

## Bulk Import and Export

Managers can run CSV import/export operations from:

```text
Tijara > Retail Operations > Bulk Import / Export
```

Supported data types:

- Products and prices, including B2C/B2B prices and Pakistan product metadata.
- Inventory quantities by product and stock location.
- Customers and suppliers.
- Hardware devices for scanner/printer/customer-display setup.
- Invoice and receipt templates.
- Storage positions for warehouse, store, rack, shelf, and bin setup.
- Promotions and deals.

Every operation can export its CSV template from the form. Import operations
read UTF-8 CSV files. Export operations generate downloadable CSV results.

## CSV Safety Rules

- Product rows require at least `name`, `default_code`, or `barcode`.
- Inventory rows identify products by `default_code` or `barcode`.
- Contact rows require at least `name`, `ref`, `email`, `phone`, or `mobile`.
- Hardware device rows require `code`.
- Invoice/receipt template rows require `name`.
- Storage position rows require `code`.
- Promotion rows require `code`.
- Optional-module columns are ignored safely when the field is not installed in
  the current database.

## Deployment Notes

Keyboard-wedge scanners can work through browser/text input without a local
driver. Printers, cash drawers, scales, and customer displays should use the
local hardware bridge in production. The bridge is open-source, runs on the shop
machine, exposes signed local HTTP endpoints, and never requires raw database
credentials.
