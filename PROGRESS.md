# Progress

## Iteration 1: Enterprise Product Scaffold

Status: Completed

Date: 2026-06-04

### Completed

- Created the Tijara Suite repository scaffold.
- Added Docker Compose development setup for Odoo and PostgreSQL.
- Added `tijara_base` for Pakistan localization foundations.
- Added `tijara_retail_core` for hardware devices, cash shifts, refunds, and
  exchanges.
- Added `tijara_pos_pk` for receipt profiles and FBR invoice queue foundation.
- Added `tijara_saas_control` for SaaS features, plans, and subscriptions.
- Added vertical module foundations for pharmacy, restaurant, garments, and
  electronics.
- Added Urdu translation scaffolds.
- Added architecture, roadmap, Pakistan localization, QA/security/devops, and
  MVP documentation.

### Validation

- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- XML files parse successfully.
- Docker Compose configuration validates.

### Known Gaps

- Odoo containers have not been started yet.
- Modules have not yet been installed into a live Odoo database.
- FBR integration is a queue/stub foundation, not a production adapter.
- Offline POS, hardware bridge, and subscription billing automation are not yet
  implemented.

### Next Iteration

- Start the Odoo stack.
- Install the base, retail, POS Pakistan, and SaaS modules.
- Fix any live Odoo module compatibility issues.
- Begin the retail MVP cashier workflow: receipt profile, refund/exchange stock
  behavior, and cash shift reporting.

## Iteration 2: Additional Retail Verticals

Status: Completed

Date: 2026-06-04

### Completed

- Added `tijara_vertical_cloth` for fabric rolls, meter/yard sales, cutting
  loss, and tailoring fields.
- Added `tijara_vertical_superstore` for department, aisle, shelf, case pack,
  promotion, loyalty, and fast-moving item fields.
- Added `tijara_vertical_grocery` for perishables, loose items, weigh-scale PLU,
  cold chain, shelf life, and freshness checks.
- Added `tijara_vertical_bakery` for bakery product metadata and production
  batch workflow.
- Added cloth, grocery, and bakery business types to company settings.
- Added SaaS feature records for the new vertical packs.
- Updated README, roadmap, and MVP scope documentation.

### Validation

- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 30 XML files parse successfully.
- Docker Compose configuration validates.
- 12 Odoo module manifests are present.

### Known Gaps

- New verticals are configuration/workflow foundations, not complete POS screens.
- Bakery batch workflow does not yet create stock moves or consume ingredients.
- Grocery price-embedded barcode parsing is not yet implemented.
- Cloth roll cutting does not yet reserve/decrement roll-level stock.

### Next Iteration

- Validate all new module files and XML.
- Start Odoo and perform live module install checks.
- Implement the first real retail MVP workflow against a running database.

## Iteration 3: POS Experience, Restaurant Service Modes, and B2B/B2C Pricing

Status: Completed

Date: 2026-06-04

### Completed

- Added `tijara_pos_experience` module for kiosk, POS customer display, menu
  boards, deals boards, display content, promotions/deals, and queue tickets.
- Added POS configuration fields for B2B/B2C enablement, kiosk enablement,
  queue enablement, customer display, menu board, deals board, and queue display.
- Added POS order fields for sale type, dine-in/takeaway/pickup order type,
  queue ticket, pickup code, and promised time.
- Added restaurant service profile for dine-in, takeaway, and pickup support.
- Added order type, pickup code, and promised time to restaurant kitchen tickets.
- Added separate product fields for B2C retail price and B2B trade price.
- Added POS Experience as a SaaS feature and included it in Retail, Vertical,
  and Enterprise plans.
- Updated README, architecture, roadmap, and MVP specification.

### Validation

- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 40 XML files parse successfully.
- Docker Compose configuration validates.
- 13 Odoo module manifests are present.

### Known Gaps

- Kiosk and display screen models are backend foundations; the browser display
  UI routes are not implemented yet.
- Product B2B/B2C fields are explicit item fields; full Odoo pricelist sync is
  still future work.
- Queue tickets are not yet automatically created from POS/kiosk orders.
- Restaurant service modes are modeled, but POS frontend buttons are not yet
  implemented.

### Next Iteration

- Validate all new module files and XML.
- Start the Odoo stack and install modules in a live database.
- Build the first POS frontend controls for B2B/B2C and dine-in/takeaway/pickup.

## Iteration 4: Separate SaaS Flags for POS Experience Features

Status: Completed

Date: 2026-06-04

### Completed

- Split B2B sales, queue system, promotion/deals display, and POS customer
  display into separate SaaS feature records.
- Kept `pos_experience` as the shared technical/core feature.
- Added the separate SaaS feature flags to Retail, Vertical, and Enterprise
  plans according to plan level.
- Added effective feature computation on subscriptions.
- Added `has_feature(feature_code)` helper for future enforcement logic.
- Updated README, architecture, and MVP documentation.

### Validation

- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 40 XML files parse successfully.
- Docker Compose configuration validates.
- 13 Odoo module manifests are present.

### Known Gaps

- The feature flags are modeled and visible in SaaS plans/subscriptions, but
  runtime enforcement in POS frontend controllers is not yet implemented.
- Display and queue browser routes are still future work.

### Next Iteration

- Validate all module files and XML.
- Start Odoo and install the modules in a live database.
- Add runtime feature checks to POS configuration and frontend flows.

## Iteration 5: Live Odoo 19 Install Smoke Test

Status: Completed

Date: 2026-06-04

### Completed

- Started the Docker Compose Odoo 19 and PostgreSQL stack.
- Installed all 13 Tijara custom modules into the live `tijara_dev` database.
- Fixed Odoo 19 security compatibility by using `res.groups.privilege` instead
  of legacy group categories.
- Fixed Odoo 19 product view inheritance by targeting the product template-only
  form and adding dedicated Tijara pages.
- Migrated custom backend view declarations from legacy `tree` to Odoo 19
  `list` views.
- Confirmed the SaaS feature catalog is seeded with 19 feature flags.
- Restarted the Odoo web service after successful module installation.
- Fixed the scaffold validator so it works from the project root.
- Added `make validate` as the local validation entry point.
- Updated README with the live install command and current status.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 40 XML files parse successfully.
- Docker Compose starts PostgreSQL and Odoo successfully.
- Live Odoo install command completed successfully.
- Database check confirms all 13 `tijara_*` modules are in `installed` state.
- Database check confirms 19 SaaS feature records.
- HTTP check confirms `http://localhost:8069` responds and redirects to `/odoo`.

### Known Gaps

- Runtime SaaS enforcement is not yet wired into POS actions and display flows.
- Kiosk, customer display, queue display, promotion display, menu display, and
  deals display still need browser routes and frontend screens.
- B2B/B2C price fields are modeled, but POS pricing selection still needs
  frontend behavior and pricelist integration.
- Restaurant dine-in, takeaway, and pickup are modeled, but POS controls and
  kitchen ticket automation still need implementation.
- Hardware bridge support for receipt printers, barcode scanners, QR, scales,
  and payment terminals is still foundation-level.

### Next Iteration

- Add runtime SaaS feature checks to POS configuration, display, queue, and
  kiosk workflows.
- Build the first POS frontend controls for B2B/B2C and dine-in/takeaway/pickup.
- Implement queue-ticket creation from POS/kiosk orders.
- Add basic browser routes for customer display, promotion display, menu/deals
  display, and kiosk.

## Iteration 6: DevOps Deployment Structure, Secrets, and Device QA Baseline

Status: Completed

Date: 2026-06-04

### Completed

- Added `DEPLOY.md` as the maintained deployment runbook.
- Split configuration into centered non-secret and secret templates:
  `.env.example` and `secrets/.env.secrets.example`.
- Updated `.gitignore` so actual env and secret files stay out of source
  control.
- Replaced committed `deploy/odoo.conf` with secret-free
  `deploy/config/odoo.conf.template`.
- Added `deploy/bin/start-odoo.sh` to render the Odoo runtime config from
  environment variables and secrets.
- Updated Docker Compose to use the runtime config renderer and require secret
  variables instead of using built-in password fallbacks.
- Added `make config` and `make install-suite` for easier DevOps operation.
- Hardened the nginx baseline for proxy headers, long-polling/websocket traffic,
  upload size, and basic response security headers.
- Added `docs/FRONTEND_DEVICE_QA.md` for touch, device, viewport, browser, Urdu,
  POS, kiosk, customer display, queue display, promotion display, and menu
  display acceptance.
- Added `tijara_pos_experience/static/src/scss/touch_responsive.scss` and wired
  it into backend, POS, and customer display asset bundles.
- Updated README, architecture, QA/security/devops, and PostgreSQL operations
  docs.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 40 XML files parse successfully.
- `docker compose --env-file .env.example --env-file secrets/.env.secrets.example config`
  validates the updated Compose structure.
- `bash -n deploy/bin/start-odoo.sh` passes.
- Compose can inspect the existing running Odoo/PostgreSQL stack with the
  centralized env-file pattern.

### Known Gaps

- Actual `.env` and `secrets/.env.secrets` files must be created per environment
  before starting a fresh deployment.
- Production should use a managed secret store instead of plain env files.
- The touch/responsive stylesheet is a baseline; kiosk, customer display, queue,
  promotion/menu/deal display, and POS frontend screens still need to be built
  and browser-tested.
- Automated cross-browser Playwright tests are documented but not implemented
  yet.

### Next Iteration

- Add runtime SaaS feature checks to POS, queue, display, and kiosk flows.
- Build browser routes/controllers for kiosk, customer display, queue display,
  promotion display, and menu/deals display.
- Start Playwright smoke tests for the documented viewport and browser matrix.
- Add POS frontend controls for B2B/B2C and dine-in/takeaway/pickup.

## Iteration 7: Inventory Intelligence, Dashboards, Reporting, and Analytics

Status: Completed

Date: 2026-06-04

### Completed

- Added `tijara_inventory_intelligence` module.
- Added storage-position model for warehouse, location, zone, aisle, rack,
  shelf, bin, barcode/QR, capacity, and temperature zone.
- Added physical placement fields to Odoo stock locations.
- Added product-level preferred storage position, critical stock quantity,
  expiry alert days, cycle-count frequency, temperature-control flag, and
  storage notes.
- Added inventory alert workbench for low stock, critical stock, expiry,
  overstock, misplaced stock, and dead stock.
- Added scheduled inventory alert scan foundation.
- Added list, form, graph, and pivot views for inventory alerts.
- Added `tijara_analytics` module.
- Added dashboard definitions, dashboard widgets, KPI snapshot history, graph
  and pivot views, and report catalog.
- Seeded five dashboard templates and four report catalog templates.
- Added SaaS features `inventory_intelligence` and `analytics_reporting`.
- Updated default SaaS plan templates:
  Retail gets inventory intelligence.
  Vertical gets inventory intelligence and analytics/reporting.
  Enterprise gets inventory intelligence and analytics/reporting.
- Updated `make install-suite` to include the two new modules.
- Added `docs/INVENTORY_INTELLIGENCE.md` and `docs/ANALYTICS_REPORTING.md`.
- Updated README, architecture, roadmap, MVP spec, and progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 51 XML files parse successfully.
- Live Odoo install/upgrade completed for `tijara_inventory_intelligence` and
  `tijara_analytics`.
- Live Odoo upgrade completed for `tijara_saas_control`.
- Database check confirms 15 installed `tijara_*` modules.
- Database check confirms 21 SaaS feature records.
- Database check confirms the two new modules are installed.
- Database check confirms Retail, Vertical, and Enterprise plan entitlements for
  inventory intelligence and analytics/reporting.

### Known Gaps

- KPI snapshots are modeled, but automated KPI collectors from POS, sale,
  purchase, stock, queue, promotion, refund, exchange, and cash-shift data are
  not yet implemented.
- Inventory alert scanning currently covers low stock, critical stock, and
  expiry foundations; overstock, misplaced stock, dead stock, FEFO planning, and
  reorder suggestions are future automation.
- Storage positions exist as master data; mobile shelf audit and scan-to-place
  workflows are not yet implemented.
- Dashboard templates and report catalog records are backend foundations; rich
  role-specific dashboard UI still needs to be built.

### Next Iteration

- Implement automated KPI snapshot collectors for sales/POS, purchase,
  inventory, refunds/exchanges, queue, and promotion data.
- Add reorder suggestion generation from low-stock and critical-stock alerts.
- Build dashboard UI surfaces for owner, inventory manager, cashier manager, and
  purchase manager.
- Add shelf/rack/bin audit workflow and barcode/QR lookup for storage positions.

## Iteration 8: Overall POS Bill Discount

Status: Completed

Date: 2026-06-04

### Completed

- Added Odoo `pos_discount` as the proven discount engine dependency for
  Tijara POS Experience.
- Added POS configuration controls for enabling overall bill discounts, default
  entry mode, maximum discount percentage, and future manager approval.
- Added POS order audit fields for bill discount mode, bill base, percentage,
  amount, and net bill amount.
- Added backend POS order and POS configuration views for the new bill discount
  fields.
- Added a touch-friendly POS popup where cashiers can enter either discount
  percentage or discount amount.
- Implemented two-way calculation so changing percentage recalculates amount,
  and changing amount recalculates percentage.
- Preserved fixed-amount behavior when order lines change by recalculating the
  required Odoo global discount percentage from the desired amount.
- Synced enabled Tijara bill discounts with Odoo `module_pos_discount`,
  `iface_discount`, and discount product setup for existing and future POS
  configurations.
- Updated README, MVP specification, roadmap, analytics reporting notes, and
  progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 53 XML files parse successfully.
- POS bill discount JavaScript files pass `node --check`.
- Live Odoo upgrade completed for `tijara_pos_experience`.
- Database check confirms `pos_discount` and `tijara_pos_experience` are
  installed.
- Database check confirms nine `tijara_bill_discount_*` fields exist across
  `pos.config` and `pos.order`.
- HTTP check confirms `http://localhost:8069/odoo` responds and redirects to
  login.

### Known Gaps

- Full browser POS cashier testing is still pending because this dev database
  currently has no POS configuration/session data.
- Existing sync hooks are ready for POS configurations when they are created.
- Manager approval is a configuration foundation flag; runtime approval
  enforcement still needs to be implemented.
- Amount mode uses Odoo's global discount line by converting the entered amount
  to the matching percentage for the current bill base.

### Next Iteration

- Create seeded POS config/session/product demo data for browser smoke tests.
- Add runtime manager approval checks for high bill discounts.
- Add discount KPIs to automated POS analytics snapshot collectors.
- Continue POS frontend controls for B2B/B2C and dine-in/takeaway/pickup.

## Iteration 9: Public Open-Source Governance

Status: Completed

Date: 2026-06-04

### Completed

- Added root `LICENSE` notice for LGPL-3.0.
- Added `docs/OPEN_SOURCE_POLICY.md` for public repository and community
  governance.
- Documented that core behavior must use Odoo Community and open-source tools.
- Documented that Odoo Enterprise modules, proprietary dependencies, private
  assets, and vendor-locked services are not allowed in the core suite.
- Added a dependency intake checklist for future open-source compatibility
  reviews.
- Updated README and architecture documentation with open-source-first rules.

### Validation

- Confirmed all current Tijara Odoo addon manifests declare `LGPL-3`.
- `make validate` passes from the project root.
- 53 XML files parse successfully.

### Known Gaps

- A full third-party dependency license inventory file should be generated once
  frontend/package dependencies are added.
- Community contribution workflow, code of conduct, and issue templates are not
  created yet.

### Next Iteration

- Add `CONTRIBUTING.md`, public issue templates, and contributor setup notes.
- Add dependency/license inventory automation when Node/Python package manifests
  are introduced.
- Continue seeded POS demo data and browser smoke tests.

## Iteration 10: POS Demo Seed and Cashier Controls

Status: Completed

Date: 2026-06-04

### Completed

- Added optional `tijara_demo_pos` module for public-repo safe POS cashier demo
  data.
- Seeded reusable demo products with barcodes, B2C/B2B prices, stock quantities,
  Urdu names, and POS availability.
- Seeded demo B2C walk-in and B2B wholesale customers.
- Seeded demo POS configuration, display screens, kiosk profile, promotion, and
  queue ticket.
- Added automatic demo POS session creation when no open session exists for the
  seeded POS config.
- Added `make seed-pos-demo` as the optional dev/test seeding entry point.
- Added `docs/POS_DEMO_SEED.md` with seed instructions and cashier smoke path.
- Added POS action-menu controls for B2B/B2C sale type and
  dine-in/takeaway/pickup service mode.
- Added POS order serialization and loading support for Tijara sale type,
  service mode, pickup code, promised time, and bill discount audit fields.
- Added POS product loading support for Tijara B2C/B2B price fields.
- Added current-ticket repricing when the cashier switches B2B/B2C.
- Added runtime manager guard for bill discounts when manager approval is
  enabled on the POS config.
- Updated README, MVP specification, roadmap, and progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 55 XML files parse successfully.
- POS bill discount and order option JavaScript files pass `node --check`.
- Live Odoo upgrade/install completed for `tijara_pos_experience` and
  `tijara_demo_pos`.
- Database checks confirm the demo module, POS config, products, customers,
  display screens, queue ticket, and open demo POS session exist.
- Database check confirms seeded stock quantities for all four demo products.
- Odoo service was recreated with the current compose config after an old
  container mount expected the removed `deploy/odoo.conf` file; the service is
  back up and `/odoo` redirects to login.

### Known Gaps

- Full browser click-through smoke testing still needs authenticated POS UI
  execution.
- B2B/B2C repricing currently updates existing ticket lines; automatic pricing
  at the exact product-add event needs a deeper POS add-line hook.
- Manager approval is enforced as a runtime manager-only guard; PIN-based
  escalation/temporary approval is still future work.
- Refund/exchange browser flow is not yet automated.

### Next Iteration

- Run authenticated browser smoke for the seeded POS cashier path.
- Add automatic B2B/B2C pricing at product-add time.
- Add queue ticket creation from completed POS/kiosk orders.
- Automate refund/exchange POS smoke coverage.

## Iteration 11: Invoice Templates, Return Scan, Hardware, and Bulk Data

Status: Completed

Date: 2026-06-04

### Completed

- Expanded invoice and receipt templates with scope, layout, language, printer
  width, custom dimensions, printer device assignment, barcode source, display
  flags, English/Urdu content, custom HTML, custom CSS, and internal notes.
- Added `tijara_invoice_barcode` on POS orders for future receipt/return barcode
  workflows.
- Added invoice barcode/QR scanning on refund/exchange requests with support
  for `TJINV:`, `POS:`, `INV:`, and `FBR:` scan prefixes.
- Added matched POS order, matched customer invoice, scanner device, scan
  status, and scan result tracking on refund/exchange requests.
- Added automatic return-line population from matched POS orders or customer
  invoices.
- Expanded hardware device configuration for scanner/printer/customer-display
  integration roles, connection status, printer language, scanner mode, bridge
  endpoint, paper width, DPI, barcode/QR support, CUPS, and keyboard-wedge
  scanners.
