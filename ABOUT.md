# About Tijara Suite

Tijara Suite is a Pakistan-focused, open-source-first enterprise business suite
built on Odoo Community and open-source infrastructure. It is designed as a
modular SaaS product for businesses that need POS, inventory, back office,
sales, purchase, procurement, expenses, customer management, ecommerce,
delivery, analytics, hardware integration, and production operations in one
shared platform.

The goal is to give Pakistani retailers, restaurants, wholesalers, and
multi-branch operators a practical community-friendly system that can start on a
local PC, grow into a branch server, and later run as a hosted SaaS platform.

## Purpose

Tijara Suite exists to solve the daily operating needs of real businesses:

- Fast cashier checkout for B2C walk-in sales and B2B customer sales.
- Reliable inventory control with stock locations, racks, shelves, bins,
  low-stock alerts, expiry tracking, and import/export.
- Back-office operations for expenses, salary records, purchases, procurement,
  suppliers, reporting, and audit history.
- Restaurant and cafe workflows for dine-in, takeaway, pickup, delivery,
  service charges, tax policy, kitchen flow, queue display, and kiosk ordering.
- Ecommerce storefront and account portal connected to inventory, customers,
  delivery, returns, and payments.
- Pakistan localization with PKR, configurable GST, Urdu/English operations,
  Urdu/English invoice printing, FBR readiness, local delivery providers, and
  local payment provider readiness.
- SaaS feature control so each tenant or business plan can enable or disable
  advanced features such as B2B pricing, customer display, queue display,
  promotion screens, kiosk, ecommerce, delivery operations, analytics, and
  hardware bridge access.

## Who It Is For

The suite is designed to be reusable across multiple Pakistani business
verticals:

- Superstores and mini-marts
- Grocery stores
- Pharmacies
- Cosmetics shops
- Bakeries
- Cafes, fast food counters, and restaurants
- Cloth, fabric, garments, uniforms, and tailoring businesses
- Shoes stores and shoes brands
- Mobile shops
- Electronics and appliance stores
- Wholesale, distribution, and multi-branch retail

Each vertical should share the same enterprise foundation while allowing
business-specific product attributes, pricing, tax, receipt, delivery, and
operational workflows.

## Core Capabilities

### POS And Retail

- Touch-friendly, cross-device, cross-browser cashier interface.
- Keyboard-first and Enter-friendly workflows for counters where touch or mouse
  use is not practical.
- B2C and B2B selling modes with separate inventory prices.
- Barcode and QR workflows for scanning products, invoices, and return receipts.
- Refund and exchange support with invoice barcode scanning.
- Overall bill discount by percentage or fixed amount, with both values kept in
  sync automatically.
- Walk-in and named customer support.
- Loyalty program foundation.
- Cash, card, PSP, and mixed payment readiness.
- Configurable receipt and invoice templates.
- English-only, Urdu-only, and bilingual print modes.

### Inventory And Warehousing

- Product, category, unit, price, and tax setup.
- Low-stock and expiry alerts.
- Warehouse, store, shelf, rack, bin, aisle, and placement metadata.
- Pharmacy expiry and batch foundations.
- Grocery and bakery perishable item foundations.
- Garment, cloth, shoes, electronics, and mobile retail attributes.
- Bulk import/export for operational data.

### Restaurant, Kiosk, And Displays

- Dine-in, takeaway, pickup, and delivery service modes.
- Cafe and restaurant tax/service-charge policy support.
- Kiosk self-ordering foundation.
- Customer display for live order visibility.
- Queue display for order status.
- Promotion, menu, and deals display screens.
- Kitchen and order-flow readiness for food service operations.

### Back Office

- Sales, purchase, procurement, expense, salary, customer, and supplier
  foundations.
- Role-based demo personas and workflow guides.
- Audit-friendly history, reports, exports, and evidence generation.
- Dashboards for owner, finance, operations, inventory, delivery, hardware,
  FBR, PSP, and DevOps views.

### Ecommerce And Delivery

