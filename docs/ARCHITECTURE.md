# Architecture

## Target

Tijara Suite is a Pakistan-first ERP/POS SaaS product built on Odoo Community.
The product should feel like a focused retail operating system, while retaining
Odoo's strength in accounting, inventory, sales, purchase, and extensibility.
The core suite is intended for a public community repository, so product
architecture must prefer open-source tools, Odoo Community extension points, and
redistributable assets.

## Diagram Pack

`docs/DIAGRAMS.md` is the canonical visual architecture pack. It contains the
deployment architecture, local development topology, system context, component
architecture, Odoo module map, data model UML, POS/ecommerce/restaurant user
flows, offline POS activity, hardware print sequence, tenant provisioning,
analytics pipeline, and release evidence flow diagrams.

Update that file whenever topology, module ownership, component boundaries,
UML, user journeys, activity flows, analytics movement, or DevOps release flow
changes.

## Tenancy Strategy

Preferred SaaS model: database per tenant.

Reasons:

- Stronger customer isolation.
- Easier backup, restore, export, and offboarding.
- Cleaner per-customer module enablement.
- Easier enterprise deployments for large customers.

The SaaS control module tracks tenant metadata, subscription plans, and feature
entitlements. Actual database provisioning should be performed by a platform
service in a later phase.

## Module Layers

1. `tijara_base`
   Pakistan localization foundation: company, partner, and product metadata.

2. `tijara_retail_core`
   Store operations: hardware registry, cash shifts, return/exchange workflow,
   invoice barcode return scanning, bulk import/export, retail product controls,
   and retail menus.

3. `tijara_inventory_intelligence`
   Low-stock alerts, critical-stock alerts, expiry alerts, warehouse placement,
   zones, aisles, racks, shelves, bins, and storage-position controls.

4. `tijara_pos_pk`
   Invoice/receipt template profiles, QR/barcode payloads, and FBR integration
   queue foundation. The module also owns the backend QWeb PDF/HTML reports for
   Tijara POS receipts and customer invoices.

5. `tijara_pos_experience`
   Self-service kiosk profiles, POS customer display, menu boards, deal boards,
   display content, promotions, queue tickets, and B2B/B2C POS configuration.

6. `tijara_analytics`
   Dashboard templates, dashboard widgets, KPI snapshot history, trend charts,
   pivot reporting, graph reporting, and report catalog.

7. `tijara_saas_control`
   Plans, features, subscriptions, and tenant metadata.

8. `tijara_ecommerce`
   Public storefront channels, online catalog publishing, B2B/B2C checkout,
   pickup/delivery queue handoff, customer order tracking, delivery-provider
   assignment, shipment create/cancel adapter events, label/manifest payloads,
   signed or dry-run delivery webhooks, and ecommerce analytics/report
   templates.

9. Vertical modules
   Pharmacy, restaurant, garments, electronics, and future industry packs.

## Analytics Strategy

The analytics layer stores KPI snapshots over time so the suite can provide
history, trends, charts, graphs, pivots, and manager dashboards without tying
every dashboard directly to transactional queries. The first dashboard catalog
covers owner overview, inventory control, POS performance, purchase/procurement,
and customer/promotion performance.

Future automated KPI collectors should read POS, sales, purchase, inventory,
refund/exchange, queue, promotion, and customer data into
`tijara.analytics.snapshot`.

## Inventory Intelligence Strategy

Odoo stock locations remain the source of truth for warehouse hierarchy.
Tijara adds practical store-floor metadata: zone, aisle, rack, shelf, bin,
barcode/QR, temperature zone, capacity, preferred product placement, low-stock
thresholds, critical-stock thresholds, expiry windows, and cycle-count frequency.

Inventory alerts are stored as records so managers can acknowledge, resolve,
analyze, and report on stock health over time.

## Hardware Strategy

Most scanners work as keyboard-wedge devices and require no backend driver.
Thermal receipt printing, label printing, cash drawer, customer displays, and
weighing scales need a local bridge. Tijara stores device type, connection type,
integration role, printer language, scanner mode, endpoint metadata, and test
results in the Odoo hardware registry.