- Added hardware Test Configuration and Mark Offline actions.
- Added `tijara.bulk.data.operation` for CSV import/export operations.
- Added CSV import/export support for products/prices, inventory quantities,
  contacts, hardware devices, invoice/receipt templates, storage positions, and
  promotions/deals.
- Added safer import validation for required CSV identifiers and optional-module
  fields.
- Added `docs/RETAIL_OPERATIONS_DATA.md` for invoice templates, return scan,
  hardware registry, CSV rules, and deployment notes.
- Updated README, MVP specification, roadmap, architecture, deployment, QA, and
  progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 56 XML files parse successfully.
- Live Odoo upgrade completed for `tijara_retail_core`, `tijara_pos_pk`, and
  `tijara_pos_experience`.
- Database checks confirm `tijara.bulk.data.operation` and the new invoice,
  scanner/printer, return-scan, and POS barcode fields are registered.
- Odoo shell smoke confirms product CSV export creates a downloadable result.
- Odoo shell smoke confirms product CSV import creates a B2B/B2C-priced product.
- Odoo shell smoke confirms inventory CSV import sets stock quantity and
  inventory CSV export creates a downloadable result.
- Odoo shell smoke confirms hardware device CSV import creates scanner metadata.
- Odoo shell smoke confirms receipt-template CSV schema export works.
- Odoo shell smoke confirms hardware Test Configuration marks a scanner ready.
- Odoo shell smoke confirms a custom customer-invoice template can be saved with
  printer assignment, custom HTML, and custom CSS.
- Odoo shell smoke confirms return scan handles both not-found and matched
  customer-invoice paths.

### Known Gaps

- At the end of Iteration 11, custom invoice/receipt template settings were
  stored and import/exportable, but rendering was still pending. Backend QWeb
  report rendering was completed in Iteration 12.
- Hardware bridge runtime drivers for ESC/POS, ZPL, CUPS, cash drawers, scales,
  and customer displays are not implemented yet.
- CSV import/export has core operational coverage, but row-level error files,
  validation previews, scheduled exports, and every vertical-specific field are
  future work.
- Return scanning was smoke-tested through Odoo shell; an authenticated browser
  cashier flow still needs automated coverage.

### Next Iteration

- Completed in Iteration 12: render configured invoice/receipt templates into
  backend POS/customer-invoice report output.
- Build the open-source local hardware bridge foundation for printer, scanner,
  cash drawer, scale, and customer-display runtime integration.
- Add browser tests for refund/exchange invoice scanning and bulk import/export
  forms.
- Extend import/export coverage to deeper vertical-specific fields and add
  row-level validation reports.

## Iteration 12: Backend Invoice and Receipt Template Rendering

Status: Completed

Date: 2026-06-04

### Completed

- Added default Tijara receipt template selection on POS configurations.
- Added optional Tijara invoice template override on customer invoices and
  credit notes.
- Added stored `tijara_invoice_barcode` on customer invoices for consistent
  invoice barcode/QR return scanning.
- Extended refund/exchange invoice scanning to match customer invoices by
  `tijara_invoice_barcode`.
- Added backend QWeb PDF/HTML report action for Tijara POS receipts.
- Added backend QWeb PDF/HTML report action for Tijara customer invoices.
- Added `Tijara Receipt` button on POS orders.
- Added `Tijara Invoice` button on customer invoices and credit notes.
- Rendered template profile settings into reports, including titles, logo,
  company NTN/STRN, English/Urdu header/footer/terms, customer, cashier, line
  table, discount column, tax, totals, payment summary, barcode, QR, custom
  HTML, and custom CSS.
- Added escaped custom HTML tokens for document number, date, customer, cashier,
  company, totals, tax, barcode value, and POS FBR invoice number.
- Updated README, retail operations guide, MVP specification, roadmap,
  architecture, and progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 59 XML files parse successfully.
- Live Odoo upgrade completed for `tijara_pos_pk` and `tijara_retail_core`.
- Database checks confirm new `account.move`, `pos.config`, and report action
  records are registered.
- Odoo shell smoke confirms Tijara customer invoice HTML rendering includes the
  configured custom HTML token output.
- Odoo shell smoke confirms Tijara POS receipt HTML rendering includes the
  configured receipt title.
- Odoo shell smoke confirms Tijara customer invoice and POS receipt QWeb PDF
  reports generate valid PDF bytes.
- Odoo shell smoke confirms refund/exchange scan can match a customer invoice
  by the generated `tijara_invoice_barcode`.
- HTTP check confirms `http://localhost:8069/odoo` still redirects to login.

### Known Gaps

- The live browser POS receipt screen and immediate thermal print payload still
  need to consume Tijara template profiles.
- PDF generation succeeds, but the dev database has a missing company logo
  filestore attachment warning that should be cleaned up in test data.
- Hardware bridge runtime drivers for ESC/POS, ZPL, CUPS, cash drawers, scales,
  and customer displays are still future work.
- Browser-authenticated tests for the new report buttons are not implemented
  yet.

### Next Iteration

- Override the browser POS receipt/print payload to use Tijara receipt profiles.
- Start the open-source local hardware bridge foundation.
- Add browser tests for the Tijara Invoice and Tijara Receipt buttons.
- Add row-level validation result files for bulk import/export.

## Iteration 13: Browser POS Receipt Profile Runtime

Status: Completed

Date: 2026-06-04

### Completed

- Added POS data loading for `tijara.receipt.profile` so browser POS sessions
  receive active POS receipt templates for the current company.
- Added POS user and POS manager read access for receipt profiles.
- Added POS company field loading for Tijara NTN, STRN, branch code, and FBR POS
  identifier so receipts can show Pakistan fiscal metadata.
- Added a browser POS model class for Tijara receipt profiles.
- Patched the live Odoo POS receipt component to inject the selected Tijara POS
  receipt profile into the receipt screen.
- Rendered configured English/Urdu title, header, footer, return policy, custom
  body HTML tokens, barcode value, QR value, customer, B2B/B2C sale type, and
  restaurant service mode on the browser POS receipt screen.
- Extended loaded POS order fields with Tijara invoice barcode, FBR QR payload,
  refund/exchange markers, and the core draft-order fields needed by Odoo POS
  device synchronization.
- Fixed browser POS boot regressions caused by draft-order loader fields missing
  `partner_id`, `lines`, `payment_ids`, and `write_date`.
- Updated README, MVP specification, retail operations guide, roadmap,
  architecture, deployment notes, frontend QA, and progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 60 XML files parse successfully.
- `node --check` passes for the new POS receipt profile model JS.
- `node --check` passes for the POS receipt runtime patch JS.
- Live Odoo upgrade completed for `tijara_pos_pk`.
- Odoo shell smoke confirms `tijara.receipt.profile` is present in the POS model
  load list.
- Odoo shell smoke confirms the assigned POS receipt profile is loaded into POS
  boot data.
- Odoo shell smoke confirms POS order barcode/FBR fields and company NTN fields
  are exposed to the POS loader.
- Full POS load-data smoke confirms `pos.config`, `pos.order`, `res.company`,
  and `tijara.receipt.profile` records load together.
- HTTP JSON-RPC smoke confirms draft POS orders include `partner_id`, `lines`,
  `payment_ids`, `write_date`, and Tijara barcode/FBR fields.
- Authenticated in-app browser smoke reaches the live POS product screen.
- Authenticated in-app browser smoke opens the register, adds a cash payment,
  validates the demo order, and reaches the receipt screen.
- Browser receipt text confirms the Tijara profile rendered `Tijara Runtime
  Receipt`, Urdu title text, custom token output, sale type, service mode,
  barcode value, return policy, and footer content.

### Known Gaps

- This is a first-pass receipt component extension; it does not fully replace
  Odoo's thermal print payload or every standard line, tax, discount, and
  payment layout section yet.
- Browser screenshot capture timed out during this run, although the browser DOM
  text confirmed receipt rendering.
- Hardware bridge runtime drivers for ESC/POS, ZPL, CUPS, cash drawers, scales,
  and customer displays are still future work.
- Browser-authenticated tests for backend Tijara Invoice/Tijara Receipt buttons
  are not implemented yet.
- Bulk import/export row-level validation result files are still pending.

### Next Iteration

- Start the open-source local hardware bridge foundation for ESC/POS, ZPL, CUPS,
  scanner, cash drawer, scale, and customer-display runtime integration.
- Add browser tests for backend Tijara Invoice and Tijara Receipt buttons.
- Add deeper receipt template controls for line, tax, discount, payment, and
  fiscal sections.
- Add row-level validation result files and preview flows for bulk import/export.

## Iteration 14: Local Hardware Bridge Foundation

Status: Completed

Date: 2026-06-04

### Completed

- Added `hardware-bridge/`, an open-source local shop-machine bridge service
  built with Python standard-library HTTP handling.
- Added bridge endpoints for health, generic test, receipt print, label print,
  cash-drawer open, customer display, scale read, and scanner event dry-run
  jobs.
- Added HMAC request signing with `X-Tijara-Timestamp` and
  `X-Tijara-Signature` headers for all bridge POST requests.
- Added dry-run job persistence so signed bridge jobs are written as JSON files
  until physical driver adapters are implemented.
- Added example bridge device configuration for receipt printer, label printer,
  cash drawer, scale, and customer display.
- Added a bridge Dockerfile and optional Docker Compose `hardware` profile.
- Added Makefile targets for `bridge-up`, `bridge-logs`, and `bridge-ps`.
- Added centralized non-secret bridge config to `.env.example`.
- Added centralized bridge shared secret placeholder to
  `secrets/.env.secrets.example`.
- Passed `TIJARA_BRIDGE_SHARED_SECRET` and bridge timeout into the Odoo service
  environment for runtime bridge calls.
- Added Odoo Hardware Device actions for `Bridge Health` and `Send Bridge Test
  Job`.
- Added Odoo-side signed bridge client helpers using standard Python
  `urllib`, `hmac`, and `hashlib`.
- Added bridge result tracking fields for last bridge job id, operation, and
  HTTP status.
- Updated README, MVP specification, roadmap, architecture, retail operations,
  deployment, frontend QA, and progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 60 XML files parse successfully.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- Local bridge server starts on `127.0.0.1:19109` with the example device
  configuration.
- Bridge `GET /health` smoke returns HTTP 200 with five configured devices and
  declared capabilities.
- Signed `POST /v1/print/receipt` smoke returns HTTP 202 and writes an accepted
  dry-run receipt job.
- Live Odoo upgrade completed for `tijara_retail_core`.
- Odoo shell smoke creates/updates a browser-bridge receipt printer device.
- Odoo shell smoke confirms `Bridge Health` records HTTP 200 and ready status.
- Odoo shell smoke confirms `Send Bridge Test Job` records HTTP 202, operation
  `print_receipt`, and a bridge job id.
- Odoo HTTP service restarted after module upgrade.

### Known Gaps

- The bridge currently records dry-run jobs only; real ESC/POS, ZPL, CUPS,
  serial scale, cash-drawer, scanner-event, and customer-display drivers are
  future work.
- The browser POS receipt print action is not yet wired to submit the live
  receipt payload to the bridge.
- Bridge websocket/event streaming for scanners and customer displays is not
  implemented yet.
- Production device hardening still needs per-store network binding rules,
  service install scripts, retry queues, and observability.

### Next Iteration

- Wire the browser POS receipt print flow to submit the rendered Tijara receipt
  payload to the local bridge for receipt-printer devices.
- Add first real driver adapters in priority order: ESC/POS dry-run-to-bytes,
  CUPS print submission, ZPL label output, and cash-drawer pulse command.
- Add browser tests for backend Tijara Invoice and Tijara Receipt buttons.
- Add row-level validation result files and preview flows for bulk import/export.

## Iteration 15: POS Receipt Print-to-Bridge Flow

Status: Completed

Date: 2026-06-04

### Completed

- Added the first bridge driver adapter for receipt dry-runs: rendered receipt
  text can now be converted into ESC/POS bytes and stored as base64 in the bridge
  job file for audit/testing.
- Extended bridge responses with driver output format and byte count when the
  ESC/POS dry-run adapter is used.
- Added a reusable Odoo hardware-device submission helper so application flows
  can send signed bridge jobs with custom payloads, not only generic device test
  payloads.
- Added a POS configuration field for selecting the local bridge receipt printer
  used by browser POS receipt printing.
- Exposed the new POS receipt printer field through the POS config data loader.
- Added POS order bridge print audit fields for job id, status, result JSON, and
  printed timestamp.
- Added `action_tijara_print_receipt_to_bridge` on POS orders. It selects the
  configured bridge receipt printer, enriches the rendered receipt payload with
  order/config/profile/company/totals/barcode metadata, signs the bridge job, and
  records the result.
- Patched the browser POS receipt print flow so, when a bridge receipt printer is
  configured, the print action submits the rendered receipt HTML/text payload to
  Odoo and then to the local bridge.
- Updated README, deployment guide, hardware bridge guide, architecture, MVP,
  roadmap, retail operations, frontend QA, and progress documentation.

### Validation

- `make validate` passes from the project root.
- Python module files compile with `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache`.
- 60 XML files parse successfully.
- `node --check` passes for the POS receipt bridge print patch.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- Live Odoo upgrade completed for `tijara_retail_core` and `tijara_pos_pk`.
- Odoo HTTP service restarted after module upgrade.
- Local bridge server starts on `127.0.0.1:19109` with the example device
  configuration.
- Bridge `GET /health` smoke returns HTTP 200 with five configured devices.
- Signed `POST /v1/print/receipt` smoke returns HTTP 202 and includes
  `driver_output_format` as `escpos_base64`.
- Odoo shell smoke configures the demo receipt printer, assigns it to POS
  configuration, and confirms the POS loader includes
  `tijara_receipt_printer_device_id`.
- Odoo shell smoke submits a POS order receipt print job to the bridge and
  confirms successful status, matching bridge job id, accepted POS order audit
  status, and ESC/POS output metadata in the stored result JSON.
- In-app browser smoke confirms the restarted Odoo web UI renders the login
  screen at `http://127.0.0.1:8069/odoo`.

### Known Gaps

- The current ESC/POS output is a dry-run bytes adapter for validation and audit;
  production printer submission still needs tested hardware drivers.
- The browser print hook has backend and JS syntax validation plus Odoo-side
  bridge smoke coverage, but a full authenticated browser click-through from
  checkout receipt screen to bridge job still needs stable automation coverage.
- ZPL, CUPS, cash-drawer pulse, serial/network scale, scanner-event streaming,
  and customer-display runtime adapters are still future work.
- Full thermal receipt payload replacement and advanced control over line, tax,
  discount, payment, and fiscal sections are still pending.

### Next Iteration

- Add browser-authenticated coverage for clicking POS receipt print and
  verifying the resulting bridge job from the browser checkout screen.
- Add the next production-facing hardware adapters in priority order: CUPS print
  submission, ZPL label output, cash-drawer pulse command, and customer-display
  update route.
- Add row-level validation result files and preview flows for bulk import/export.
- Add browser tests for backend Tijara Invoice and Tijara Receipt buttons.

## Iteration 16: Enterprise Runtime Foundations

Status: Completed

Date: 2026-06-04

### Completed

- Expanded the hardware bridge driver layer beyond ESC/POS dry-run bytes.
- Added adapter foundations for ESC/POS receipt bytes, ZPL label bytes,
  CUPS/raw TCP/file delivery, ESC/POS cash-drawer pulse bytes, scale readings,
  scanner-event JSON persistence, and customer-display JSON output.
- Extended bridge capabilities and job responses with driver transport/status
  details.
- Added central bridge output directory configuration and an output volume for
  Docker Compose hardware deployments.
- Added SaaS enforcement helpers on companies, controlled by
  `TIJARA_SAAS_ENFORCEMENT_ENABLED` or the
  `tijara.saas.enforcement_enabled` system parameter.
- Added POS configuration entitlement checks for B2B sales, queue system,
  promotion/menu/deals display, customer display, and kiosk core access.
- Added tenant provisioning request/admin console foundation for SaaS operators.
- Added subscription usage/limit status and a manual plan-limit check action.
- Replaced the FBR queue stub with dry-run/live HTTP adapter submission,
  endpoint/secret configuration, response mapping, POS order update, and a
  disabled-by-default FBR submission cron.
- Added public display/kiosk routes and JSON endpoints for menu, deals,
  promotion, customer display, kiosk, and queue display screens.
- Added the first daily analytics KPI collector for POS revenue/orders/basket
  size/refunds, inventory alert counts, queue wait time, and active promotions.
- Added a disabled-by-default analytics collection cron and a manual
  `Collect Daily Snapshots` server action.
- Added GitHub Actions CI baseline, JavaScript syntax check script, security
  audit script, PostgreSQL backup script, k6 load-smoke script, and Makefile
  targets for the new operations.
- Added Nginx rate limiting for login, database, JSON-RPC, display, and kiosk
  paths.
- Updated README, deployment guide, hardware bridge guide, architecture, MVP,
  roadmap, retail operations, analytics, QA/security/devops, and progress docs.

### Validation

- `make validate` passes from the project root and now compiles both addons and
  the hardware bridge package.
- 63 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- Live Odoo upgrade completed for `tijara_retail_core`, `tijara_saas_control`,
  `tijara_pos_experience`, `tijara_pos_pk`, and `tijara_analytics`.
- Odoo HTTP service restarted after module upgrade.
- Odoo shell smoke confirms SaaS enforcement blocks B2B on Starter plan and
  allows B2B/queue/customer display on Enterprise plan.
- Odoo shell smoke confirms subscription limit check reports `ok`.
- Odoo shell smoke confirms tenant provisioning request reaches `provisioned`.
- Odoo shell smoke confirms FBR dry-run adapter submits and generates a
  `DRY-FBR-*` invoice number.
- Odoo shell smoke confirms display and queue records can be seeded.
- Odoo shell smoke confirms daily analytics collection creates KPI snapshots.
- Bridge driver smoke confirms ESC/POS receipt file output, ZPL label file
  output, cash-drawer pulse file output, customer-display JSON file output, and
  scale dry-run reading.
- HTTP smoke confirms `/tijara/display/smoke-menu` returns 200 and
  `/tijara/display/smoke-menu/data` returns configured content and promotions.
- In-app browser smoke confirms the display screen renders `Smoke Menu`,
  `Smoke Deal`, `PKR 250`, and promotion content.

### Known Gaps

- Hardware adapters are production-shaped but not target-hardware certified.
- CUPS, raw TCP, serial scale, cash drawer, and customer-display behavior still
  need physical device QA and per-model support notes.
- Tenant provisioning has an admin console but does not yet create databases,
  install modules, or configure DNS/backups automatically.
- Subscription billing/payment automation is still pending.
- FBR live mode is adapter-ready, but certified provider/API credentials and
  production compliance validation are still pending.
- Display/kiosk routes show configured content, promotions, and queue data; full
  self-ordering kiosk checkout is still pending.
- CI is a baseline; full browser E2E, Odoo transaction tests, load tests,
  dependency/container scanning, and security regression suites still need
  expansion.

### Next Iteration

