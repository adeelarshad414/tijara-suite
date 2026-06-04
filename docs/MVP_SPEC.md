# MVP Specification

## MVP Goal

Launch a pilot-ready retail SaaS for one Pakistani superstore/general retail
customer, with enough structure to later enable pharmacy, restaurant, garments,
electronics, cloth/fabric, grocery, and bakery packs.

## Included in MVP

- Company setup with Pakistan fields.
- Product catalog with Urdu name, barcode alias, local SKU, and tax category.
- Separate B2C retail and B2B trade prices on product records.
- Customer profile with CNIC, NTN, STRN, Urdu name, and credit limit.
- POS sale workflow using Odoo POS as the first base.
- POS B2C/B2B sale type fields.
- First-pass POS B2B/B2C action control that can reprice existing ticket lines
  from Tijara B2C/B2B product fields.
- First-pass POS service-mode action control for dine-in, takeaway, and pickup.
- Overall POS bill discount by percentage or fixed amount, with automatic
  two-way recalculation between percentage, amount, bill base, and net bill.
- Invoice and receipt template settings for English, Urdu, or bilingual
  receipts, customer invoices, refund/exchange documents, and quotations.
- Backend QWeb PDF/HTML rendering for Tijara POS receipt and customer invoice
  templates.
- First-pass live browser POS receipt rendering from Tijara POS receipt
  profiles, including Urdu title/footer text, custom body token output,
  QR/barcode values, and return policy text.
- Invoice barcode/QR scanning on refund and exchange requests.
- POS customer display, menu board, deals board, kiosk, and queue configuration
  foundation.
- Hardware device registry for printers, scanners, cash drawer, weighing scale,
  customer display, fiscal devices, integration roles, print languages, scanner
  modes, and configuration testing.
- Local hardware bridge foundation with signed dry-run endpoints for receipt
  print, label print, cash drawer, scale, scanner event, and customer display
  test jobs.
- Browser POS receipt print-to-bridge flow for configured local bridge receipt
  printers, including order-level print status, job id, result JSON, and printed
  timestamp.
- Hardware bridge adapter foundations for ESC/POS receipt bytes, ZPL label
  bytes, CUPS/raw TCP/file delivery, cash-drawer pulse, scale reading, scanner
  event persistence, and customer-display output.
- Public kiosk, customer display, queue display, menu board, and deals/promotion
  display routes.
- SaaS runtime enforcement foundation for B2B sales, queue system, promotion
  display, and customer display.
- FBR queue dry-run/live HTTP adapter foundation.
- Manual and scheduled daily analytics KPI snapshot collector.
- CSV import/export foundation for products/prices, inventory quantities,
  contacts, hardware devices, invoice/receipt templates, storage positions, and
  promotions/deals.
- Cash shift open/close workflow.
- Refund and exchange request workflow with approval path.
- Purchase and inventory using standard Odoo flows.
- Inventory intelligence foundation for low-stock alerts, critical-stock alerts,
  expiry alerts, warehouse/store placement, racks, shelves, bins, and storage
  positions.
- Analytics and reporting foundation for dashboards, KPI history, trends,
  charts, graphs, pivots, and report catalog templates.
- SaaS plan/feature metadata.
- Docker Compose development deployment.
- Vertical feature foundations for pharmacy, restaurant, garments, electronics,
  cloth/fabric, superstore, grocery, and bakery.

## Not Yet Included

- Custom offline POS frontend.
- Certified/production FBR integration against the final approved provider/API.
- Subscription payment automation.
- Tenant database provisioning automation. A provisioning request/admin console
  foundation exists, but it does not create databases yet.
- Production monitoring stack.
- Target-hardware certification for ESC/POS, ZPL, CUPS, serial scale, scanner
  event, cash-drawer, and customer-display adapter paths.
- Full thermal print payload replacement and advanced receipt line/tax/payment
  layout controls.
- Automated Odoo module install tests.

## MVP Acceptance Criteria

- A developer can start Odoo with the custom addons mounted.
- The base, retail, POS Pakistan, and SaaS modules are visible in Apps.
- A manager can configure company Pakistan fields.
- A cashier/manager can create a cash shift.
- A cashier can apply an overall POS bill discount as either a percentage or an
  amount, and the linked value updates automatically.
- A cashier can switch the POS ticket between B2C and B2B sale type.
- A cashier can switch the POS ticket between dine-in, takeaway, and pickup.
- A manager can register a receipt printer or scanner.
- A manager can health-check a browser-bridge hardware device and send a signed
  dry-run bridge test job.
- A manager can assign a local bridge receipt printer to a POS configuration.
- A manager can configure invoice/receipt templates with language, layout,
  barcode source, display flags, printer assignment, and custom HTML/CSS.
- A user can print a Tijara customer invoice or POS receipt from backend QWeb
  reports using the configured template profile.
- A cashier can complete a POS checkout and see the browser receipt consume the
  configured Tijara POS receipt profile.
- A cashier can submit the browser POS receipt print action to a configured
  local bridge receipt printer and the POS order records the bridge job audit.
- A cashier can scan an invoice barcode/QR into a refund/exchange request and
  load the matched invoice lines.
- A manager can import and export CSV data for products, inventory, contacts,
  hardware devices, invoice/receipt templates, storage positions, and
  promotions/deals.
- A user can create a refund/exchange request and move it through approval.
- A manager can create SaaS plans and subscriptions.
- A manager can enable SaaS enforcement and block POS configuration options not
  included in the active subscription.
- A manager can create and track tenant provisioning requests.
- A manager can configure display screens, kiosk profiles, promotions/deals,
  and queue tickets.
- A customer or operator can open public display/kiosk routes for configured
  screens.
- A manager can define storage positions by warehouse, location, zone, aisle,
  rack, shelf, and bin.
- A manager can scan or review inventory alerts for low stock, critical stock,
  and expiring lots.
- A manager can view dashboard definitions, KPI history, charts, pivots, and
  report catalog templates.
- A manager can manually collect daily KPI snapshots; scheduled collection is
  installed disabled by default.
- SaaS plans can independently enable B2B sales, queue system, promotion
  display, and customer display features.
- SaaS plans can enable inventory intelligence and analytics/reporting features.
- Restaurant service profile supports dine-in, takeaway, and pickup.
- Urdu labels are present for the first backend terms.

## First Pilot Business

Use a general retail/superstore pilot before pharmacy or restaurant. It has the
widest overlap with the platform core and avoids pharmacy/regulatory and
restaurant/KOT complexity during the first proof.
