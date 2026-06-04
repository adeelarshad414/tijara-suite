# Roadmap

## Phase 1: Retail MVP

- Product catalog with barcode and Urdu labels.
- Separate B2C retail and B2B trade price fields on products.
- POS sale flow.
- POS B2B/B2C and dine-in/takeaway/pickup action controls.
- Overall POS bill discount by percentage or fixed amount.
- Invoice and receipt template customization foundation.
- Backend QWeb PDF/HTML rendering for Tijara POS receipt and customer invoice
  templates.
- First-pass live browser POS receipt rendering from Tijara template profiles.
- Receipt printing and invoice barcode/QR return-scan foundation.
- Scanner/printer hardware registry with configuration testing.
- Signed local hardware bridge dry-run foundation.
- POS receipt print-to-bridge flow for configured browser-bridge receipt
  printers, including ESC/POS dry-run bytes for validation.
- Hardware bridge adapter foundations for ESC/POS, ZPL, CUPS/raw TCP/file,
  cash drawer, scale, scanner events, and customer-display output.
- SaaS runtime enforcement foundation for B2B, queue, promotion display, and
  customer display features.
- Public kiosk, queue display, customer display, menu board, and deals board
  routes.
- FBR dry-run/live HTTP adapter foundation.
- Daily analytics KPI collector foundation.
- Odoo transaction/HTTP test foundation for SaaS, FBR, analytics, and display
  route behavior.
- Playwright browser E2E scaffold for display/kiosk and staging authenticated
  POS/refund/report smoke paths.
- CI, security audit, backup, restore-drill, monitoring, and load-smoke
  baseline.
- Customer management.
- Supplier and purchase flow.
- Inventory stock in/out and branch stock.
- CSV bulk import/export for products, inventory, contacts, hardware,
  templates, storage positions, and promotions/deals.
- Low-stock, critical-stock, expiry, rack, shelf, bin, and storage-position
  foundation.
- Refund and exchange workflow.
- Cash shift opening and closing.
- POS customer display and queue ticket foundation.
- Dashboard, KPI history, chart, graph, pivot, and report catalog foundation.

## Phase 2: SaaS Platform

- Tenant provisioning request/admin console foundation.
- Database-per-tenant provisioning operator script.
- Plan and subscription management.
- Subscription invoice-generation and external payment-status foundation.
- Feature flag enforcement.
- Tenant onboarding wizard.
- Backups and restore automation.
- Admin support console.

## Phase 3: Pakistan Localization

- Urdu translations and RTL-aware screens.
- PKR defaults.
- CNIC, NTN, STRN, and branch identifiers.
- Certified FBR POS adapter.
- Pakistan receipt templates.
- Tax reports for retail operators.

## Phase 4: Vertical Packs

- Pharmacy: batch, expiry, prescription, MRP, generic names.
- Restaurant: dine-in, takeaway, pickup, tables, kitchen order tickets, service charges.
- Garments: size/color grids, seasonal stock, alterations.
- Electronics: warranty, serial/IMEI, repair handoff.
- Cloth/fabric: meter and yard sales, fabric rolls, tailoring services.
- Superstore: departments, aisles, shelves, case packs, promotions.
- Grocery: loose/weighed items, perishables, shelf life, cold chain.
- Bakery: recipes, shelf-life hours, allergens, production batches.

## Phase 5: Enterprise Readiness

- Offline-tolerant POS.
- Target-hardware certification and service installers for ESC/POS, ZPL, CUPS,
  scanners, scales, cash drawers, and customer displays.
- Hardware certification profiles and per-model QA evidence.
- Full thermal print payload replacement and advanced receipt template controls
  for line, tax, discount, payment, and fiscal sections.
- Self-service kiosk ordering checkout flow.
- Richer menu boards, promotion/deals screens, customer displays, and queue
  screens.
- Deeper automated analytics collectors for sales, purchase, stock, customer,
  supplier, refund, exchange, bill-discount, and cash-shift data.
- Inventory intelligence automation for reorder suggestions, dead-stock
  detection, FEFO/expiry planning, stock placement audits, and shelf utilization.
- Approval workflows.
- Audit logs.
- Advanced RBAC.
- Open API and webhooks.
- CI/CD and release channels.
- Security hardening.
- Monitoring, alerting, and incident runbooks.