- Add real Odoo transaction tests for SaaS enforcement, FBR dry-run submission,
  analytics collection, and display-route payloads.
- Add browser-authenticated POS checkout print-to-bridge automation and backend
  report-button browser tests.
- Add tenant database provisioning automation script/runbook and subscription
  invoice generation foundation.
- Add physical-device certification profiles for target ESC/POS, ZPL, CUPS,
  cash drawer, customer display, and scale models.
- Expand display/kiosk routes toward real self-service ordering and
  customer-display live order state.

## Iteration 17: Production Readiness QA and Operations

Status: Completed

Date: 2026-06-04

### Completed

- Added committed Odoo post-install tests for:
  - SaaS enforcement enabled/disabled behavior.
  - Starter-plan blocking and Enterprise-plan allowing B2B, queue, and customer
    display features.
  - Tenant provisioning request state flow into active subscription state.
  - FBR dry-run submission, invoice number, QR payload, and response storage.
  - FBR live-mode guard behavior when endpoint/credentials are missing.
  - Daily analytics collector snapshot generation.
  - Display controller entitlement checks and public payload assembly.
- Added `scripts/run_odoo_tests.sh` and `make test-odoo` for repeatable Odoo
  transaction/HTTP-style testing.
- Added Playwright browser E2E scaffolds under `tests/e2e/` for public
  display/kiosk routes and staging-gated authenticated POS checkout,
  refund/exchange, and report smoke tests.
- Added `package.json`, `playwright.config.mjs`, and extended JS syntax checks
  to include E2E `.mjs` files.
- Added tenant database provisioning automation with
  `scripts/provision_tenant_db.sh` and `make provision-tenant`.
- Added SaaS subscription billing foundation:
  - `account` dependency for invoice generation.
  - Billing cycle, amount override, billing product, last invoice, payment
    provider/status, external reference, paid timestamp, and invoice count.
  - Draft customer invoice generation from subscription plans.
  - Billing-status sync and external-payment recording actions.
- Added FBR live adapter hardening:
  - Provider field, client ID, idempotency key, submission attempts,
    last-request timestamp, and response status.
  - HTTPS-only live endpoint guard by default.
  - Client/idempotency headers and response invoice-number validation.
  - Failed submissions now persist failed state and error message instead of
    being rolled back by a raised UI exception.
- Added hardware certification profiles and `make hardware-cert-smoke` for
  ESC/POS receipt/cash drawer, ZPL labels, scanner event, scale reading, and
  customer display dry-run validation.
- Added restore-drill automation with `deploy/postgres/restore-drill.sh` and
  `make restore-drill`.
- Added Prometheus and Blackbox Exporter monitoring profile/config plus
  `make monitoring-up` and `make monitoring-logs`.
- Added logging guidance in `deploy/logging/README.md`.
- Added Trivy/npm/pip-audit hooks with `make container-scan` and
  `make dependency-scan`.
- Updated `README.md`, `DEPLOY.md`, `docs/QA_SECURITY_DEVOPS.md`,
  `docs/ROADMAP.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 64 XML files parse successfully.
- `bash scripts/js_check.sh` passes, including the new Playwright `.mjs` files.
- `bash scripts/security_audit.sh` passes before Odoo test execution and again
  after generated cache cleanup.
- `python3 scripts/hardware_certification_smoke.py` passes all dry-run hardware
  certification profiles.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- Odoo test runner passed on isolated database `tijara_test_iter17e`:
  - 8 post-install tests.
  - 0 failures.
  - 0 errors.
  - Covered `tijara_saas_control`, `tijara_pos_pk`, `tijara_analytics`, and
    `tijara_pos_experience`.
- Odoo tests generated Python cache artifacts in mounted addons; generated
  `__pycache__` folders were removed after the run.
- Final cleanup check confirms no `__pycache__` folders and no `.pyc` files
  remain under `outputs/tijara-suite`.

### Known Gaps

- Playwright E2E tests are committed but authenticated POS/refund/report flows
  still require staging credentials, POS config IDs, and route URLs to run.
- Physical hardware is still not certified; the new certification profiles are
  dry-run and must be repeated on real printer, cash drawer, scanner, scale,
  label printer, and customer-display models.
- Tenant provisioning now creates/updates tenant databases through an operator
  script, but DNS, ingress, tenant admin setup, backup policy assignment,
  monitoring labels, and post-provision smoke tests are not fully automated.
- Subscription billing creates draft Odoo invoices and tracks external payment
  state, but production provider webhooks, reconciliation, dunning, tax policy,
  and suspension automation are still pending.
- FBR live mode is hardened, but certified provider credentials, exact payload
  mapping, sandbox certification, and production compliance validation are still
  pending.
- Monitoring is a baseline availability profile; PostgreSQL exporter, Odoo
  business metrics, Alertmanager routing, dashboards, and incident automation
  still need production setup.
- Offline POS and full self-service kiosk ordering checkout are still pending.

### Next Iteration

- Run Playwright E2E against the live dev/staging Odoo instance with seeded POS
  config IDs and display slugs.
- Build real kiosk self-ordering checkout flow and customer-display live order
  state.
- Add physical hardware certification evidence capture per supported device
  model.
- Automate tenant DNS/ingress, admin user creation, backup policy, monitoring
  labels, and post-provision smoke tests around `scripts/provision_tenant_db.sh`.
- Add payment provider webhook adapters and subscription dunning/suspension
  rules.
- Add Alertmanager/Grafana/Loki or OpenSearch stack and incident runbooks.
- Continue toward offline POS sync and FBR certified-provider integration.

## Iteration 18: Staging E2E, Kiosk Checkout, Customer Display, and SaaS Ops

Status: Completed

Date: 2026-06-04

### Completed

- Built a real kiosk self-ordering checkout foundation:
  - Public `/tijara/kiosk/<slug>` touch UI with cart, customer/mobile capture,
    payment method selection, B2B/B2C audience selection, and
    dine-in/takeaway/pickup order type selection.
  - Public `/tijara/kiosk/<slug>/checkout` POST route with server-side item and
    price validation.
  - New `tijara.kiosk.order` and `tijara.kiosk.order.line` records with totals,
    pickup code, status workflow, and queue-ticket creation when the tenant has
    the `queue_system` feature.
- Added customer-display live order state:
  - New `tijara.customer.display.state` and line models.
  - Customer-display payload now returns order reference, line items, payment
    state, customer/cashier context, and totals.
  - POS orders can publish to the configured customer display state.
- Expanded SaaS billing operations:
  - Added secret-guarded public payment webhook route
    `/tijara/saas/payment/webhook/<provider>`.
  - Added auditable webhook event records and idempotent provider event lookup.
  - Added paid/failed/past-due/refunded status application into subscriptions.
  - Added dunning level, grace date, suspension reason, and dunning/suspension
    action on subscriptions.
- Improved tenant provisioning operations:
  - Added DNS, ingress, admin, backup, monitoring, and operations-manifest
    fields to provisioning requests.
  - Added `scripts/generate_tenant_ops_manifest.py` and
    `make provision-tenant-ops` to generate tenant DevOps artifacts.
- Added physical hardware certification records:
  - New `tijara.hardware.certification` model and views for printer, scanner,
    scale, cash drawer, label printer, and customer-display evidence tracking.
- Expanded monitoring baseline:
  - Added Alertmanager, Grafana, and Loki services/configuration to the
    monitoring Compose profile.
  - Added Grafana Prometheus/Loki datasource provisioning and Loki retention
    baseline.
- Upgraded browser E2E from scaffold to live seeded checks:
  - Added `scripts/e2e_seed.py`, `scripts/seed_e2e_odoo.sh`, and `make seed-e2e`.
  - Seed creates stable menu, kiosk, and customer-display slugs plus an
    Enterprise subscription for the target dev/staging DB.
  - Playwright tests now support `ODOO_DATABASE` for multi-database Odoo
    sessions and exercise public display data, kiosk shell, kiosk checkout, and
    customer-display live state on desktop and mobile projects.
- Added `package-lock.json` and `.gitignore` entries for Node/Playwright
  generated artifacts.
- Updated `README.md`, `DEPLOY.md`, `tests/e2e/README.md`,
  `deploy/monitoring/README.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 68 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- `python3 scripts/hardware_certification_smoke.py` passes all dry-run device
  certification profiles.
- `npm install` completed for Playwright dependencies with 0 vulnerabilities.
- Live dev DB `tijara_dev` was upgraded for `tijara_retail_core`,
  `tijara_saas_control`, and `tijara_pos_experience`, then Odoo HTTP was
  restarted.
- `make seed-e2e DB=tijara_dev` seeded and committed public E2E screen/profile
  data.
- Seeded Playwright run passed:
  - Command used `ODOO_BASE_URL=http://127.0.0.1:8069`,
    `ODOO_DATABASE=tijara_dev`, `TIJARA_DISPLAY_SLUG=tijara-e2e-menu`,
    `TIJARA_KIOSK_SLUG=tijara-e2e-kiosk`, and
    `TIJARA_CUSTOMER_DISPLAY_SLUG=tijara-e2e-customer`.
  - 8 browser tests passed across desktop and mobile projects.
- Final Odoo test runner passed on isolated database `tijara_test_iter18c`:
  - 12 post-install tests.
  - 0 failures.
  - 0 errors.
  - Covered `tijara_saas_control`, `tijara_pos_pk`, `tijara_analytics`, and
    `tijara_pos_experience`.
- Final cleanup removed generated `node_modules`, Playwright result artifacts,
  `__pycache__` folders, and `.pyc` files from the output tree.

### Known Gaps

- Kiosk checkout creates auditable kiosk/queue orders but does not yet complete
  paid POS accounting, payment-terminal authorization, or kitchen/payment
  orchestration.
- Customer display has live state records and payloads, but the POS frontend
  still needs continuous real-time publishing during cart editing/payment.
- Payment webhook foundation is provider-agnostic; JazzCash, Easypaisa, Stripe,
  or local bank payload mapping, signature verification, reconciliation, and
  settlement reports still need production adapter work.
- Tenant operations manifests are generated, but actual DNS provider APIs,
  certificate issuance, tenant admin creation, and post-provision smoke
  execution are still provider-specific follow-up work.
- Hardware certification records now exist, but physical certification on real
  printer, scanner, cash drawer, scale, label printer, and display models is
  still pending.
- Monitoring now includes Prometheus, Blackbox, Alertmanager, Grafana, and Loki,
  but production still needs alert routes, log shippers, PostgreSQL exporter,
  dashboards, and incident runbooks.
- FBR still needs certified provider credentials, exact payload mapping,
  sandbox sign-off, and production compliance testing.
- Offline POS sync remains pending.

### Next Iteration

- Wire POS frontend live updates into customer-display state during cart,
  discount, payment, refund, and receipt phases.
- Extend kiosk checkout into POS order/payment/kitchen ticket creation for
  restaurant and bakery pilots.
- Add real provider-specific payment webhook adapters and reconciliation
  reports.
- Automate tenant admin creation, DNS provider integration, TLS issuance,
  Blackbox target reload, and post-provision smoke execution.
- Add physical hardware certification evidence import/export and per-model pilot
  sign-off reports.
- Start offline POS queue/sync design and first implementation slice.

## Iteration 19: Kiosk POS Sync, Provider Adapters, FBR Compliance, and Offline Queue

Status: Completed

Date: 2026-06-04

### Completed

- Added kiosk-to-Odoo-POS sync:
  - Kiosk profiles can map a POS register plus cash/card/bank payment methods.
  - Kiosk payment capture modes now include pay-at-counter, record-paid,
    terminal-reference, and provider-webhook modes.
  - Kiosk orders now store payment provider/status/reference/terminal fields,
    linked POS config/session/order/payment method/payment record, sync
    timestamp, and sync error.
  - Configured kiosk checkout can create a linked `pos.order`, add a
    `pos.payment`, mark the POS order paid, and attempt stock picking creation
    while preserving a kiosk sync error if picking needs follow-up.
- Added continuous customer-display publishing foundation:
  - Authenticated `/tijara/customer-display/publish` JSON route.
  - Backend method for POS frontend snapshots with line/totals payloads.
  - POS frontend best-effort live publisher with fingerprinting so cart edits
    update customer-display state without blocking checkout.
  - Server-side POS order create/write auto-publish for configured customer
    displays when the tenant has the customer-display feature.
- Added provider-aware SaaS payment webhook adapters:
  - JazzCash, Easypaisa, Stripe, and generic/manual payload normalization.
  - Provider reference, transaction id, settlement batch, signature status,
    reconciliation status, and reconciled timestamp fields.
- Added FBR production-compliance metadata:
  - Certification environment, certified provider name, credential reference,
    provider invoice UUID, sandbox/certification reference, signed payload hash,
    compliance status, and certification check timestamp.
  - Live mode now checks certified-provider/client/credential readiness before
    submitting.
- Added real-device hardware certification evidence fields:
  - Observed serial, store location, driver version, physical signature,
    last physical seen timestamp, attachment evidence, and evidence hash.
- Added offline POS queue foundation:
  - `tijara.offline.pos.queue` model, access rules, menu, and views.
  - Payload hashing, JSON validation, duplicate-conflict detection, replay
    state, and error tracking.
- Updated demo seeding so the demo kiosk profile links to the demo POS config
  after POS config creation.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 69 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after generated Python cache cleanup.
- `python3 scripts/hardware_certification_smoke.py` passes all dry-run device
  profiles.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- Odoo test runner passed on isolated database `tijara_test_iter19e`:
  - 16 post-install tests.
  - 0 failures.
  - 0 errors.
  - Covered `tijara_saas_control`, `tijara_pos_pk`, `tijara_analytics`, and
    `tijara_pos_experience`.
- Live `tijara_dev` module upgrade completed for retail core, POS Pakistan,
  SaaS control, POS experience, and demo POS modules; the Odoo web container was
  restarted after the upgrade.
- Seeded E2E data was generated for public display, kiosk, customer display,
  and POS config flows.
- `npm install` completed for the Playwright E2E dependencies with 0
  vulnerabilities.
- Seeded Playwright E2E passed against live Odoo with elevated browser and
  localhost permissions:
  - 8 browser tests passed across desktop and mobile-touch projects.
  - 6 authenticated backend/POS route tests were skipped pending a fuller
    browser POS login/session harness.
- Final cleanup removed generated Python caches, Node dependencies, and
  Playwright result artifacts; the security audit passes on the cleaned tree.

### Known Gaps

- Kiosk POS sync now creates paid POS orders when configured, but full payment
  terminal authorization and kitchen/payment orchestration still require
  provider/device contracts and end-to-end pilots.
- POS customer-display live publishing is best-effort frontend polling; richer
  event-driven lifecycle hooks for payment, refund, and receipt phases are next.
- Provider adapters normalize common JazzCash/Easypaisa/Stripe payload shapes,
  but production still needs exact contract validation, native signature checks,
  settlement files, chargeback/refund reconciliation, and PSP certification.
- Physical hardware certification now stores evidence, but real printer,
  scanner, scale, cash drawer, label printer, and customer-display certification
  must still be performed on target models.
- FBR compliance metadata is present, but live certified provider credentials,
  sandbox sign-off, and production API compliance are still pending.
- Offline POS queue exists, but the offline browser/mobile POS client and replay
  worker are not complete yet.

### Next Iteration

- Run and stabilize Odoo tests, module upgrade, seeded E2E, and live POS browser
  flows after this implementation.
- Build offline POS browser queue capture and replay worker for linked POS
  orders.
- Add provider-native signature verification and settlement reconciliation jobs.
- Add physical hardware certification import/export reports and pilot sign-off
  templates.
- Harden FBR payload mapping with certified-provider sandbox credentials.
- Add customer-display lifecycle hooks for payment, paid/receipt, refund, and
  idle timeout states.

## Iteration 20: Offline POS Browser Capture, Replay Worker, and E2E Harness

Status: Completed

Date: 2026-06-04

### Completed

- Added authenticated offline POS browser endpoints:
  - `POST /tijara/offline-pos/capture` for one captured browser order.
  - `POST /tijara/offline-pos/replay` for pending queue replay by device or all
    devices.
  - `GET /tijara/offline-pos/status` for queue state counts.
- Extended `tijara.offline.pos.queue` with source app, order reference, payment
  status, amount, offline captured timestamp, replay attempts, last replay time,
  and server-side replay methods.
- Added server replay into real Odoo POS accounting flow:
  - Opens or creates the POS session for the captured register.
  - Rebuilds POS order lines with product taxes and discounts.
  - Recreates POS payments from captured browser payment payloads.
  - Marks the POS order paid when payments cover the total.
  - Stores linked replayed `pos.order`, replay state, attempts, and errors.
- Added duplicate protection for replayed device/order UID pairs and payload
  hash conflicts.
- Added per-register PostgreSQL advisory locking and retryable lock/serialization
  handling for offline replay into the same POS configuration.
- Added disabled-by-default `Tijara Replay Offline POS Orders` cron for staged
  worker rollout.
- Added POS frontend offline queue asset:
  - Stable per-register device id.
  - localStorage queue for captured browser orders.
  - Order serialization with products, customer, B2B/B2C, service mode, totals,
    and payment lines.
  - Automatic replay when the browser is online.
  - Best-effort capture on POS sync failure.
- Extended Odoo transaction tests for offline POS capture/replay and replayed
  source-order deduplication.
- Added Playwright helper utilities and an authenticated offline POS replay
  browser smoke test.
- Updated the E2E seed script to print product and payment-method IDs required
  by the authenticated offline replay test.
- Added optional `TIJARA_E2E_PASSWORD`/`TIJARA_E2E_LOGIN` user seeding for
  authenticated staging browser tests without committing credentials.
- Updated `README.md`, `DEPLOY.md`, E2E docs, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 70 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after generated-artifact cleanup.
- Docker Compose config validates with `.env.example` and
  `secrets/.env.secrets.example`.
- Odoo test runner passed on isolated database `tijara_test_iter20_final`:
  - 18 post-install tests.
  - 0 failures.
  - 0 errors.
  - Covered `tijara_saas_control`, `tijara_pos_pk`, `tijara_analytics`, and
    `tijara_pos_experience`.
- Live `tijara_dev` module upgrade completed for `tijara_pos_experience`; the
  Odoo web container was restarted after the upgrade.
- Seeded E2E data was generated with display, kiosk, customer-display, POS
  config, product, payment method, and optional authenticated E2E user exports.
- `npm install` completed for Playwright dependencies with 0 vulnerabilities.
- Seeded Playwright E2E passed against live Odoo with elevated browser and
  localhost permissions:
  - 9 browser tests passed.
  - 7 tests skipped intentionally: POS UI shell is opt-in, refund/report routes
    need staging URLs, and mobile offline replay is opt-in to avoid parallel
    replay against one POS register.
- Final cleanup removed generated Python caches, Node dependencies, and
  Playwright result artifacts; artifact scans are empty.

### Known Gaps

- Offline POS now has browser capture and server replay, but the cashier-facing
  offline mode UX, conflict review screen, mobile offline replay certification,
  and full offline payment terminal orchestration still need pilot hardening.
