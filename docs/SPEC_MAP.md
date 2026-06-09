# Tijara Suite Spec Map

This generated spec map summarizes the current Odoo Community SaaS suite,
developer runtime, personas, public routes, and demo data used by the local
agentic development pipeline.

## Stack

| Area | Value |
|---|---|
| App | Tijara Suite |
| Type | Odoo Community SaaS web application |
| Version | 0.18.0 |
| Local URL | `http://localhost:8069` |
| Long polling | `http://localhost:8072` |
| Hardware bridge | `http://localhost:9109` |
| Database | PostgreSQL via Docker Compose |
| Optional profiles | `hardware`, `monitoring` |
| Diagram pack | `docs/DIAGRAMS.md` |

## Personas

| Persona | Demo email | Primary workflows |
|---|---|---|
| Platform superadmin | `superadmin@demo.tijara-suite.local` | SaaS plans, tenant provisioning, protected release evidence |
| Tenant admin | `tenant-admin@demo.tijara-suite.local` | Business configuration, feature flags, analytics, approvals |
| Cashier | `cashier@demo.tijara-suite.local` | POS checkout, refunds, receipt print, offline replay |
| Inventory manager | `inventory-manager@demo.tijara-suite.local` | Products, low stock, expiry, racks, shelves, bulk data |
| Accountant | `accountant@demo.tijara-suite.local` | Settlements, refunds, chargebacks, FBR queue, draft moves |
| Expense manager | `expense-manager@demo.tijara-suite.local` | Back-office expenses, approvals, paid/unpaid evidence |
| Salary manager | `salary-manager@demo.tijara-suite.local` | Salary batches, deductions, bonuses, payroll closeout |
| Loyalty manager | `loyalty-manager@demo.tijara-suite.local` | Walk-in capture, B2B/B2C customers, loyalty tiers and points |
| Vertical manager | `vertical-manager@demo.tijara-suite.local` | Vertical catalogs, B2B/B2C prices, stock policy, business settings |
| Promotion manager | `promotion-manager@demo.tijara-suite.local` | Promotions, menu/deal screens, customer display, queue display |
| Ecommerce manager | `ecommerce-manager@demo.tijara-suite.local` | Storefront channels, online catalog, B2B/B2C ecommerce pricing, pickup/delivery orders |
| Analytics manager | `analytics-manager@demo.tijara-suite.local` | Dashboards, reports, trends, KPI and audit review |
| Restaurant operator | `restaurant@demo.tijara-suite.local` | Dine-in, takeaway, pickup, kiosk, queue, kitchen tickets |
| Public display | `public-display@demo.tijara-suite.local` | Kiosk, queue, customer display, menu board, deals board route checks |

## Screen Inventory

| Screen | Route | Auth | Purpose |
|---|---|---|---|
| Odoo Login | `/web/login` | Public | Authentication entry point |
| Odoo App Shell | `/odoo` | Authenticated | Odoo backend, POS, reports, and module menus |
| Kiosk Display | `/tijara/display/tijara-demo-kiosk` | Public | Self-ordering kiosk route by display slug |
| Kiosk Checkout API | `/tijara/display/tijara-demo-kiosk/checkout` | Public JSON | Kiosk checkout payload submission |
| Menu Board | `/tijara/display/tijara-demo-menu-board` | Public | Menu display screen |
| Deals Board | `/tijara/display/tijara-demo-deals-board` | Public | Deals and promotions screen |
| Customer Display | `/tijara/display/tijara-demo-customer-display` | Public | Customer-facing live order display |
| Queue Display | `/tijara/display/tijara-demo-queue-display` | Public | Queue and pickup status display |
| Ecommerce Storefront | `/tijara/ecommerce/tijara-demo-web` | Public | Public online catalog and checkout route |
| Ecommerce Catalog API | `/tijara/ecommerce/tijara-demo-web/catalog` | Public JSON | B2C/B2B catalog, stock, Urdu/English product payload |
| Ecommerce Checkout API | `/tijara/ecommerce/tijara-demo-web/checkout` | Public JSON | Online checkout submission into Odoo sale orders |
| Ecommerce Tracking | `/tijara/ecommerce/tijara-demo-web/track` | Public | Customer pickup-code/mobile and private-token order tracking |
| Ecommerce Tracking API | `/tijara/ecommerce/tijara-demo-web/track/status` | Public JSON | Customer-safe order, queue, payment, and delivery tracking payload |
| Payment Webhook | `/tijara/saas/payment/webhook/generic` | Signed public | PSP webhook ingestion |

## Feature Inventory

- POS checkout with B2B and B2C pricing.
- Bill-level discount by amount or percentage with synchronized values.
- Refund and exchange workflows with invoice barcode scanning.
- Receipt and invoice template customization.
- CSV import and export for operational data.
- Hardware bridge for printers, scanners, drawers, scales, labels, and customer displays.
- Kiosk, menu, deals, promotion, queue, and customer-display routes.
- Ecommerce storefront, catalog API, checkout API, sale-order sync, pickup/
  delivery queue handoff, customer order tracking, dry-run delivery-provider
  assignment, and ecommerce analytics templates.
- Offline POS capture, replay, and conflict review.
- SaaS feature flags and runtime enforcement.
- Tenant provisioning and operations manifests.
- Subscription billing, webhooks, settlement reconciliation, dunning, and suspension.
- FBR adapter queue and readiness evidence.
- Inventory low-stock, expiry, rack, shelf, bin, and warehouse intelligence.
- Analytics dashboards, reports, trends, and daily KPI collectors.
- Back-office expenses, salary batches, loyalty, vertical retail mix, and
  cafe/restaurant charge-policy dashboards.
- Protected release evidence gates and production readiness reports.

## Demo Data

Run:

```bash
make seed-pos-demo
make seed-demo-users
```

The optional `tijara_demo_pos` module seeds POS config, an open POS session,
vertical demo products, B2B/B2C customers, loyalty records, display screens,
kiosk profile, queue ticket, promotion/deal records, ecommerce storefront
channel, published online products, invoice/receipt templates, back-office
expenses, and a salary batch. Demo users in
`docs/TEST_CREDENTIALS.csv` are deterministic staging accounts that can be
created or mapped with `make seed-demo-users` before authenticated browser E2E
runs.