The first bridge foundation lives in `hardware-bridge/`. It exposes signed local
HTTP endpoints, validates HMAC request signatures, records dry-run jobs to disk,
and lets Odoo hardware records run bridge health and signed test-job actions.
The browser POS receipt print action can now send the rendered receipt payload
through Odoo to a configured local bridge receipt printer, and POS orders store
the bridge job id, status, result JSON, and printed timestamp. The current
bridge includes adapter paths for ESC/POS receipt bytes, ZPL labels, CUPS/raw
TCP/file delivery, cash-drawer pulse bytes, scale readings, scanner event
persistence, and customer-display state output. These adapters are production
shaped but still require target-hardware certification before customer rollout.

The production architecture should include:

- Browser POS frontend.
- Local hardware bridge installed on the shop machine.
- Signed websocket or HTTP channel from browser to bridge.
- Device registry in Odoo.
- POS configuration assignment for the active bridge receipt printer.
- Fallback network printing where supported.

## Data Exchange Strategy

Bulk CSV import/export is modeled as an auditable Odoo operation. The first
supported data domains are products/prices, inventory quantities, contacts,
hardware devices, invoice/receipt templates, storage positions, and
promotions/deals.

The product goal is to keep import/export open and portable for community
deployments while adding stricter validation, row-level error reporting, and
automated tests as the suite moves toward pilot readiness.

## Template Rendering Strategy

Invoice and receipt customization is stored in `tijara.receipt.profile`. POS
orders select their default profile from `pos.config`; customer invoices can use
an invoice-specific override or fall back to the company profile for the
document scope.

Backend QWeb reports render the first template output for customer invoices and
POS order receipts. The live browser POS receipt now loads
`tijara.receipt.profile` records through the POS data loader and injects the
selected profile into Odoo's receipt component for titles, Urdu text, custom
body tokens, QR/barcode output, policy text, and footer content. When a local
bridge printer is assigned on the POS configuration, the browser print action
submits that rendered receipt payload to the bridge through an Odoo-signed
backend call. The remaining template architecture work is full thermal print
payload replacement and deeper control over the standard Odoo line, tax,
discount, and payment sections.

## Customer Experience Surfaces

The POS experience layer should support:

- Self-ordering kiosks.
- POS customer-facing displays.
- Menu boards.
- Promotions and deals boards.
- Queue/order-ready displays.
- B2B/B2C counter configuration and display pricing.

These are separate SaaS feature flags even though they share the
`tijara_pos_experience` technical module:

- `b2b_sales`
- `queue_system`
- `promotion_display`
- `customer_display`

These surfaces must be touch-first and cross-device. Shared responsive baseline
styles live in `tijara_pos_experience/static/src/scss/touch_responsive.scss`,
and the acceptance matrix is maintained in `docs/FRONTEND_DEVICE_QA.md`.
Public routes now serve these display surfaces:

- `/tijara/display/<slug>`
- `/tijara/display/<slug>/data`
- `/tijara/kiosk/<slug>`
- `/tijara/kiosk/<slug>/data`

## Configuration and Secrets

Tijara uses one centered non-secret config file and one centered secret file per
environment:

- `.env` for non-secret environment settings.
- `secrets/.env.secrets` for local/staging secrets.

Committed Odoo runtime configuration is a template at
`deploy/config/odoo.conf.template`. The actual Odoo config is rendered inside
the container by `deploy/bin/start-odoo.sh` using environment variables. For
production SaaS, these secrets should come from a managed secret store rather
than a plain env file.

## Open Source Architecture Rules

- Core ERP/POS behavior uses Odoo Community, not Odoo Enterprise.
- Infrastructure defaults use open-source tooling such as PostgreSQL, Nginx,
  Docker, Docker Compose, Python, JavaScript/OWL, XML, SCSS, and open-source
  test tooling.
- Proprietary services may only be optional adapters; they must not be required
  for community deployment of the core suite.
- Dependencies and assets must be checked for public redistribution and
  LGPL-3.0 compatibility before they are added.

## Compliance Strategy

FBR POS integration should be implemented as an adapter, not hardcoded into the
POS order flow. Orders enter a queue, are submitted to FBR, receive verification
data, and print the verification QR/code on the receipt. The system must handle
temporary connectivity failures without losing fiscal auditability.