- Replay uses captured product/payment IDs and current Odoo tax/payment
  configuration; production rollout must certify this per POS register and
  store network.
- Payment provider adapters still need native provider signatures, settlement
  file reconciliation, refunds, chargebacks, and PSP certification.
- FBR still needs certified-provider credentials, sandbox sign-off, and live
  compliance tests.
- Hardware certification still needs real device pilots and signed evidence.
- Monitoring, alerting, restore drills, security scanning, and load testing
  still need production execution against staging.

### Next Iteration

- Add offline conflict review/actions for duplicate source orders and failed
  replay records.
- Enable properly permissioned staging POS credentials and opt into POS UI,
  mobile offline replay, refund, and report browser checks.
- Build provider-native signature verification and settlement reconciliation
  jobs.
- Continue FBR certified-provider sandbox wiring and hardware certification
  pilot records.

## Iteration 21: Offline Conflict Review and Full Staging POS E2E Harness

Status: Completed

Date: 2026-06-04

### Completed

- Added cashier-facing offline POS queue UX:
  - POS control button shows local browser queue count.
  - Cashiers can trigger an immediate replay check from the POS shell.
  - The status dialog reports queued orders, blocked review items, and replayed
    items from the current check.
- Expanded `tijara.offline.pos.queue` into a back-office review workbench:
  - New terminal states: duplicate, merged, and cancelled.
  - Review metadata: reviewer, review time, review action, review note,
    duplicate target, and merge target.
  - Stored audit measures: payload line count, payment count, total delta, and
    replay latency.
  - Actions for retry, cancel, mark duplicate, merge, manual mark replayed, and
    fail.
  - Dedicated Offline Conflict Review action plus Offline Replay Audit
    pivot/graph views.
- Added Odoo transaction tests for offline conflict resolution:
  - Duplicate marking.
  - Merge resolution.
  - Cancellation with reviewer metadata.
  - Retry-to-replay for a previously failed but valid offline order.
- Added staging POS user setup to the E2E seed:
  - Creates/updates a staging-only POS E2E user when
    `TIJARA_E2E_PASSWORD` is supplied.
  - Grants internal user, POS user, POS manager, Tijara user, and Tijara manager
    groups using Odoo 19 `group_ids`.
  - Prints seeded POS/product/payment/refund/report/offline-review exports.
- Added seeded browser E2E coverage:
  - Authenticated POS shell launch through `pos.config.open_ui()`.
  - Offline conflict review backend route.
  - Offline browser capture/replay into a paid POS order.
  - Receipt report rendering for replayed POS orders.
  - Print-to-bridge method coverage with accepted/unreachable bridge outcomes.
  - Refund barcode scan against a seeded POS receipt through authenticated
    Odoo JSON-RPC.
- Fixed Odoo 19 POS config loader compatibility:
  - `tijara_pos_pk` now loads required core `pos.config` fields such as
    company, currency, payment methods, pricelist flags, receipt flags,
    discount flags, printer/proxy flags, and POS UI toggles.
  - This fixed the direct staging POS UI crash caused by missing
    `use_pricelist`, `currency_id`, and related config data.
- Updated `README.md`, `DEPLOY.md`, E2E docs, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 70 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after generated-artifact cleanup.
- Docker Compose config validates with required dev secret values supplied.
- Live `tijara_dev` module upgrades completed for:
  - `tijara_pos_experience`
  - `tijara_pos_pk`
- The live Odoo web container was restarted after module upgrades.
- POS loader shell probe confirmed `pos.config`, `pos.session`,
  `res.company`, `res.currency`, and `res.users` data now load for the seeded
  POS session.
- Odoo test runner passed on isolated database `tijara_test_iter21_final`:
  - 20 post-install tests.
  - 0 failures.
  - 0 errors.
  - Covered `tijara_saas_control`, `tijara_pos_pk`, `tijara_analytics`, and
    `tijara_pos_experience`.
- Seeded Playwright E2E passed against live Odoo with POS UI enabled:
  - 19 browser tests passed across desktop and mobile-touch projects.
  - 1 test skipped intentionally: mobile offline replay remains opt-in via
    `TIJARA_RUN_MOBILE_OFFLINE_E2E=1`.
- Final cleanup removed generated Python caches, `node_modules`, and Playwright
  result artifacts; artifact scan is empty.

### Known Gaps

- POS offline capture/replay and conflict review are now functional, but
  store-network pilots still need real cashier training, recovery runbooks,
  payment-terminal behavior, and load testing.
- Print-to-bridge browser E2E reaches the Odoo method path; a real local bridge
  service and physical receipt printer are still required for accepted print
  certification.
- Payment providers still need native signatures, settlement reconciliation,
  refunds, chargebacks, and PSP certification.
- FBR still needs certified-provider credentials, sandbox sign-off, and live
  compliance tests.
- Hardware certification still needs real printer, scanner, scale, cash drawer,
  label printer, and customer-display devices.
- Monitoring, alerting, restore drills, security scanning, and load testing
  still need staging/production execution.

### Next Iteration

- Start provider-native payment hardening: JazzCash/Easypaisa/Stripe signature
  verification, settlement reconciliation, refunds, and chargeback records.
- Add FBR certified-provider sandbox adapter configuration and compliance test
  fixtures once credentials/contracts are available.
- Add offline POS runbooks and pilot dashboards for queue age, conflicts,
  duplicate rate, replay latency, and failed-retry trends.
- Build physical hardware certification execution records around the bridge E2E
  path for each target printer/scanner/scale/display model.
- Add staging monitoring drills for POS/offline endpoints, hardware bridge
  health, backup restore, and alert routing.

## Iteration 22: Payment Hardening, Offline Pilot Dashboards, Hardware Execution Checks, and Monitoring Drills

Status: Completed

Date: 2026-06-05

### Completed

- Hardened SaaS payment webhooks:
  - Added native Stripe webhook HMAC verification.
  - Added JazzCash secure-hash verification candidates for provider-contract
    validation.
  - Added Easypaisa HMAC verification support using raw-body or sorted-field
    payload signatures.
  - Added `TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES` /
    `tijara.saas.payment_require_native_signatures` enforcement switch.
  - Added provider event type, signature algorithm, signature checked time,
    provider audit hash, fee amount, net amount, refund reference, chargeback
    reference, and chargeback reason fields.
  - Added explicit payment, settlement, refund, chargeback, and unknown event
    types.
  - Added reconciliation actions for manually reconciled and mismatch states.
- Improved payment event behavior:
  - Refund events move subscriptions back to past due.
  - Chargeback events record the provider reason/reference and move the
    subscription to past due with a suspension reason.
  - Settlement events remain auditable reconciliation records without
    accidentally changing subscription state.
- Added offline POS pilot operations metrics:
  - Queue age minutes.
  - Pilot attention state: OK, watch, blocked, resolved.
  - Failure bucket: validation, duplicate, payment, stock/picking,
    device/network, unknown.
  - Outage reference, recovery owner, and cashier runbook notes.
  - Automatic metric refresh after capture, validation, replay, retry, cancel,
    duplicate, merge, and manual replay actions.
  - Added Offline Pilot Dashboard action/menu and graph/pivot/list fields.
- Added physical hardware certification execution records:
  - `tijara.hardware.certification.check` model.
  - Per-device check templates for receipt printer, label printer, scanner, QR
    scanner, cash drawer, scale, customer display, and fiscal device.
  - Bridge execution action with observed response, bridge job id, response
    code, duration, operator, execution time, and evidence hash.
  - Certification pass gate now requires all execution checks to pass when
    checks exist.
  - Added list/form/pivot/graph views and access rules.
- Added staging monitoring drill tooling:
  - `scripts/staging_monitoring_drill.py`.
  - `make monitoring-drill`.
  - Checks Odoo web, offline POS status, hardware bridge health, Prometheus,
    Alertmanager, Grafana, and optional backup artifact presence.
- Updated deployment/config/docs:
  - `.env.example`
  - `secrets/.env.secrets.example`
  - `README.md`
  - `DEPLOY.md`
  - `PROGRESS.md`

### Validation

- `make validate` passes.
- 70 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after generated cache cleanup.
- `scripts/staging_monitoring_drill.py` smoke passes with blank endpoints and
  reports skipped checks instead of crashing.
- Isolated Docker Compose Odoo test run passed on database
  `tijara_test_iter22b`:
  - 24 post-install tests.
  - 0 failures.
  - 0 errors.
  - Covered `tijara_saas_control`, `tijara_retail_core`, `tijara_pos_pk`,
    `tijara_pos_experience`, and `tijara_analytics`.
- Initial Odoo test run found and fixed one offline pilot metric bug:
  invalid payloads were marked failed but skipped metric refresh before the
  early `continue`.
- Temporary isolated Docker Compose project and volumes were removed.
- Final generated-artifact scan is empty.

### Known Gaps

- Provider-native signature implementations still need PSP contract validation
  and certification with JazzCash, Easypaisa, and Stripe production/sandbox
  payloads.
- Settlement reconciliation is now modeled and auditable, but real settlement
  file/API import, payout matching, refunds, chargeback deadlines, and PSP
  dispute workflows still need provider-specific automation.
- Offline pilot dashboards are available, but real store-network drills,
  cashier training, payment-terminal behavior, load testing, and signed runbooks
  are still required.
- Hardware execution records exist, but real physical devices still need
  certification evidence for each printer, scanner, scale, drawer, label
  printer, and customer-display model.
- FBR still needs certified-provider credentials, sandbox sign-off, and live
  compliance tests.
- Monitoring drill tooling exists, but staging/production alert routing,
  backup restore drills, log retention, load testing, and security scanning must
  be executed against the actual environment.

### Next Iteration

- Build provider settlement import/reconciliation records for JazzCash,
  Easypaisa, Stripe, and manual bank transfers.
- Add refund and chargeback operator workflows with due dates, evidence,
  partial/full amount handling, and subscription/accounting impacts.
- Add a staging offline POS pilot runbook document and KPI snapshots for queue
  age, blocked queues, duplicate rate, replay latency, and failed retry trends.
- Add certified-provider FBR sandbox fixture support once real provider
  contracts/credentials are available.
- Run monitoring, backup restore, load, and security drills against a prepared
  staging environment.

## Iteration 23: Provider Settlement Reconciliation and Dispute Workflows

Status: Completed

Date: 2026-06-05

### Completed

- Committed Iteration 22 as local milestone:
  - Commit `4d3d077 Add payment hardening and pilot readiness`.
- Added provider settlement import and reconciliation models:
  - `tijara.saas.payment.settlement.batch`.
  - `tijara.saas.payment.settlement.line`.
  - Provider support for manual bank, JazzCash, Easypaisa, Stripe, and generic
    other providers.
  - Settlement JSON import supports a list or an object with `lines`,
    `transactions`, or `data`.
  - Statement line normalization captures provider event reference,
    transaction id, invoice/subscription hints, event type, gross amount, fee,
    net amount, settlement date, raw line JSON, and deterministic line hash.
  - Settlement lines match to existing payment webhooks, subscriptions, and
    SaaS invoices.
  - Settlement batches compute line count, matched count, mismatch count,
    dispute line count, actual gross/fee/net, expected gross/fee/net, and
    deltas.
  - Operators can import statements, match lines, create dispute cases, mark
    reconciled, mark mismatch, and close batches.
- Added refund and chargeback operator workflow:
  - `tijara.saas.payment.dispute`.
  - Cases support refund and chargeback types with provider reference,
    transaction id, amount, fee, due date, assigned operator, reason, evidence,
    outcome, and accounting action required.
  - Evidence hash includes summary, evidence JSON, attachments, amount, provider
    reference, transaction id, and reason.
  - Open cases move subscriptions to past due.
  - Evidence submission moves cases to evidence-submitted state.
  - Won cases restore subscriptions to paid/active.
  - Lost/refunded cases keep subscriptions past due and record the accounting
    action required.
- Connected existing payment webhooks to dispute cases:
  - Refund/chargeback webhook events now create or link operator dispute cases.
  - Webhook form has a Create Dispute Case action and dispute case link.
- Added settlement/dispute UI:
  - Payment Settlements menu.
  - Settlement Lines menu.
  - Refunds and Chargebacks menu.
  - List/form/pivot/graph views for settlement batches, settlement lines, and
    dispute cases.
- Updated default Odoo test tags to include `tijara_retail_core` from the
  previous iteration and kept the wider enterprise test scope.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes after implementation.
- 72 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after removing generated
  `__pycache__` build artifacts from the isolated Odoo run.
- Isolated Docker/Odoo transaction suite passed with `0 failed, 0 error(s)` of
  26 tests for `tijara_saas_control`, `tijara_retail_core`, `tijara_pos_pk`,
  `tijara_pos_experience`, and `tijara_analytics`.
- Odoo transaction tests were extended for:
  - Settlement batch import, matching, gross/fee/net totals, line hashes, and
    reconciled status.
  - Settlement refund line creating a dispute case, moving subscription past
    due, submitting evidence, hashing evidence, and winning the case to restore
    paid/active status.
  - Refund and chargeback webhook events creating dispute cases.

### Known Gaps

- Settlement import supports JSON payloads, but production still needs
  provider-specific CSV/API/file parsers and exact field mapping from each PSP
  contract.
- Accounting impact is tracked as required action, but automatic journal
  entries, credit notes, refund payments, chargeback fees, and payout clearing
  still need implementation with finance sign-off.
- PSP settlement/reconciliation needs certification with real JazzCash,
  Easypaisa, Stripe, and bank statement samples.
- FBR certified-provider sandbox/live compliance remains pending.
- Hardware and offline POS still need real store/device pilots.
- Monitoring, load, security, and restore drills still need execution against a
  prepared staging environment.

### Next Iteration

- Add provider-specific settlement parser fixtures for JazzCash, Easypaisa,
  Stripe, and manual bank transfer statements.
- Build accounting posting workflow for refunds, credit notes, provider fees,
  chargeback fees, payout clearing, and reconciliation write-off policy.
- Add finance approval controls for dispute outcomes and settlement batch
  closeout.
- Add staging offline POS pilot runbook and KPI collectors for pilot metrics.
- Continue FBR certified-provider sandbox fixture support once credentials and
  contracts are available.

## Iteration 24: Settlement Parser Profiles and Finance Closeout Controls

Status: Completed

Date: 2026-06-05

### Completed

- Added provider settlement parser controls:
  - Settlement batches now support `statement_format` as JSON or CSV.
  - Parser profile options are available for auto/generic, JazzCash merchant
    statement, Easypaisa merchant statement, Stripe balance transaction, and
    manual bank statement payloads.
  - CSV statements are imported through `csv.DictReader`.
  - JSON statements still support a list or an object with `lines`,
    `transactions`, or `data`.
  - Normalization now covers provider references, source/balance transaction
    ids, bank references, invoice/subscription hints, gross amount, fee, net,
    provider status, and timestamp/date parsing.
- Added finance accounting action workflow:
  - New model `tijara.saas.payment.accounting.action`.
  - Actions cover payout clearing, provider fees, refund credit notes, refund
    payments, chargeback receivables, chargeback fees, write-off review, and
    manual review.
  - Each accounting action tracks source settlement batch/line, dispute case,
    webhook event, subscription, invoice, amount, approval state, approval user,
    timestamps, raw context JSON, notes, and deterministic audit hash.
- Added settlement closeout controls:
  - Settlement batches now track finance approval required/status, approver, and
    approval timestamp.
  - Settlement lines generate finance actions from payment/refund/chargeback
    event type and fee/net/gross amounts.
  - Settlement batches cannot be marked reconciled while finance approval is
    required and accounting actions are missing or unapproved.
- Added dispute finance controls:
  - Refund and chargeback cases now track finance approval status and generated
    accounting actions.
  - Lost chargebacks generate chargeback receivable, chargeback fee, and
    write-off review actions.
  - Refund cases generate refund credit-note/payment actions.
  - Won dispute cases mark finance approval as not required.
- Added Odoo UI:
  - Payment Accounting Actions menu with list/form/search/pivot/graph views.
  - Finance action tabs and buttons on settlement batches, settlement lines, and
    refund/chargeback cases.
- Removed Odoo 19 deprecation warning from customer-display publish route by
  switching the controller route to `type="jsonrpc"`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 73 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after generated `__pycache__`
  artifacts were removed.
- Isolated Docker/Odoo transaction suite passed with `0 failed, 0 error(s)` of
  28 tests for `tijara_saas_control`, `tijara_retail_core`, `tijara_pos_pk`,
  `tijara_pos_experience`, and `tijara_analytics`.
- Odoo transaction tests now cover:
  - Settlement finance action generation and approval gating before batch
    reconciliation.
  - Stripe CSV parser profile fixture normalization for amount/fee/net cents,
    source transaction, subscription matching, and settlement date parsing.
  - Refund settlement line accounting action generation.
  - Chargeback dispute accounting actions, approval hashes, and finance
    approval status.

### Known Gaps

- Parser profiles are implemented against normalized fixtures, but production
  still needs real signed-off JazzCash, Easypaisa, Stripe, and bank statement
  samples from provider contracts.
- Accounting actions are auditable approval records, but automatic journal
  entries, credit notes, refund payments, chargeback fee entries, payout
  clearing moves, and write-offs still need configured accounts and finance
  sign-off.
- PSP settlement certification, FBR certified-provider sandbox/live sign-off,
  and real hardware/store pilots remain pending.
- Full staging browser E2E, monitoring drills, backup restore drills, load
  testing, dependency/container scanning, and security review still need staged
  execution.

### Next Iteration

- Build automatic accounting posting foundations behind explicit finance
  configuration:
  - Provider clearing journal/account settings.
  - Provider fee expense account.
  - Refund/credit-note account mapping.
  - Chargeback receivable/fee/write-off account mapping.
  - Draft journal entry or credit-note creation from approved accounting
    actions.
- Add Odoo tests that prove approved accounting actions create draft accounting
  moves only when all finance configuration is present.
- Add deployment documentation for finance account setup and month-end
  settlement close SOP.
- Continue toward staging execution: browser E2E, monitoring drill, restore
  drill, load smoke, and security scan runs.

## Iteration 25: Finance Account Mapping and Draft Accounting Moves

Status: Completed

Date: 2026-06-05

### Completed

- Added company-level payment accounting configuration:
  - Payment accounting journal.
  - PSP clearing account.
  - Payment counterpart account.
  - Provider fee expense account.
  - Refund/credit-note account.
  - Chargeback receivable account.
  - Chargeback fee expense account.
  - Write-off expense account.
- Added guarded accounting move creation on
  `tijara.saas.payment.accounting.action`:
  - Approved actions can create balanced draft Odoo journal entries.
  - Draft move creation is blocked until the required finance configuration is
    present.
  - Manual-review actions intentionally refuse automatic move creation.
  - Existing draft moves are reused to avoid duplicate accounting entries.
  - Draft move creator/time and audit hash are tracked.
- Added accounting routes for payout clearing, provider fees,
  refund/credit-note clearing, refund payment clearing, chargeback receivable,
  chargeback fee, and write-off actions.