- Storefront, checkout, account portal, saved addresses, order history, and
  return/exchange request foundations.
- Delivery provider profiles for Pakistan couriers and in-house riders.
- Delivery retry and backoff queue.
- Delivery exception dashboard and SLA breach evidence.
- Delivery reconciliation reports.

### SaaS And Tenant Operations

- SaaS feature flags and plan-level controls.
- Tenant provisioning foundations.
- Subscription billing foundations.
- Protected release evidence chain for staging and production readiness.
- Centralized runtime configuration and secret handling.

### Hardware, Payments, And FBR Readiness

- Local hardware bridge foundation for ESC/POS printers, CUPS, ZPL labels, cash
  drawers, scanners, scales, and customer displays.
- Dry-run and dummy certification evidence paths for development and demos.
- FBR queue and adapter foundation for future certified provider integration.
- JazzCash, Easypaisa, Stripe, and reconciliation readiness foundations.

Live production use still requires real hardware certification, real FBR
provider credentials, payment provider certification, and compliance testing
before customer go-live.

## Open-Source Position

The public product foundation is built around Odoo Community and open-source
tools. The repository should remain safe for community collaboration:

- Do not commit real API keys, database passwords, payment secrets, FBR
  credentials, courier tokens, or customer data.
- Keep runtime variables in `.env` and secrets in `secrets/.env.secrets`.
- Keep example values in `.env.example` and `secrets/.env.secrets.example`.
- Use real provider credentials only in staging or production secret managers.
- Prefer open-source components for core behavior and avoid proprietary
  dependencies in the shared foundation.

## How To Use The Application

For a local demo or development run:

```bash
cp .env.example .env
mkdir -p secrets
cp secrets/.env.secrets.example secrets/.env.secrets
make up
make install-suite
make upgrade-pkr-gst
make verify-pkr-gst
make seed-pos-demo
make seed-demo-users
```

Open Odoo at:

```text
http://localhost:8069
```

Use the public-safe demo personas in `docs/TEST_CREDENTIALS.csv` and follow the
role workflows in:

- `docs/USER_GUIDE_ALL_USERS.md`
- `docs/HOW_TO_USE_GUIDELINES.md`
- `docs/VISUAL_USER_GUIDE_ALL_FUNCTIONS.md`
- `docs/SCREENSHOT_USER_GUIDE.md`
- `docs/BILINGUAL_QUICK_STARTS.md`

For local service control:

```bash
bash scripts/tijara-start.sh --all --install-suite --seed-demo
bash scripts/tijara-stop.sh --force-kill-ports
python3 scripts/tijara_services.py status
```

For staging or server setup:

```bash
python3 scripts/tijara_host.py preflight --all-profiles
python3 scripts/tijara_host.py init-config --environment staging --generate-secrets
python3 scripts/tijara_host.py deploy --with-hardware --with-monitoring --install-suite
```

For validation and release evidence:

```bash
make validate
make local-e2e-evidence
make protected-pos-matrix-evidence
make protected-release-chain
```

## Production Readiness Status

Tijara Suite has a strong enterprise product foundation, broad module coverage,
documentation, deployment automation, monitoring dashboards, local evidence
generation, and protected release workflow scaffolding.

It is not fully production-certified until these items are completed with real
staging or production evidence:

- Protected authenticated browser POS checkout, refund, print, and offline
  replay matrix on a real self-hosted protected runner.
- Physical hardware certification for printers, scanners, drawers, scales, and
  displays.
- FBR certified provider integration, credentials, sandbox sign-off, and live
  compliance testing.
- JazzCash, Easypaisa, Stripe, and other PSP certification for signatures,
  settlement, refunds, chargebacks, and reconciliation.
- Courier provider certification and live webhook/reconciliation evidence.
- Tenant DNS, TLS, ingress, backup, restore, monitoring, alerting, load, and
  security evidence from protected infrastructure.

The current project status is tracked in `PROGRESS.md`. Deployment and
operations details are tracked in `DEPLOY.md`.