- Added back-office UI:
  - Company form finance account fields.
  - Payment Accounting Action buttons for `Create Draft Move` and `Post Move`.
  - Search/list visibility for approved actions that still need a draft move.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 74 XML files parse successfully.
- Isolated Docker/Odoo transaction suite passed with `0 failed, 0 error(s)` of
  31 tests for `tijara_saas_control`, `tijara_retail_core`, `tijara_pos_pk`,
  `tijara_pos_experience`, and `tijara_analytics`.
- New Odoo transaction tests cover:
  - Approved accounting actions refusing draft move creation when finance
    configuration is missing.
  - Approved provider fee actions creating balanced draft journal entries from
    configured company accounts.
  - Re-running draft move creation reuses the existing move.
  - Manual-review actions refusing automatic accounting moves.

### Known Gaps

- Draft journal entries exist, but production posting policy still needs
  finance sign-off for each PSP, bank, tax, refund, and write-off scenario.
- Credit-note and refund-payment specialization is still modeled as draft
  journal-entry foundation rather than full tax-aware payment workflows.
- PSP settlement parser certification still needs signed-off JazzCash,
  Easypaisa, Stripe, and bank statement samples.
- FBR certified-provider sandbox/live sign-off remains pending.
- Physical hardware certification, staging browser E2E, monitoring drills,
  backup restore drills, load testing, dependency/container scans, and security
  review still need staging/production execution.

### Next Iteration

- Add finance batch actions to create draft moves for all approved settlement
  or dispute accounting actions in one operator step.
- Add specialized refund/credit-note and refund-payment workflows where Odoo
  accounting/tax treatment requires customer documents instead of journal
  entries.
- Add staging browser E2E execution for POS checkout, refund barcode scan,
  receipt print-to-bridge, customer display, and offline replay.
- Run monitoring drill, restore drill, load smoke, dependency/container scans,
  and security audit against a prepared staging stack.
- Continue PSP/FBR certification work once real provider samples, credentials,
  and compliance contracts are available.

## Iteration 26: Bulk Finance Draft Move Closeout

Status: Completed

Date: 2026-06-05

### Completed

- Added bulk draft accounting move creation for settlement closeout:
  - Settlement batches can create draft moves for all approved finance actions.
  - Settlement lines can create draft moves for their approved finance actions.
  - Refund/chargeback dispute cases can create draft moves for all approved
    finance actions.
- Added operator UI controls:
  - `Create Draft Moves` on settlement batch forms after finance approval.
  - `Create Draft Moves` on settlement line forms when finance actions exist.
  - `Create Draft Moves` on refund/chargeback case forms after finance
    approval.
  - Inline finance action lists now show linked accounting moves.
- Added guardrails:
  - Bulk closeout refuses to run when no approved finance actions are ready.
  - Existing accounting-action safeguards still prevent missing configuration,
    manual-review auto posting, duplicate draft moves, or posting unapproved
    actions.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes after generated `__pycache__`
  artifacts were removed.
- Isolated Docker/Odoo transaction suite passed with `0 failed, 0 error(s)` of
  31 tests for `tijara_saas_control`, `tijara_retail_core`, `tijara_pos_pk`,
  `tijara_pos_experience`, and `tijara_analytics`.
- Odoo transaction tests were extended to cover:
  - Settlement batch bulk draft move creation for approved payout clearing and
    provider fee actions.
  - Chargeback dispute bulk draft move creation for receivable, fee, and
    write-off actions.

### Known Gaps

- Bulk move creation improves finance closeout, but credit-note and refund
  payment specialization is still pending for tax-aware customer document
  scenarios.
- Production finance policy still needs sign-off on posting, write-off,
  refund, chargeback, bank-clearing, and PSP-specific treatment.
- Staging browser E2E, monitoring drills, restore drills, load tests,
  dependency/container scans, and security review still need execution against
  a prepared staging stack.
- PSP/FBR certification still depends on real provider samples, credentials,
  and compliance contracts.

### Next Iteration

- Build specialized refund/credit-note and refund-payment workflows where Odoo
  accounting and Pakistan tax treatment require customer-facing documents or
  payments rather than generic journal entries.
- Add staging browser E2E execution for POS checkout, refund barcode scan,
  receipt print-to-bridge, customer display, and offline replay.
- Run monitoring drill, restore drill, load smoke, dependency/container scans,
  and security audit against a prepared staging stack.
- Continue PSP/FBR certification work once real provider samples, credentials,
  and compliance contracts are available.

## Iteration 27: Specialized Refund Credit Notes and Refund Payments

Status: Completed

Date: 2026-06-05

### Completed

- Added customer-facing refund accounting specialization:
  - Approved `refund_credit_note` accounting actions now create draft customer
    refund credit notes (`out_refund`) linked to the source subscription and
    source invoice when available.
  - Approved `refund_payment` accounting actions now create draft outbound
    `account.payment` refund payments linked back to the finance action.
  - Posting a refund payment action posts the payment, links the generated
    accounting move, marks the action posted, and refreshes the audit trail.
- Added company setup for `Tijara Refund Payment Journal`.
- Added production guardrails:
  - Refund payments require a configured refund payment journal.
  - Refund payments require an outbound outstanding payment account on the
    journal/payment method or company payment account setup.
  - Refund payments require a customer receivable destination account.
  - Duplicate document creation reuses existing linked credit notes or payments.
- Updated finance closeout UI visibility:
  - Payment Accounting Actions show linked refund payments.
  - Settlement batch, settlement line, and dispute case finance-action lists now
    show linked refund payments alongside accounting moves.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- Isolated Docker/Odoo transaction suite passed with `0 failed, 0 error(s)` of
  33 tests for `tijara_saas_control`, `tijara_retail_core`, `tijara_pos_pk`,
  `tijara_pos_experience`, and `tijara_analytics`.
- Odoo transaction tests were extended to cover:
  - Refund credit-note actions creating draft customer credit notes.
  - Refund payment actions creating draft outbound payments.
  - Refund payment posting linking the generated posted accounting move.
  - Refund journal outstanding-account and customer receivable setup through
    the accounting fixtures.

### Known Gaps

- Production finance/tax policy still needs sign-off for refund credit notes,
  outbound refund payments, chargebacks, write-offs, and PSP/bank clearing.
- PSP settlement parser certification still needs real JazzCash, Easypaisa,
  Stripe, and bank statement samples plus provider sign-off.
- FBR certified-provider sandbox/live sign-off remains pending.
- Physical hardware certification, staging browser E2E, monitoring drills,
  backup restore drills, load testing, dependency/container scans, and security
  review still need staging/production execution.

### Next Iteration

- Run the full staging browser E2E harness against a permissioned Odoo POS user:
  POS checkout, refund barcode scan, receipt print-to-bridge, customer display,
  offline replay, and kiosk checkout.
- Add staging monitoring drill evidence, backup restore drill evidence, load
  smoke results, dependency/container scan output, and security review notes.
- Continue PSP/FBR certification work once real provider samples, credentials,
  and compliance contracts are available.
- Start physical hardware certification records for the first printer, cash
  drawer, scanner, scale, customer display, and label printer models.

## Iteration 28: Staging Browser E2E Evidence Runner

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_staging_e2e.sh` for production-style browser QA execution:
  - Supports `TIJARA_E2E_SCOPE=public`, `authenticated`, or `full`.
  - Validates required staging slugs, credentials, POS config/product/payment
    IDs, refund barcode, refund action URL, report URL, and offline review URL
    before Playwright runs.
  - Probes the Odoo `/web/login` endpoint before executing specs.
  - Runs the existing critical Playwright specs for public display, kiosk
    checkout, customer display, POS shell, print-to-bridge, refund barcode scan,
    report rendering, offline replay, and offline conflict review.
  - Writes ignored evidence under `deploy/runtime/e2e-evidence/<run-id>/`:
    environment summary, Playwright output, JSON results, and Markdown summary.
- Added `make e2e-staging` and `npm run test:e2e:staging`.
- Updated `README.md`, `DEPLOY.md`, `tests/e2e/README.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_staging_e2e.sh` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- The evidence runner is ready, but a real staging execution still requires a
  running Odoo staging URL, seeded E2E slugs, and a permissioned POS test user.
- Browser E2E still needs full click-through assertions for real POS checkout
  payment flow beyond shell/open/report/route coverage.
- Physical hardware certification, PSP/FBR certification, monitoring drills,
  backup restore drills, load testing, dependency/container scans, and security
  review still need staging/production execution.

### Next Iteration

- Execute `make seed-e2e` and `make e2e-staging` against a live staging stack,
  then archive evidence artifacts from `deploy/runtime/e2e-evidence/`.
- Expand direct POS browser assertions for cashier checkout, payment, receipt,
  refund scan, and customer display updates using the permissioned staging POS
  user.
- Run monitoring drill, restore drill, load smoke, container/dependency scans,
  and security review against the same staging environment.

## Iteration 29: Staging Operations Evidence Runner

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_staging_ops_checks.sh` for grouped staging operations
  sign-off evidence:
  - Supports `TIJARA_OPS_CHECKS=monitoring,load,dependency` for the normal
    staging smoke.
  - Supports `TIJARA_OPS_CHECKS=full` to include monitoring, restore drill,
    load smoke, dependency scan, and container scan.
  - Supports `TIJARA_OPS_STRICT=1` to fail when checks are skipped because a
    tool, URL, or backup artifact is missing.
  - Writes ignored evidence under `deploy/runtime/ops-evidence/<run-id>/`:
    environment summary, per-check logs, status table, and Markdown summary.
- Added `make ops-staging` and `npm run ops:staging`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_staging_ops_checks.sh` passes.
- Local non-strict skip-path smoke for an unknown check writes evidence and
  exits cleanly.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- The operations evidence runner is ready, but true production evidence still
  needs a live staging stack with monitoring services, backup artifact, k6,
  Trivy, and optional pip-audit installed.
- Restore drill and container scanning should be required with
  `TIJARA_OPS_STRICT=1` during release sign-off.
- Browser POS click-through, physical hardware certification, PSP/FBR
  certification, and security review execution still remain open.

### Next Iteration

- Execute `make ops-staging` with `TIJARA_OPS_CHECKS=full` and
  `TIJARA_OPS_STRICT=1` against a prepared staging stack.
- Archive staging operations evidence and browser E2E evidence together for a
  release-candidate sign-off package.
- Expand authenticated POS browser click-through for checkout, payment,
  receipt, refund barcode scan, customer display updates, and offline replay.

## Iteration 30: Release Candidate Evidence Gate

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_release_candidate_gate.sh` for release-candidate sign-off:
  - Supports `TIJARA_RELEASE_CHECKS=local` for scaffold validation, JavaScript
    checks, security audit, and shell script syntax checks.
  - Supports `TIJARA_RELEASE_CHECKS=full` for clean-git, local checks, Odoo
    transaction tests, guarded staging browser E2E, and guarded staging
    operations evidence.
  - Writes ignored evidence under `deploy/runtime/release-evidence/<run-id>/`:
    environment summary, per-check logs, status table, and Markdown summary.
- Added `make release-candidate` and `npm run release:candidate`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_release_candidate_gate.sh` passes.
- `TIJARA_RELEASE_CHECKS=local make release-candidate` passes and writes local
  release evidence.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Full release-candidate execution still needs a live seeded staging Odoo stack,
  permissioned POS test user, E2E slugs/IDs, monitoring services, backup
  artifact, k6, Trivy, and Docker test access.
- Browser POS click-through still needs richer checkout/payment/refund
  assertions beyond current route/shell/API-level staging coverage.
- Physical hardware certification, PSP/FBR certification, and formal security
  review execution remain open.

### Next Iteration

- Prepare and execute `TIJARA_RELEASE_CHECKS=full make release-candidate`
  against a staging release candidate.
- Expand POS browser click-through assertions for cashier checkout, payment,
  receipt printing, refund barcode scan, customer display updates, and offline
  replay.
- Start release sign-off evidence templates for PSP/FBR and physical hardware
  certification packages.

## Iteration 31: Release Sign-Off Package Templates

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/generate_signoff_pack.py` for production release approval
  packages:
  - Generates go/no-go, PSP certification, FBR certification, physical hardware
    certification, finance/tax, and security review templates.
  - Captures package ID, target environment, git branch, git head, and generated
    timestamp.
  - Accepts evidence files or directories through repeated `--evidence-path`
    arguments or `TIJARA_SIGNOFF_EVIDENCE_PATHS`.
  - Writes an `evidence-manifest.json` with SHA-256 fingerprints, relative
    paths, absolute paths, and file sizes for attached evidence.
  - Defaults output to `deploy/runtime/signoff-packages/<run-id>/`, which stays
    ignored from source control.
- Added operator shortcuts:
  - `make signoff-pack`
  - `npm run signoff:pack`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Local sign-off package smoke run passes with a temporary output directory.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Templates are ready, but production sign-off still needs real PSP settlement
  samples, certified FBR sandbox/live responses, physical hardware pilot
  evidence, finance/tax approval, and security owner approval.
- Full release-candidate execution still needs a live seeded staging Odoo stack,
  permissioned POS test user, monitoring services, backup artifact, k6, Trivy,
  and Docker test access.
- Browser POS click-through still needs richer checkout/payment/refund
  assertions beyond current route/shell/API-level staging coverage.

### Next Iteration

- Execute `TIJARA_RELEASE_CHECKS=full make release-candidate` against a prepared
  staging release candidate and feed evidence into `make signoff-pack`.
- Expand authenticated POS browser click-through for checkout, payment, receipt
  printing, refund barcode scan, customer display updates, and offline replay.
- Start live pilot sign-off records for first supported PSP, certified FBR
  provider, receipt printer, cash drawer, scanner, scale, customer display, and
  label printer models.

## Iteration 32: Authenticated Enterprise POS Browser Journey

Status: Completed

Date: 2026-06-05

### Completed

- Added `tests/e2e/pos-enterprise-journey.spec.mjs` as an integrated
  authenticated Playwright staging journey:
  - Captures a paid browser/offline POS payload.
  - Replays the order into Odoo POS.
  - Verifies paid order state, lines, payments, B2C audience, takeaway order
    type, and generated Tijara receipt barcode.
  - Renders the Tijara POS receipt report for the created order.
  - Exercises `action_tijara_print_receipt_to_bridge` and accepts configured or
    unconfigured bridge-printer outcomes as evidence.
  - Publishes and reads customer-display state when the POS register has a
    customer display configured.
  - Creates a refund/exchange request and verifies barcode matching against the
    generated receipt barcode.
  - Replays the same browser order again to prove duplicate handling.
  - Reads offline POS status by source device for replay audit evidence.
- Added the new spec to the guarded staging E2E runner for
  `TIJARA_E2E_SCOPE=authenticated` and `TIJARA_E2E_SCOPE=full`.
- Updated `README.md`, `DEPLOY.md`, `tests/e2e/README.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_staging_e2e.sh` passes.
- `bash scripts/js_check.sh` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- The integrated journey is ready, but actual execution still needs a live
  seeded staging Odoo stack with permissioned POS credentials.
- Direct cashier UI clicks through product grid, pay screen, receipt screen, and
  refund form controls still need deeper selectors once the staging POS UI is
  available.
- PSP/FBR certified-provider credentials and physical hardware devices are still
  external blockers for production certification.

### Next Iteration

- Add staging E2E evidence summarization into the release sign-off package so
  the enterprise POS journey result is easier for release approvers to review.
- Expand direct POS UI click selectors for product search, add-to-cart,
  payment, receipt print button, and refund form when a prepared staging stack
  is available.
- Continue PSP/FBR/hardware certification automation around real provider and
  device evidence.

## Iteration 33: Sign-Off Evidence Summary Extraction

Status: Completed

Date: 2026-06-05

### Completed

- Enhanced `scripts/generate_signoff_pack.py` to generate
  `evidence-summary.md` alongside the sign-off templates and manifest.
- The evidence summary now:
  - Groups attached evidence by release candidate, browser E2E, operations,
    hardware, FBR, PSP, security, or general evidence.
  - Extracts status, exit code, run ID, scope, base URL, evidence directory,
    start time, and finish time from attached `summary.md` files.
  - Parses `status.tsv` files and summarizes passed, failed, and skipped check
    counts with per-check messages.
  - Copies only non-secret lines from `env-summary.txt` files.
  - Adds approver checklist focus items for release, browser E2E, operations,
    and secret-handling review.
- Added the generated `evidence-summary.md` reference to the sign-off package
  README and `evidence-manifest.json`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Local sign-off package smoke run passes with temporary release/E2E/ops
  evidence files.
- Generated `evidence-summary.md` includes run summaries, status-table counts,
  and non-secret environment snapshots.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- The summary extractor is ready, but real approver value depends on executing
  release-candidate, E2E, and operations harnesses against live staging.
- It summarizes text evidence only; screenshots, videos, PDFs, and hardware
  attachments are fingerprinted but not visually summarized.
- PSP/FBR and physical hardware certification still require real provider and
  device evidence.

### Next Iteration

- Add release package guardrails that fail or warn when required evidence groups
  are missing for a target environment.
- Execute the full release-candidate gate and sign-off pack against a prepared
  staging stack.
- Continue direct POS UI click-through selectors and external certification
  evidence workflows.

## Iteration 34: Sign-Off Required Evidence Guardrails

Status: Completed

Date: 2026-06-05

### Completed

- Added required evidence group guardrails to
  `scripts/generate_signoff_pack.py`.
- Operators can now require sign-off evidence groups through:
  - Repeated `--required-evidence-group` arguments.
  - `TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS`, such as
    `release,e2e,ops,security,hardware,fbr,psp`.
- Added group alias normalization:
  - `release`, `release-candidate`, and `rc` map to `Release Candidate`.
  - `e2e`, `browser`, and `playwright` map to `Browser E2E`.
  - `ops` maps to `Operations`.
- Added `TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1` and
  `--strict-required-evidence` so missing groups can fail the command after the
  package is written.
- The package README, `evidence-summary.md`, and `evidence-manifest.json` now
  show required groups, missing groups, strict/warn mode, and group counts.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Local sign-off package smoke passes with required release/E2E/ops evidence
  groups present.
- Strict guardrail smoke exits non-zero when a required PSP group is missing,
  after writing the package and missing-group metadata.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Required evidence group selection is operator-driven; production policy still
  needs final owner decisions for exactly which groups are mandatory per release
  type.
- Guardrails verify attached evidence categories, not semantic certification
  quality inside PSP/FBR/hardware documents.
- Production sign-off still depends on live staging execution and real external
  provider/device evidence.

### Next Iteration

- Add machine-readable release readiness decision output from the sign-off
  package for CI/CD and release dashboards.
- Execute full staging release-candidate and sign-off flows once staging
  credentials, PSP/FBR samples, and hardware evidence are available.
- Continue direct cashier POS UI selector coverage.

## Iteration 35: Machine-Readable Release Readiness Decision

Status: Completed

Date: 2026-06-05

### Completed

- Added `release-readiness.json` generation to
  `scripts/generate_signoff_pack.py`.
- The readiness file now includes:
  - Package ID, target environment, git branch, and git head.
  - `decision` values of `ready`, `warning`, or `blocked`.
  - `ci_status` values of `pass`, `pass_with_warnings`, or `fail`.
  - Blockers and warnings derived from missing required evidence groups,
    non-passing `summary.md` statuses, failed status-table checks, skipped
    checks, and missing attached evidence.
  - Evidence group counts, required groups, missing groups, strict mode,
    summary reviews, and parsed check rows.
- Linked `release-readiness.json` from the generated sign-off package README.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Local sign-off package smoke produces `decision=warning` when operations
  evidence includes a skipped restore check.
- Strict missing-group smoke produces `decision=blocked` and exits non-zero
  when required PSP evidence is missing.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- CI/CD is not yet wired to consume `release-readiness.json`.
- Warning and blocker policy still needs final production release-owner
  thresholds.
- Real readiness still depends on live staging execution, PSP/FBR provider
  evidence, and physical hardware certification.

### Next Iteration

- Add CI/CD release-readiness check target that can fail builds on
  `decision=blocked`.
- Continue direct cashier POS UI selectors for product search, cart, payment,
  receipt print, refund form, and customer-display assertions.
- Prepare staging execution commands for full release-candidate, E2E,
  operations, sign-off, and readiness JSON collection.

## Iteration 36: Release Readiness CI Checker

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/check_release_readiness.py` for CI/CD and release-terminal
  gating.
- The checker:
  - Reads `release-readiness.json`.
  - Prints package ID, target environment, git head, decision, CI status,
    blockers, and warnings.
  - Exits `1` for `decision=blocked` or `ci_status=fail`.
  - Supports `TIJARA_RELEASE_FAIL_ON_WARNING=1` or `--fail-on-warning` to fail
    warnings during strict release drills.
  - Exits `2` for missing, unreadable, or unknown readiness JSON.
- Added operator shortcuts:
  - `make check-release-readiness READINESS=...`
  - `npm run release:readiness -- <path>`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Readiness checker exits `0` for the warning sample by default.
- Readiness checker exits `1` for the warning sample with
  `TIJARA_RELEASE_FAIL_ON_WARNING=1`.
- Readiness checker exits `1` for the blocked sample.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- GitHub Actions or deployment pipeline YAML is not yet wired to call the
  readiness checker.
- Release-owner policy still needs a final decision on whether warning should
  fail every production release.
- Live staging evidence and external PSP/FBR/hardware certifications are still
  required before true production approval.

### Next Iteration

- Wire release readiness into CI/CD or release-candidate automation.
- Continue direct cashier POS UI selector coverage.
- Execute staging release evidence once staging credentials and external
  provider/device evidence are available.

## Iteration 37: CI Release Readiness Wiring

Status: Completed

Date: 2026-06-05

### Completed

- Wired `.github/workflows/tijara-ci.yml` into the release-readiness flow:
  - Runs `TIJARA_RELEASE_RUN_ID=ci-local TIJARA_RELEASE_CHECKS=local make
    release-candidate`.
  - Generates a strict CI sign-off package from
    `deploy/runtime/release-evidence/ci-local`.
  - Requires the `Release Candidate` evidence group.
  - Runs `make check-release-readiness` against
    `deploy/runtime/signoff-packages/ci-local/release-readiness.json`.
  - Uploads release evidence and sign-off package artifacts as
    `tijara-ci-release-evidence`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Local CI-equivalent release gate passes with temporary evidence output.
- Local CI-equivalent sign-off package generation passes with strict release
  evidence requirement.
- Local CI-equivalent readiness check exits `0`.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- The CI wiring proves local release readiness only; it does not run live
  staging browser E2E, Odoo transaction tests, monitoring, restore, load,
  dependency, or container checks.
- Staging and production deployment pipelines still need environment-specific
  release gates, artifact retention policy, approvals, rollback automation, and
  secret-manager integration.
- External PSP/FBR/hardware certification evidence is still pending.

### Next Iteration

- Add a staging release evidence runbook script that sequences full release
  candidate, E2E, ops, sign-off package generation, readiness check, and
  artifact paths.
- Continue direct cashier POS UI selector coverage.
- Prepare production deployment/rollback automation once staging evidence is
  available.

## Iteration 38: Staging Release Sign-Off Orchestrator

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_staging_release_signoff.sh` as a one-command staging
  release evidence orchestrator.
- The wrapper:
  - Keeps release, E2E, operations, sign-off package, readiness JSON, and
    orchestration evidence under one run ID.
  - Runs `make release-candidate` with configurable
    `TIJARA_STAGING_RELEASE_CHECKS` defaulting to `full`.
  - Passes shared E2E and operations evidence directories into the nested
    guarded staging runners.
  - Generates a sign-off package with configurable required evidence groups.
  - Runs the release-readiness checker with configurable warning policy.
  - Continues through sign-off and readiness even if an earlier step fails, so
    blocked releases still produce complete evidence and artifact paths.
  - Writes orchestration `summary.md`, `status.tsv`, `env-summary.txt`, and
    per-step logs under `deploy/runtime/staging-release/<run-id>/`.
- Added operator shortcuts:
  - `make staging-release-signoff`
  - `npm run release:staging-signoff`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_staging_release_signoff.sh` passes.
- Local smoke with temporary runtime root and local release checks passes.
- Smoke-generated readiness JSON returns `decision=ready` and `ci_status=pass`.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Full staging execution still needs a seeded staging Odoo stack, POS E2E
  credentials, monitoring endpoints, backup artifact, k6, Trivy, Docker test
  access, and strict ops settings.
- The orchestrator sequences the release evidence, but it does not create
  external PSP/FBR/hardware evidence by itself.
- Production deployment and rollback automation still need to consume the
  staging-ready package.

### Next Iteration

- Add production deployment/rollback evidence templates or automation hooks that
  consume the staging sign-off package.
- Continue direct cashier POS UI selector coverage.
- Prepare real staging execution once credentials and hardware/provider evidence
  are available.

## Iteration 39: Production Deployment Gate Evidence

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_production_deployment_gate.py` to consume a staging
  sign-off `release-readiness.json` before production cutover.
- The gate now records:
  - Release readiness decision and CI status.
  - Backup reference.
  - Rollback reference.
  - Monitoring reference.
  - Release approver.
  - Sign-off package path.
  - Deployment blockers and warnings.
- For `TIJARA_DEPLOYMENT_TARGET=production`, backup, rollback, monitoring,
  approver, and sign-off package evidence are required by default.
- The gate writes:
  - `deployment-decision.json`.
  - `status.tsv`.
  - `env-summary.txt`.
  - `summary.md`.
  - `pre-cutover-checklist.md`.
  - `rollback-checklist.md`.
- Added operator shortcuts:
  - `make production-deployment-gate READINESS=...`
  - `npm run release:deployment-gate -- <path>`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Production deployment gate smoke exits `0` with ready readiness JSON plus
  backup, rollback, monitoring, approver, and sign-off package refs.
- Production deployment gate smoke exits non-zero when required backup,
  rollback, monitoring, and approver refs are missing.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- The gate records deployment readiness evidence; it does not execute live
  infrastructure rollout or rollback commands.
- Production approval policy still needs real owners, artifact retention rules,
  and incident/escalation contacts.
- Live staging sign-off, external PSP/FBR evidence, and physical hardware
  certification are still required before production cutover can be approved.

### Next Iteration

- Add production rollback execution hooks or deployment provider adapters after
  the deployment target is chosen.
- Continue direct cashier POS UI selector coverage.
- Execute staging and deployment gate flows with real evidence when external
  credentials and devices are available.

## Iteration 40: Production Rollback Execution Hooks

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_production_rollback.py` to consume
  `deployment-decision.json` from the production deployment gate.
- Added dry-run-first rollback providers:
  - `manifest` for manual/provider-specific rollback review.
  - `docker-compose` for Compose service rollback command evidence with
    `ODOO_IMAGE` rollback-reference injection by default.
  - `kubernetes` for Kubernetes deployment image rollback command evidence.
- Added safety controls:
  - Rollback is dry-run unless `TIJARA_ROLLBACK_EXECUTE=1` is set.
  - Live command execution also requires `CONFIRM_PRODUCTION_ROLLBACK=YES`.
  - Missing rollback references block the rollback evidence run.
- The rollback run writes:
  - `rollback-decision.json`.
  - `status.tsv`.
  - `env-summary.txt`.
  - `summary.md`.
  - Per-step command logs.
- Added operator shortcuts:
  - `make production-rollback DEPLOYMENT_GATE=...`
  - `npm run release:rollback -- <path>`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Manifest provider dry-run smoke exits `0` and writes rollback evidence.
- Docker Compose provider dry-run smoke exits `0` and writes expected command
  evidence.
- Kubernetes provider dry-run smoke exits `0` and writes expected command
  evidence.
- Execute-mode smoke without `CONFIRM_PRODUCTION_ROLLBACK=YES` exits non-zero.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Rollback execution has provider hooks, but live provider execution still needs
  a real deployment target, credentials, and production approval.
- Docker Compose rollback assumes the deployment config has already been pointed
  at the rollback image or package reference.
- Kubernetes rollback covers image rollback; database restore and schema
  rollback still require operator-controlled restore approval.

### Next Iteration

- Add direct cashier POS UI selector coverage for product search, cart,
  payment, receipt print, refund form, and customer display.
- Add deployment provider-specific production smoke commands after target
  infrastructure is selected.
- Run staging and rollback dry-run gates with real release evidence.

## Iteration 41: Direct Cashier POS UI Click-Through Coverage

Status: Completed

Date: 2026-06-05

### Completed

- Added `tests/e2e/pos-direct-ui-clickthrough.spec.mjs`.
- The new opt-in browser spec covers:
  - Opening the real POS UI from `pos.config.open_ui`.
  - Searching the seeded product by name.
  - Clicking the product to add it to the cart.
  - Navigating to the payment screen.
  - Optionally selecting the seeded payment method.
  - Optionally validating a real browser sale and clicking receipt print.
  - Optionally opening the refund form, filling the seeded invoice barcode, and
    clicking the scan action.
- Added staging toggles:
  - `TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1`.
  - `TIJARA_RUN_DIRECT_POS_VALIDATE_E2E=1`.
  - `TIJARA_RUN_DIRECT_REFUND_FORM_E2E=1`.
  - `TIJARA_RUN_MOBILE_DIRECT_POS_UI_E2E=1`.
- Extended `scripts/e2e_seed.py` to print:
  - `TIJARA_E2E_PRODUCT_NAME`.
  - `TIJARA_E2E_PAYMENT_METHOD_NAME`.
- Added the direct UI spec to authenticated and full staging E2E scopes.
- Updated `README.md`, `DEPLOY.md`, `tests/e2e/README.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_staging_e2e.sh` passes.
- `bash scripts/js_check.sh` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Direct POS UI click-through still needs execution against a live seeded
  staging Odoo POS register with a permissioned POS user.
- UI selector fallbacks are intentionally broad because Odoo POS class names and
  labels vary by version/theme; live staging execution will determine whether
  more precise selectors are needed.
- Real receipt print through hardware still depends on configured bridge
  printer and physical certification.

### Next Iteration

- Execute direct POS UI click-through on staging and tighten selectors based on
  actual screenshots/traces.
- Add production provider-specific post-deployment smoke commands once target
  infrastructure is selected.
- Continue PSP/FBR/hardware certification evidence work with real provider and
  device inputs.

## Iteration 42: Production Smoke Evidence Hooks

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_production_smoke.py` for post-deploy and post-rollback
  smoke evidence.
- The smoke runner:
  - Checks `TIJARA_SMOKE_BASE_URL` root and `/web/login` when supplied.
  - Accepts repeated named endpoints with `--url name=url`.
  - Optionally consumes deployment and rollback decision JSON files.
  - Treats HTTP 2xx/3xx as pass and 4xx/5xx/unreachable endpoints as blockers
    unless non-strict mode is enabled.
  - Writes `smoke-decision.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md`.
- Added operator shortcuts:
  - `make production-smoke`
  - `npm run release:smoke`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Production smoke passes against temporary `file://` endpoints.
- Production smoke exits non-zero for an unreachable strict endpoint.
- Production smoke records warnings instead of blockers in non-strict mode.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.

### Known Gaps

- Real production smoke execution still needs live production/staging URLs,
  display slugs, customer-display slugs, and operator-approved smoke endpoints.
- The runner checks endpoint availability; workflow-level functional assertions
  still come from Playwright staging E2E and Odoo transaction tests.
- Production monitoring and alert confirmation still need real Grafana,
  Prometheus, Alertmanager, and log evidence.

### Next Iteration

- Execute staging/deployment/smoke flows against real staging infrastructure.
- Tighten direct POS UI selectors based on real Playwright traces.
- Continue PSP/FBR/hardware certification evidence work with real provider and
  device inputs.

## Iteration 43: External Certification Evidence Intake

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/collect_certification_evidence.py` for PSP, FBR, and hardware
  certification evidence intake.
- The collector:
  - Requires category-specific metadata before sign-off.
  - Rejects secret-like metadata keys such as password, token, secret, API key,
    and client secret fields.
  - Fingerprints external evidence files or directories with SHA-256 without
    copying provider/device evidence into the public repo.
  - Writes `certification-evidence.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/certification-evidence/<run-id>/`.
  - Supports strict and non-strict modes for staged dry runs versus production
    release gates.
- Added operator shortcuts:
  - `make certification-evidence`
  - `npm run certification:evidence`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md` with certification
  evidence collection and release sign-off wiring.

### Validation

- PSP evidence smoke passes and writes `decision=passed`.
- FBR evidence smoke passes and writes `decision=passed`.
- Hardware evidence smoke passes and writes `decision=passed`.
- Secret-like PSP metadata smoke exits non-zero and writes `decision=failed`.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/collect_certification_evidence.py` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Real PSP certification still needs provider UAT/live evidence from JazzCash,
  Easypaisa, Stripe, bank, or another selected PSP.
- FBR production readiness still needs certified provider credentials, sandbox
  approval, live API compliance evidence, and tax-owner sign-off.
- Hardware production readiness still needs physical device evidence for each
  printer, scanner, scale, cash drawer, customer display, and label printer
  model used by tenants.
- Release sign-off package generation must be run with the real certification
  evidence directories included in `TIJARA_SIGNOFF_EVIDENCE_PATHS`.

### Next Iteration

- Add provider-specific PSP reconciliation/certification adapters for native
  signatures, refunds, chargebacks, and settlement batches.
- Add FBR certified-provider sandbox/live adapter hardening once the provider
  endpoint and credentials are available.
- Add device-profile certification records for real printer, drawer, scanner,
  scale, and display models.

## Iteration 44: PSP Provider Readiness Adapter Matrix

Status: Completed

Date: 2026-06-05

### Completed

- Added `tijara.saas.payment.provider.adapter` as a reusable provider adapter
  service for manual/bank, JazzCash, Easypaisa, Stripe, and generic PSP flows.
- The adapter exposes:
  - Redacted provider readiness reports with webhook route, native signature
    requirement, secret-presence status, settlement parser profile, event
    coverage, and certification status.
  - Provider contract metadata for payment, settlement, refund, and chargeback
    fields.
  - Signature-aware payload validation that returns normalized provider values
    before webhook application.
  - Provider-specific settlement parser profile lookup.
- Payment settlement batches now auto-select provider-specific parser profiles
  for JazzCash, Easypaisa, Stripe, manual bank, and generic provider statements.
- Added Odoo transaction-test coverage for:
  - Redacted Stripe provider readiness with native signatures required.
  - Signed Stripe refund payload validation through the adapter.
  - Missing JazzCash native signature secret as a failed readiness condition
    when native signatures are required.
  - Easypaisa default settlement parser selection.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  addons/tijara_saas_control/models/payment_provider_adapter.py
  addons/tijara_saas_control/models/payment_settlement.py
  addons/tijara_saas_control/tests/test_saas_enforcement.py` passes.
- `make test-odoo` was attempted in the sandbox and failed on Docker socket
  permissions.
- Escalated `make test-odoo` reached Odoo/Postgres, but the local Docker
  environment failed with Postgres password authentication for user `odoo`.

### Known Gaps

- Odoo transaction tests still need a correctly configured local/staging
  Docker secret set before they can provide final execution evidence for this
  adapter iteration.
- PSP readiness reports still need real provider certification references and
  approved status values for JazzCash, Easypaisa, Stripe, or the selected bank
  provider.
- Provider adapters still need real settlement-file fixtures from contracted
  PSPs to confirm exact field mapping and reconciliation tolerances.

### Next Iteration

- Fix the local/staging Odoo test environment credential mismatch and rerun the
  SaaS/PSP transaction tests.
- Add provider settlement fixture smoke tests for JazzCash, Easypaisa, and
  Stripe statement imports.
- Extend sign-off evidence packaging to include provider readiness JSON from
  staging.

## Iteration 45: Odoo Test Database Credential Preflight

Status: Completed

Date: 2026-06-05

### Completed

- Added a redacted database credential preflight to `scripts/run_odoo_tests.sh`.
- The preflight:
  - Runs before the Odoo module test boot.
  - Uses the same Compose env files and Odoo service environment as the real
    Odoo test run.
  - Verifies PostgreSQL authentication with `ODOO_DB_HOST`, `ODOO_DB_PORT`,
    `ODOO_DB_USER`, `ODOO_DB_PASSWORD`, and `POSTGRES_DB`.
  - Prints only host/user/database and error class, never password values.
  - Explains the common local Docker volume mismatch when env passwords are
    changed after the Postgres volume was created.
  - Can be bypassed only for diagnostics with `TIJARA_SKIP_DB_PREFLIGHT=1`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_odoo_tests.sh` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- Escalated `make test-odoo` now fails early with a clear redacted database
  credential preflight message instead of a long Odoo stack trace.

### Known Gaps

- The active local Docker Postgres volume still rejects the configured Odoo
  database password for user `odoo`.
- Full Odoo transaction tests are still blocked until the active database role
  password is rotated to match the secret source, or the local database volume
  is intentionally recreated for development.

### Next Iteration

- Add provider settlement fixture smoke tests that can run without a live Odoo
  database, then run the Odoo versions after the database credential mismatch is
  fixed.
- Add a staging provider-readiness evidence exporter so sign-off packages can
  consume PSP readiness JSON directly.
- Continue FBR certified-provider adapter hardening.

## Iteration 46: PSP Settlement Fixture Smoke

Status: Completed

Date: 2026-06-05

### Completed

- Added committed PSP settlement fixtures for:
  - JazzCash merchant statement v1.
  - Easypaisa merchant statement v1.
  - Stripe balance transaction v1.
- Each fixture includes payment, refund, chargeback, and settlement examples.
- Added `scripts/psp_settlement_fixture_smoke.py` as a standalone validator that
  does not require a live Odoo database.
- The smoke validator:
  - Loads JSON and CSV provider statement fixtures.
  - Infers the provider parser profile from the fixture name.
  - Checks secret-like key safety.
  - Confirms required event coverage for payment, refund, chargeback, and
    settlement.
  - Normalizes provider event references, transaction ids, gross amount, fee,
    net amount, event type, and line hashes.
  - Writes `psp-fixture-smoke.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/psp-fixture-smoke/<run-id>/`.
- Added operator shortcuts:
  - `make psp-fixture-smoke`
  - `npm run psp:fixture-smoke`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `python3 scripts/psp_settlement_fixture_smoke.py --run-id fixture-smoke`
  passes.
- `make psp-fixture-smoke` passes.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/psp_settlement_fixture_smoke.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Fixtures are representative open-source samples, not certified provider
  production statements.
- Real PSP certification still needs provider UAT/live fixtures and settlement
  file sign-off from JazzCash, Easypaisa, Stripe, bank, or the selected PSP.
- Odoo transaction tests for importing the fixtures remain blocked until the
  local/staging database credential mismatch is fixed.

### Next Iteration

- Add a provider-readiness evidence exporter so staging can write PSP readiness
  JSON into release sign-off packages.
- Add Odoo transaction tests that import these fixtures once the database
  credential mismatch is resolved.
- Continue FBR certified-provider adapter hardening.

## Iteration 47: PSP Readiness Evidence Exporter

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/export_psp_readiness.py` for redacted PSP provider readiness
  evidence.
- The exporter:
  - Reads `PROVIDER_CONTRACTS` directly from the committed Odoo provider adapter
    source using Python AST, so it does not need Odoo imports or a live
    database.
  - Supports manual/bank, JazzCash, Easypaisa, Stripe, and generic PSP
    provider profiles.
  - Records webhook route, settlement parser profile, native signature
    requirement, secret-presence status, event coverage, certification
    reference/status, refund fields, chargeback fields, and settlement fields.
  - Accepts `--secret-present provider=true`, `--certification-reference
    provider=value`, and `--certification-status provider=approved` for
    staging evidence without printing secret values.
  - Writes `psp-readiness.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/psp-readiness/<run-id>/`.
  - Fails when native signatures are required but secret presence is not
    confirmed, unless non-strict mode is enabled.
- Added operator shortcuts:
  - `make psp-readiness-evidence`
  - `npm run psp:readiness`
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Default readiness export passes with warnings when live PSP certifications
  are not supplied.
- Supplied Stripe readiness export passes with native signatures required,
  secret presence confirmed, and certification status approved.
- JazzCash readiness export fails when native signatures are required and
  secret presence is not confirmed.
- `make psp-readiness-evidence` passes with warning decision.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_psp_readiness.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- PSP readiness evidence still needs real staging secret-presence confirmation
  and provider certification references from contracted PSPs.
- The exporter proves readiness metadata and contract coverage; live webhook,
  settlement, refund, and chargeback certification still require provider UAT
  or live evidence.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Extend the sign-off package generator to summarize PSP readiness evidence as
  a first-class PSP evidence source.
- Continue FBR certified-provider adapter hardening.
- Add staging/live PSP provider fixture imports after database credentials are
  corrected.

## Iteration 48: PSP Readiness Sign-Off Extraction

Status: Completed

Date: 2026-06-05

### Completed

- Enhanced `scripts/generate_signoff_pack.py` to parse attached
  `psp-readiness.json` evidence.
- `evidence-summary.md` now includes a dedicated PSP Readiness Evidence section
  with:
  - PSP readiness decision.
  - CI status.
  - Native signature requirement.
  - Provider decision.
  - Secret-presence confirmation.
  - Certification reference/status presence.
  - Settlement parser profile.
- `release-readiness.json` now includes `psp_readiness_reviews` with
  provider-level PSP readiness details for CI dashboards and release
  automation.
- Release readiness decisions now treat failed PSP readiness manifests or
  failed provider decisions as blockers, and warning PSP readiness/provider
  decisions as warnings.
- Improved `status.tsv` parsing so normal three-column evidence status tables
  keep their check messages in `release-readiness.json`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Generated clean Stripe PSP readiness evidence with native signatures required,
  secret presence confirmed, and certification status approved.
- Generated a sign-off package with PSP evidence required in strict mode.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes `psp_readiness_reviews`.
- Confirmed `evidence-summary.md` includes the PSP Readiness Evidence section.
- Confirmed three-column `status.tsv` messages are retained in
  `release-readiness.json`.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/generate_signoff_pack.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- PSP readiness extraction depends on staging teams supplying real
  `psp-readiness.json` evidence.
- Real PSP certification, settlement, refund, and chargeback evidence still
  requires provider UAT/live artifacts.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Continue FBR certified-provider adapter hardening.
- Add staging/live PSP provider fixture imports after database credentials are
  corrected.
- Add monitoring evidence extraction for production smoke and rollback packages.

## Iteration 49: FBR Readiness Evidence and Sign-Off Extraction

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/export_fbr_readiness.py` for redacted FBR certified-provider
  readiness evidence.
- The exporter:
  - Supports dry-run and live FBR adapter modes.
  - Records certification environment, certified-provider presence, HTTPS
    endpoint readiness, client-id presence, credential-reference or secret
    presence, sandbox/live reference presence, FBR POS ID, branch code, and
    signed payload hash presence.
  - Hashes endpoint values instead of exposing endpoint-sensitive detail in the
    machine-readable manifest.
  - Fails strict live/production readiness when HTTPS endpoint, provider name,
    client id, credential presence, or sandbox/live reference is missing.
  - Writes `fbr-readiness.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/fbr-readiness/<run-id>/`.
- Added operator shortcuts:
  - `make fbr-readiness-evidence`
  - `npm run fbr:readiness`
- Enhanced `scripts/generate_signoff_pack.py` to parse attached
  `fbr-readiness.json` evidence.
- `evidence-summary.md` now includes a dedicated FBR Readiness Evidence section.
- `release-readiness.json` now includes `fbr_readiness_reviews`.
- Release readiness decisions now treat failed FBR readiness as blockers and
  warning FBR readiness as warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Default FBR readiness export passes with warnings for dry-run/staging
  evidence without real certified-provider data.
- Live-ready FBR sample passes with HTTPS endpoint, provider, client id,
  credential reference, sandbox reference, POS ID, branch code, and payload hash.
- Strict live FBR sample fails when endpoint/credentials/provider/reference are
  missing.
- `make fbr-readiness-evidence` passes with warning decision.
- Generated a sign-off package with FBR evidence required in strict mode.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes `fbr_readiness_reviews`.
- Confirmed `evidence-summary.md` includes the FBR Readiness Evidence section.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_fbr_readiness.py scripts/generate_signoff_pack.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- FBR readiness evidence still needs real certified-provider endpoint,
  credentials, sandbox/live response reference, POS ID, branch code, and signed
  payload hash from staging/UAT.
- FBR live compliance still requires certified-provider API contract validation
  and tax-owner sign-off.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add monitoring evidence extraction for production smoke and rollback packages.
- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.

## Iteration 50: Monitoring Evidence Extraction

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/export_monitoring_evidence.py` for post-deploy/post-rollback
  monitoring evidence.
- The exporter:
  - Consumes production smoke decision JSON.
  - Consumes production deployment gate decision JSON.
  - Consumes rollback decision JSON.
  - Probes configured Prometheus, Alertmanager, Grafana, or custom monitoring
    endpoints.
  - Writes `monitoring-evidence.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/monitoring-evidence/<run-id>/`.
  - Defaults to warnings when evidence references or monitoring endpoints are
    not attached, and blocks on failed checks unless non-strict mode is enabled.
- Added operator shortcuts:
  - `make monitoring-evidence`
  - `npm run monitoring:evidence`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group `monitoring-evidence.json` and monitoring-labeled evidence paths as
    Operations evidence.
  - Parse attached `monitoring-evidence.json`.
  - Add `monitoring_reviews` into `release-readiness.json`.
  - Add a Monitoring Evidence section to `evidence-summary.md`.
  - Treat failed monitoring evidence as blockers and warning monitoring
    evidence as warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Monitoring exporter passes with warnings when smoke/deployment/rollback refs
  and monitoring endpoints are not attached.
- Monitoring exporter passes with deterministic file-backed smoke/deployment/
  rollback refs and endpoint probes.
- `make monitoring-evidence` passes with warning decision.
- Generated a sign-off package with Operations evidence required in strict mode
  using monitoring evidence.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes `monitoring_reviews`.
- Confirmed `evidence-summary.md` includes the Monitoring Evidence section.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_monitoring_evidence.py scripts/generate_signoff_pack.py`
  passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Real monitoring evidence still needs live Prometheus, Alertmanager, Grafana,
  smoke, deployment, and rollback decision artifacts from staging/production.
- The exporter proves evidence wiring and endpoint availability; alert firing,
  routing, and incident runbooks still need live drills.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add alert/incident runbook evidence capture for Alertmanager routing and
  backup/restore drill references.
- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.

## Iteration 51: Incident Runbook Evidence Extraction

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/export_incident_runbook_evidence.py` for production incident
  runbook readiness evidence.
- The exporter:
  - Records release, DevOps, support, business, and on-call owner presence.
  - Records alert route, incident runbook URL, backup reference, restore-drill
    reference, rollback reference, and monitoring evidence reference presence.
  - Rejects secret-like metadata keys.
  - Defaults to non-strict warning mode for local/staging evidence and supports
    `--strict` for production gates.
  - Writes `incident-runbook-evidence.json`, `status.tsv`,
    `env-summary.txt`, and `summary.md` under
    `deploy/runtime/incident-runbooks/<run-id>/`.
- Added operator shortcuts:
  - `make incident-runbook-evidence`
  - `npm run incident:runbook`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group incident runbook evidence as Operations evidence.
  - Parse attached `incident-runbook-evidence.json`.
  - Add `incident_runbook_reviews` into `release-readiness.json`.
  - Add an Incident Runbook Evidence section to `evidence-summary.md`.
  - Treat failed incident runbook evidence as blockers and warning evidence as
    warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Strict empty incident runbook export fails with required owner/reference
  blockers.
- Non-strict empty incident runbook export writes warning evidence.
- Strict supplied incident runbook export passes.
- `make incident-runbook-evidence` passes with warning decision.
- Generated a sign-off package with Operations evidence required in strict mode
  using incident runbook evidence.
- Confirmed `release-readiness.json` includes `incident_runbook_reviews`.
- Confirmed `evidence-summary.md` includes the Incident Runbook Evidence
  section.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_incident_runbook_evidence.py scripts/generate_signoff_pack.py`
  passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Real incident readiness still needs named production owners, real on-call
  contacts, Alertmanager route, runbook URL, backup, restore-drill, rollback,
  and monitoring evidence references.
- Alert firing/routing and incident communications still need live drills.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.
- Add load-test evidence extraction and sign-off parsing.

## Iteration 52: Load Test Evidence Extraction

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/export_load_evidence.py` for k6/load-test release evidence.
- The exporter:
  - Reads k6 `--summary-export` JSON when attached.
  - Accepts explicitly supplied p95 duration, failure-rate, and checks-rate
    metrics for deterministic dry-runs.
  - Applies configurable thresholds for p95 duration, failure rate, and k6
    checks pass rate.
  - Supports strict production blocking and non-strict staging warning mode.
  - Writes `load-evidence.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/load-evidence/<run-id>/`.
- Added operator shortcuts:
  - `make load-evidence`
  - `npm run load:evidence`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group load evidence as Operations evidence.
  - Parse attached `load-evidence.json`.
  - Add a Load Test Evidence section to `evidence-summary.md`.
  - Add `load_reviews` into `release-readiness.json`.
  - Treat failed load evidence as blockers and warning load evidence as
    release warnings.
  - Treat generic evidence `summary.md` warning statuses as warnings instead of
    automatic blockers.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Strict passing load evidence export succeeds from a k6-style summary fixture.
- Non-strict load evidence export succeeds with warning decision when k6 summary
  and metrics are not attached.
- Strict failing load evidence export exits non-zero with a p95 duration blocker.
- `make load-evidence` passes and writes local warning evidence.
- Generated a sign-off package with Operations evidence required in strict mode
  using passing load evidence.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes `load_reviews`.
- Confirmed `evidence-summary.md` includes the Load Test Evidence section,
  base URL, p95 duration, failure-rate, and checks-rate metrics.
- Generated a warning load evidence sign-off package and confirmed
  `decision=warning` with `ci_status=pass_with_warnings`.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_load_evidence.py scripts/generate_signoff_pack.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Real load evidence still needs k6 execution against seeded staging and
  production-like traffic profiles.
- The staging operations harness still needs to export k6 summary JSON into the
  structured load evidence exporter automatically.
- Load targets, thresholds, VU counts, and durations still need production
  release-owner approval per customer size and vertical.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Wire `scripts/run_staging_ops_checks.sh` load checks into
  `scripts/export_load_evidence.py` so grouped operations evidence includes
  structured load decisions automatically.
- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.

## Iteration 53: Operations Load Evidence Automation

Status: Completed

Date: 2026-06-05

### Completed

- Enhanced `scripts/run_staging_ops_checks.sh` so the `load` check now:
  - Runs k6 with `--summary-export`.
  - Writes `k6-load-summary.json` inside the operations evidence directory.
  - Calls `scripts/export_load_evidence.py` automatically.
  - Stores nested structured load evidence under
    `deploy/runtime/ops-evidence/<run-id>/load-evidence/`.
  - Records separate `load-smoke` and `load-evidence` rows in `status.tsv`.
  - Links the nested `load-evidence.json` from the operations summary.
  - Emits warning-mode load evidence when k6 is unavailable in non-strict mode.
  - Fails both load smoke and load evidence in strict mode when the load step is
    blocked or over threshold.
- Updated `scripts/export_load_evidence.py` to support both k6 summary formats:
  nested `values` metrics and direct metric fields such as `p(95)` and
  `value`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_staging_ops_checks.sh` passes.
- Forced no-k6 PATH run passes in non-strict mode and writes warning
  `load-evidence.json`.
- Real k6 ops load run against local Odoo passes outside the sandbox and writes:
  - `status.tsv` with passing `load-smoke` and `load-evidence` rows.
  - `k6-load-summary.json`.
  - nested `load-evidence/load-evidence.json` with `decision=passed`.
  - p95 duration, failure-rate, and checks-rate metrics.
- Generated a sign-off package from the ops evidence directory with Operations
  required in strict mode.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes nested ops `load_reviews`.
- Confirmed `evidence-summary.md` includes Load Test Evidence from the nested
  ops evidence directory.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_load_evidence.py scripts/generate_signoff_pack.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Full `make ops-staging` still needs a prepared staging stack with monitoring,
  dependency/container scan tools, restore backup artifact, and production-like
  load target.
- The local k6 pass required unsandboxed local TCP access; CI/staging runners
  need network access to the target Odoo URL.
- Load profiles are still smoke-level and need larger vertical-specific
  profiles for superstore, pharmacy, restaurant, grocery, bakery, and cloth
  pilots.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add larger open-source k6 load profiles for POS checkout, public display, and
  kiosk endpoints, with evidence export support.
- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.

## Iteration 54: Enterprise Surface Load Profiles

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/load_enterprise_surfaces.k6.js`.
- The enterprise k6 profile:
  - Loads the POS/Odoo shell through `TIJARA_POS_LOAD_URL` or `/odoo`.
  - Loads public display shell and data when `TIJARA_DISPLAY_SLUG` is set.
  - Loads kiosk shell and data when `TIJARA_KIOSK_SLUG` is set.
  - Loads customer-display data when `TIJARA_CUSTOMER_DISPLAY_SLUG` is set.
  - Supports authenticated cookies through `TIJARA_LOAD_AUTH_COOKIE` or
    `TIJARA_LOAD_COOKIE` for staging-only protected URLs.
  - Keeps kiosk checkout POST load disabled by default.
  - Enables kiosk checkout order creation only when
    `TIJARA_RUN_KIOSK_CHECKOUT_LOAD=1`.
  - Uses open-source k6 thresholds from `TIJARA_LOAD_MAX_P95_MS`,
    `TIJARA_LOAD_MAX_FAIL_RATE`, and `TIJARA_LOAD_MIN_CHECKS_RATE`.
- Added `scripts/run_load_profile.sh` to run reusable load profiles, preserve
  k6 summary JSON, and export structured load evidence even when k6 exits
  non-zero.
- Added operator shortcuts:
  - `make load-profile`
  - `make load-enterprise-surfaces`
  - `npm run load:profile`
  - `npm run load:enterprise`
- Enhanced `scripts/export_load_evidence.py` and
  `scripts/generate_signoff_pack.py` so load evidence carries
  `profile_name`, and sign-off summaries show the profile name in
  `load_reviews`.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `bash -n scripts/run_load_profile.sh` passes.
- `k6 inspect scripts/load_enterprise_surfaces.k6.js` passes.
- `k6 inspect scripts/load_smoke.k6.js` passes.
- Short `enterprise-surfaces` run against local Odoo passes outside the sandbox
  with `TIJARA_LOAD_VUS=1` and `TIJARA_LOAD_DURATION=5s`.
- Generated load evidence includes `profile_name=enterprise-surfaces`,
  `decision=passed`, p95 duration, failure-rate, and checks-rate metrics.
- Generated a sign-off package from the enterprise profile evidence with
  Operations required in strict mode.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes `load_reviews` with
  `profile_name=enterprise-surfaces`.
- Confirmed `evidence-summary.md` includes the Load Test Evidence profile name
  and metrics.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_load_evidence.py scripts/generate_signoff_pack.py` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- The enterprise profile is still a staging-safe surface profile; full POS
  checkout load needs a seeded authenticated POS route/session and cashier test
  policy.
- Kiosk checkout load is intentionally opt-in because it creates real kiosk
  orders and optional POS orders on the target tenant.
- Vertical-specific load mixes for superstore, pharmacy, restaurant, grocery,
  bakery, and cloth pilots still need production traffic assumptions.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add a staging load-profile evidence matrix that records approved VU/duration
  thresholds by tenant size and vertical.
- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.

## Iteration 55: Load Profile Approval Matrix Evidence

Status: Completed

Date: 2026-06-05

### Completed

- Added `deploy/config/load-profile-matrix.json` as a secret-free draft matrix
  for tenant-size and vertical-specific load expectations.
- The matrix covers:
  - Small pilot retail for cloth, electronics, and garments.
  - Medium superstore and grocery.
  - Restaurant kiosk/counter.
  - Bakery rush.
  - Pharmacy steady regulated pilot.
  - Large multi-branch enterprise.
- Added `scripts/export_load_profile_matrix.py`.
- The exporter:
  - Validates required profile fields.
  - Rejects secret-like profile keys.
  - Validates VU counts, k6 duration syntax, p95 thresholds, failure-rate
    thresholds, and checks-rate thresholds.
  - Records approval owner/reference presence.
  - Defaults to warning mode for local/staging and supports strict blocking for
    production release.
  - Writes `load-profile-matrix.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/load-profile-matrix/<run-id>/`.
- Added operator shortcuts:
  - `make load-profile-matrix-evidence`
  - `npm run load:matrix`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group load profile matrix evidence as Operations evidence.
  - Parse attached `load-profile-matrix.json`.
  - Add a Load Profile Matrix Evidence section to `evidence-summary.md`.
  - Add `load_matrix_reviews` into `release-readiness.json`.
  - Treat failed matrix evidence as blockers and warning matrix evidence as
    release warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Default matrix evidence export succeeds with warning decision when approval
  owner/reference are not supplied.
- Strict matrix evidence export succeeds when approval owner/reference are
  supplied.
- Generated a sign-off package with Operations evidence required in strict mode
  using approved matrix evidence.
- Confirmed `release-readiness.json` decision is `ready`.
- Confirmed `release-readiness.json` includes `load_matrix_reviews`.
- Confirmed `evidence-summary.md` includes the Load Profile Matrix Evidence
  section.
- `make load-profile-matrix-evidence` passes and writes warning evidence when
  release approval metadata is not supplied.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_load_profile_matrix.py scripts/generate_signoff_pack.py`
  passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- The matrix is a draft baseline until pilot traffic assumptions are signed off
  by release owners per customer size and vertical.
- The profiles still need execution against seeded staging tenants with
  monitoring and rollback evidence attached.
- Kiosk checkout load remains opt-in because it creates transactional records.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.
- Add a release evidence bundle that combines load profile matrix, enterprise
  surface load evidence, monitoring, incident runbook, and production smoke
  evidence under one operations run ID.

## Iteration 56: Operations Release Evidence Bundle

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/run_operations_release_bundle.py`.
- The bundle runner:
  - Uses one operations run ID across nested evidence generators.
  - Runs load profile matrix evidence.
  - Runs enterprise surface load evidence.
  - Runs production smoke evidence.
  - Runs monitoring evidence and attaches the smoke decision reference.
  - Runs incident runbook evidence and attaches the monitoring evidence
    reference.
  - Continues after child evidence failures so release owners receive a full
    bundle instead of a partial log.
  - Writes per-step logs, nested evidence directories, `status.tsv`,
    `env-summary.txt`, `summary.md`, and `operations-release-bundle.json`
    under `deploy/runtime/operations-release-bundle/<run-id>/`.
  - Supports strict production mode through `TIJARA_OPS_BUNDLE_STRICT=1`.
  - Supports release-blocking warnings through
    `TIJARA_OPS_BUNDLE_FAIL_ON_WARNING=1`.
  - Normalizes check order so smoke runs before monitoring and monitoring runs
    before incident evidence even if the operator lists checks out of order.
- Added operator shortcuts:
  - `make operations-release-bundle`
  - `npm run ops:release-bundle`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group `operations-release-bundle.json` as Operations evidence.
  - Parse attached operations bundle evidence.
  - Add an Operations Release Bundle Evidence section to
    `evidence-summary.md`.
  - Add `operations_bundle_reviews` into `release-readiness.json`.
  - Treat failed bundle evidence as blockers and warning bundle evidence as
    release warnings.
  - Parse six-column `status.tsv` files so bundle messages show the actual
    decision text instead of the log-file column.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/run_operations_release_bundle.py scripts/generate_signoff_pack.py`
  passes.
- Warning-mode operations bundle run succeeds with all five lanes present:
  load matrix, enterprise load, smoke, monitoring, and incident runbook.
- The warning-mode bundle writes `operations-release-bundle.json`,
  `status.tsv`, `summary.md`, nested evidence directories, and per-step logs.
- Generated a sign-off package with Operations evidence required in strict mode
  using the operations bundle directory.
- Confirmed `evidence-summary.md` includes Operations Release Bundle Evidence.
- Confirmed `release-readiness.json` includes `operations_bundle_reviews`.
- Confirmed bundle evidence references load matrix, load enterprise, smoke,
  monitoring, and incident manifests.
- `make operations-release-bundle` passes in warning mode and writes the full
  bundle under a temporary output directory.
- A deliberately out-of-order bundle check list is normalized before execution.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- A production-ready bundle still needs live staging URLs, k6 network access,
  monitoring endpoints, release-owner matrix approval, incident owners,
  backup/restore/rollback references, and production smoke endpoints.
- The local dry-run intentionally produced warnings because k6 was hidden and
  owner/endpoint references were not supplied.
- Full production release should run with strict and fail-on-warning enabled.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add FBR provider response fixture smoke tests once certified-provider sample
  responses are available.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.
- Add CI/CD artifact upload and retention guidance for operations release
  bundles.

## Iteration 57: FBR Provider Response Fixture Smoke

Status: Completed

Date: 2026-06-05

### Completed

- Added committed generic certified-provider FBR response fixtures under
  `tests/fixtures/fbr_provider_responses/`.
- Added `scripts/fbr_provider_fixture_smoke.py`.
- The FBR fixture smoke:
  - Loads committed provider response fixtures without requiring a live Odoo
    database.
  - Validates accepted provider responses for success status, FBR invoice
    number, QR payload, provider invoice UUID, and certification reference.
  - Validates rejected provider responses for rejection/non-success status,
    actionable error text, and no unexpected invoice number.
  - Rejects secret-like keys in committed fixtures.
  - Writes `fbr-fixture-smoke.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/fbr-fixture-smoke/<run-id>/`.
  - Records provider, environment, fixture hashes, response hashes, accepted
    response count, and rejected response count.
- Added operator shortcuts:
  - `make fbr-fixture-smoke`
  - `npm run fbr:fixture-smoke`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Parse attached `fbr-fixture-smoke.json` evidence.
  - Add an FBR Fixture Evidence section to `evidence-summary.md`.
  - Add `fbr_fixture_reviews` into `release-readiness.json`.
  - Treat failed fixture smoke evidence as release blockers and warning fixture
    smoke evidence as release warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- `python3 scripts/fbr_provider_fixture_smoke.py --run-id fbr-fixture --output
  /private/tmp/tijara-fbr-fixture-smoke` passes with `decision=passed`.
- `make fbr-fixture-smoke` passes.
- `npm run fbr:fixture-smoke` passes.
- `python3 scripts/generate_signoff_pack.py --run-id signoff-fbr-fixture
  --output /private/tmp/tijara-signoff-fbr-fixture --evidence-path
  /private/tmp/tijara-fbr-fixture-smoke --required-evidence-group fbr
  --strict-required-evidence` passes.
- Confirmed `evidence-summary.md` includes FBR Fixture Evidence with two
  accepted and two rejected generic certified-provider responses.
- Confirmed `release-readiness.json` includes `fbr_fixture_reviews` and is
  `ready` for the focused FBR fixture evidence run.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/fbr_provider_fixture_smoke.py scripts/generate_signoff_pack.py`
  passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- Generic response fixtures are not a substitute for certified-provider
  sandbox/live payloads.
- FBR production readiness still needs real provider credentials, sandbox
  compliance sign-off, live endpoint validation, and tax/compliance owner
  approval.
- Local Odoo FBR transaction tests remain blocked until database credentials are
  corrected.

### Next Iteration

- Add CI/CD artifact upload and retention guidance for operations and
  certification evidence bundles.
- Add staging/live Odoo FBR transaction execution after database credentials are
  corrected.
- Add production-grade secret-manager and evidence-retention checks into the
  release gate.

## Iteration 58: Release Retention and Secret-Manager Evidence

Status: Completed

Date: 2026-06-05

### Completed

- Added `scripts/export_release_retention_evidence.py`.
- The retention exporter:
  - Records artifact-store, artifact-retention policy, certification-retention
    policy, secret-manager provider/reference, and secret-rotation policy
    readiness without exposing secret values.
  - Validates operational retention baselines for CI artifacts, release
    evidence, certification evidence, logs, and backups.
  - Fingerprints attached release evidence directories/files with SHA-256
    hashes and byte counts.
  - Rejects secret-like metadata keys.
  - Writes `release-retention-evidence.json`, `status.tsv`,
    `env-summary.txt`, and `summary.md` under
    `deploy/runtime/release-retention-evidence/<run-id>/`.
  - Supports strict production mode and warning-mode local execution.
- Added operator shortcuts:
  - `make release-retention-evidence`
  - `npm run release:retention`
- Enhanced `scripts/run_operations_release_bundle.py` to include a
  `retention` lane after load matrix, enterprise load, production smoke,
  monitoring, and incident runbook evidence.
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group release retention evidence as Operations evidence.
  - Parse attached `release-retention-evidence.json`.
  - Add a Release Retention Evidence section to `evidence-summary.md`.
  - Add `release_retention_reviews` into `release-readiness.json`.
  - Treat failed retention evidence as release blockers and warning retention
    evidence as release warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Strict complete retention export passes:
  `python3 scripts/export_release_retention_evidence.py --run-id
  retention-ready --output /private/tmp/tijara-retention-ready
  --target-environment production --artifact-store-reference
  s3://tijara-release-evidence/retention-ready --artifact-retention-policy-ref
  policy:release-evidence-365d --certification-retention-policy-ref
  policy:certification-evidence-365d --secret-manager-provider vault
  --secret-manager-reference vault:tijara/production
  --secret-rotation-policy-ref policy:quarterly-secret-rotation
  --ci-artifact-retention-days 30 --release-evidence-retention-days 365
  --certification-evidence-retention-days 365 --log-retention-days 30
  --backup-retention-days 30 --evidence-path
  /private/tmp/tijara-fbr-fixture-smoke --strict`.
- `make release-retention-evidence` passes in warning mode when production
  references are not supplied.
- `npm run release:retention` passes in warning mode.
- `python3 scripts/run_operations_release_bundle.py --run-id ops-retention
  --output /private/tmp/tijara-ops-retention --checks retention` passes in
  warning mode and writes a retention manifest.
- Full local operations bundle with
  `TIJARA_OPS_BUNDLE_OUTPUT=/private/tmp/tijara-ops-bundle-retention make
  operations-release-bundle` completes in warning mode and includes the
  `retention` lane.
- Generated a sign-off package with Operations evidence required in strict mode
  using the strict retention evidence directory.
- Confirmed `evidence-summary.md` includes Release Retention Evidence.
- Confirmed `release-readiness.json` includes `release_retention_reviews` and
  is `ready` for the focused complete retention evidence run.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_release_retention_evidence.py
  scripts/run_operations_release_bundle.py scripts/generate_signoff_pack.py`
  passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- The local operations bundle remains warning-mode because production URLs,
  k6-ready network/load prerequisites, incident owner references, monitoring
  endpoints, and retention/secret-manager references are not configured
  locally.
- Artifact upload still needs the final production CI/CD provider and bucket or
  object-store configuration.
- Secret-manager references now have release evidence, but production still
  needs actual provider integration, rotation jobs, and access-review evidence.
- Odoo transaction tests remain blocked by the local Docker database credential
  mismatch.

### Next Iteration

- Add CI/CD artifact retention workflow guidance or workflow hooks for the
  chosen GitHub Actions/Open-source deployment pipeline.
- Add production secret-manager integration checks for runtime configuration
  files once the target provider is selected.
- Continue staging/live FBR transaction execution after database credentials and
  certified-provider sandbox credentials are corrected.

## Iteration 59: CI Artifact Retention Workflow Hook

Status: Completed

Date: 2026-06-05

### Completed

- Enhanced `.github/workflows/tijara-ci.yml` so CI now:
  - Runs the local release-candidate gate.
  - Generates strict release retention evidence from the CI release evidence
    directory.
  - Builds the CI sign-off package with both release and operations evidence
    groups required.
  - Checks `release-readiness.json` after retention evidence is included.
  - Uploads release evidence, release retention evidence, and sign-off packages
    in one artifact.
  - Sets `retention-days: 30` and `if-no-files-found: error` on the uploaded
    artifact.
- Updated `README.md`, `DEPLOY.md`, `docs/QA_SECURITY_DEVOPS.md`, and
  `PROGRESS.md`.

### Validation

- Local CI-equivalent release gate passes with:
  `TIJARA_RELEASE_RUN_ID=ci-retention TIJARA_RELEASE_CHECKS=local make
  release-candidate`.
- Strict CI-equivalent retention export passes for
  `deploy/runtime/release-evidence/ci-retention`.
- CI-equivalent sign-off package generation passes with:
  `TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/ci-retention,deploy/runtime/release-retention-evidence/ci-retention`
  and `TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,ops`.
- `make check-release-readiness
  READINESS=deploy/runtime/signoff-packages/ci-retention/release-readiness.json`
  exits `0` with `decision=ready` and `ci_status=pass`.
- `.github/workflows/tijara-ci.yml` parses successfully with PyYAML.
- Confirmed the workflow includes the local release retention evidence step,
  explicit artifact `retention-days: 30`, `if-no-files-found: error`, and the
  release retention evidence upload path.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- CI is still the public-repo baseline; production deployment still needs the
  final staging/production runner, artifact store, environment protection,
  approval gates, and rollback promotion flow.
- CI retention evidence uses safe GitHub Actions references, not a live
  production object store or external secret manager.
- FBR certified-provider live credentials and Odoo transaction execution remain
  external blockers.

### Next Iteration

- Add runtime secret-manager configuration checks that validate production env
  templates are reference-only and no secret values are committed.
- Add deployment environment protection/runbook evidence for staging and
  production approval gates.
- Continue staging/live FBR transaction execution when credentials are
  available.

## Iteration 60: Runtime Secret Manager Evidence

Status: Completed

Date: 2026-06-05

### Completed

- Removed `FBR_CLIENT_SECRET` from `.env.example` so the central non-secret
  template no longer declares a secret-like assignment.
- Added `scripts/export_secret_manager_evidence.py`.
- The secret-manager evidence exporter:
  - Validates that non-secret env templates do not define secret-like keys.
  - Validates that `secrets/.env.secrets.example` contains required secret
    placeholders.
  - Validates secret example values are placeholders or references, not real
    values.
  - Confirms critical Compose secrets use required `:?` guards.
  - Confirms the Odoo startup script requires DB/master passwords and refuses
    placeholder production secrets.
  - Confirms no non-example files are present under `secrets/`.
  - Records production secret-manager provider/reference, rotation policy, and
    access-review references without copying secret values.
  - Writes `secret-manager-evidence.json`, `status.tsv`, `env-summary.txt`, and
    `summary.md` under `deploy/runtime/secret-manager-evidence/<run-id>/`.
  - Supports strict production mode and local warning mode.
- Added operator shortcuts:
  - `make secret-manager-evidence`
  - `npm run secret-manager:evidence`
- Enhanced `scripts/generate_signoff_pack.py` to:
  - Group secret-manager evidence as Security evidence.
  - Parse attached `secret-manager-evidence.json`.
  - Add a Secret Manager Evidence section to `evidence-summary.md`.
  - Add `secret_manager_reviews` into `release-readiness.json`.
  - Treat failed secret-manager evidence as release blockers and warning
    evidence as release warnings.
- Updated `README.md`, `DEPLOY.md`, and `PROGRESS.md`.

### Validation

- Strict production-reference secret-manager export passes:
  `python3 scripts/export_secret_manager_evidence.py --run-id
  secret-manager-ready --output /private/tmp/tijara-secret-manager-ready
  --target-environment production --secret-manager-provider vault
  --secret-manager-reference vault:tijara/production
  --secret-rotation-policy-ref policy:quarterly-secret-rotation
  --secret-access-review-ref review:2026-q2-production-secrets --strict`.
- `make secret-manager-evidence` passes in warning mode when production
  references are not supplied.
- `npm run secret-manager:evidence` passes in warning mode.
- Generated a sign-off package with Security evidence required in strict mode
  using the strict secret-manager evidence directory.
- Confirmed `evidence-summary.md` includes Secret Manager Evidence.
- Confirmed `release-readiness.json` includes `secret_manager_reviews` and is
  `ready` for the focused complete secret-manager evidence run.
- `PYTHONPYCACHEPREFIX=/private/tmp/tijara-pycache python3 -m py_compile
  scripts/export_secret_manager_evidence.py scripts/generate_signoff_pack.py`
  passes.
- `docker compose --env-file .env.example --env-file
  secrets/.env.secrets.example config --quiet` passes.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- The exporter verifies references and committed configuration hygiene; it does
  not connect to the production secret manager or prove runtime secret delivery.
- Production still needs actual Vault/SOPS/Kubernetes/Docker/cloud secret-manager
  integration, rotation jobs, access-review evidence, and incident procedures.
- CI does not yet require secret-manager evidence as a Security group.
- FBR certified-provider live credentials and Odoo transaction execution remain
  external blockers.

### Next Iteration

- Wire secret-manager evidence into CI as a required Security evidence group.
- Add deployment environment protection/runbook evidence for staging and
  production approval gates.
- Continue staging/live FBR transaction execution when credentials are
  available.

## Iteration 61: CI Secret Manager Evidence Enforcement

Status: Completed

Date: 2026-06-05

### Completed

- Enhanced `.github/workflows/tijara-ci.yml` so CI now:
  - Generates strict secret-manager evidence after release retention evidence.
  - Requires Release, Operations, and Security evidence groups in the CI sign-off
    package.
  - Includes `deploy/runtime/secret-manager-evidence/ci-local` in the uploaded
    release evidence artifact.
- Updated `README.md`, `DEPLOY.md`, `docs/QA_SECURITY_DEVOPS.md`, and
  `PROGRESS.md`.

### Validation

- Local CI-equivalent release gate passes with:
  `TIJARA_RELEASE_RUN_ID=ci-secret-manager TIJARA_RELEASE_CHECKS=local make
  release-candidate`.
- Strict CI-equivalent retention export passes for
  `deploy/runtime/release-evidence/ci-secret-manager`.
- Strict CI-equivalent secret-manager evidence export passes for
  `deploy/runtime/secret-manager-evidence/ci-secret-manager`.
- CI-equivalent sign-off package generation passes with:
  `TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/ci-secret-manager,deploy/runtime/release-retention-evidence/ci-secret-manager,deploy/runtime/secret-manager-evidence/ci-secret-manager`
  and `TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,ops,security`.
- `make check-release-readiness
  READINESS=deploy/runtime/signoff-packages/ci-secret-manager/release-readiness.json`
  exits `0` with `decision=ready` and `ci_status=pass`.
- `.github/workflows/tijara-ci.yml` parses successfully with PyYAML.
- Confirmed the workflow includes the local secret manager evidence step, the
  `release,ops,security` required group list, and the secret-manager evidence
  upload path.
- `make validate` passes.
- 74 XML files parse successfully.
- `bash scripts/js_check.sh` passes.
- `bash scripts/security_audit.sh` passes.
- `git diff --check` passes.
- No `__pycache__` directories are present under `addons`, `scripts`, or
  `tests`.

### Known Gaps

- CI still proves only committed config hygiene and reference readiness; it does
  not connect to a live production secret manager.
- Production deployment still needs environment protection, approval gates,
  promotion/rollback runbooks, and real object-store/secret-manager wiring.
- FBR certified-provider live credentials and Odoo transaction execution remain
  external blockers.

### Next Iteration

- Add deployment environment protection/runbook evidence for staging and
  production approval gates.
- Add production runtime secret-manager connectivity checks after the target
  provider is selected.
- Continue staging/live FBR transaction execution when credentials are
  available.
