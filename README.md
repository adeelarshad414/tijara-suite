# Tijara Suite

Tijara Suite is an enterprise-grade, Pakistan-focused business platform built on
Odoo Community and open-source infrastructure. The product target is a modular
SaaS suite for POS, inventory, back office, sales, purchase, procurement,
expenses, customers, suppliers, refunds, exchanges, Urdu/English operations,
barcode/QR workflows, store hardware, self-service kiosk, customer display,
menu/deal screens, queue system, and B2B/B2C selling.
The POS billing flow includes overall bill-level discount entry by either
percentage or fixed amount, with both values kept in sync for cashier clarity
and manager audit.
The retail operations foundation also includes configurable invoice/receipt
templates, rendered Tijara POS receipt and customer invoice reports, invoice
barcode scanning for returns, scanner/printer registry metadata, and CSV
import/export for core operational data. The live browser POS receipt screen now
loads Tijara receipt profiles for cashier receipt rendering, including bilingual
header/footer content, custom HTML tokens, QR/barcode output, and return policy
text. The first local hardware bridge foundation is also included for signed
dry-run printer, scanner, cash-drawer, scale, and customer-display jobs, and the
browser POS receipt print action can submit the rendered receipt payload to a
configured local bridge receipt printer.

The first market verticals are:

- Superstores and general retail
- Grocery stores
- Bakeries
- Cloth and fabric shops
- Pharmacies
- Restaurants
- Garments and textile retail
- Electronics and appliance stores
- Wholesale and multi-branch retail

## Product Principles

- Keep the core suite public-repo friendly and open-source-first.
- Own the commercial product layer while respecting Odoo Community licensing.
- Use Odoo Community and open-source tools for core product behavior.
- Avoid Odoo Enterprise, proprietary dependencies, private assets, and
  vendor-locked services in the core suite.
- Keep each business vertical as an optional module.
- Support SaaS feature flags from the beginning.
- Keep sellable SaaS features separate even when they share one technical
  module, such as B2B sales, queue system, promotion display, and customer
  display.
- Build Pakistan localization as a first-class foundation, not a later patch.
- Favor standard Odoo models where they fit, and add custom models only where
  the Pakistani retail workflow needs them.
- Design for offline-tolerant POS, hardware integration, auditability, security,
  and production operations.

## Repository Layout

```text
addons/
  tijara_base/                 Pakistan localization foundation
  tijara_retail_core/          Retail operations, hardware, cash shifts, returns
  tijara_inventory_intelligence/ Low stock, expiry, racks, shelves, bins
  tijara_pos_pk/               POS receipt, QR, and FBR integration readiness
  tijara_pos_experience/       Kiosk, displays, promotions, queue, B2B/B2C POS
  tijara_analytics/            Dashboards, KPI history, trends, charts, reports
  tijara_saas_control/         SaaS plans, tenants, feature flags
  tijara_demo_pos/             Optional POS demo seed for cashier smoke tests
  tijara_vertical_pharmacy/    Pharmacy-specific fields and workflows
  tijara_vertical_restaurant/  Restaurant-specific table/KOT foundation
  tijara_vertical_garments/    Garments-specific product attributes
  tijara_vertical_electronics/ Electronics warranty and serial workflows
  tijara_vertical_cloth/       Fabric roll, meter sale, and tailoring fields
  tijara_vertical_superstore/  Department, aisle, shelf, pack, and promo fields
  tijara_vertical_grocery/     Perishable, loose item, PLU, and cold-chain fields
  tijara_vertical_bakery/      Bakery product and production batch foundation
deploy/
  bin/                         Runtime helpers, including Odoo config renderer
  config/                      Secret-free runtime config templates
  logging/                     Logging retention and aggregation notes
  monitoring/                  Prometheus and Blackbox Exporter baseline
  nginx/                       Reverse proxy configuration
  postgres/                    Database notes, backup hooks, restore drills
hardware-bridge/               Local shop-machine device bridge foundation
docs/                          Architecture, roadmap, analytics, inventory, QA
                               retail operations, hardware, and data exchange
secrets/                       Ignored local/staging secrets, example included
scripts/                       Operational helper scripts
tests/e2e/                     Playwright browser E2E staging scaffolds
DEPLOY.md                      Deployment, secrets, release, and rollback guide
LICENSE                        Root LGPL-3.0 project license notice
```

## Local Development

1. Copy `.env.example` to `.env`.
2. Copy `secrets/.env.secrets.example` to `secrets/.env.secrets`.
3. Change secret values before staging or production.
4. Start the stack:

```bash
make up
```

5. Open `http://localhost:8069`.
6. Create a database and install the Tijara modules from Apps, or run the suite
   install command:

```bash
make install-suite
```

Run the local scaffold validator from the project root with:

```bash
make validate
```

Production-readiness checks and scaffolds:

```bash
make test-odoo
make js-check
make security-audit
make hardware-cert-smoke
make e2e
make load-smoke
make load-enterprise-surfaces
make load-profile-matrix-evidence
make release-candidate
make certification-evidence
make psp-readiness-evidence
make psp-fixture-smoke
make fbr-readiness-evidence
make fbr-fixture-smoke
make monitoring-evidence
make incident-runbook-evidence
make release-retention-evidence
make secret-manager-evidence
make secret-runtime-evidence
make deployment-environment-evidence
make tenant-ops-evidence
make load-evidence
make operations-release-bundle
make production-ops-readiness
make ops-tool-evidence
make signoff-pack
make check-release-readiness READINESS=deploy/runtime/signoff-packages/<run-id>/release-readiness.json
make staging-release-signoff
make production-deployment-gate READINESS=deploy/runtime/signoff-packages/<run-id>/release-readiness.json
make production-rollback DEPLOYMENT_GATE=deploy/runtime/deployment-gates/<run-id>/deployment-decision.json
make production-smoke
make tenant-smoke
make tenant-rollout
```

See `DEPLOY.md` for deployment, secret handling, backups, release checks, and
rollback guidance.

## Current Status

The custom suite has passed live Odoo 19 install and upgrade smoke tests. The
`tijara_dev` database installs all 15 Tijara custom modules, seeds 21 SaaS
feature flags, includes five analytics dashboards, includes four report catalog
templates, and the Odoo service responds at `http://localhost:8069` with the web
app redirecting to `/odoo`.
The optional `tijara_demo_pos` module is also installed in the dev database for
cashier smoke-test data; it is not part of the production suite install.

The current code is an enterprise product foundation: models, security access,
menus, backend views, SaaS plans/features, Pakistan localization fields, POS
experience foundations, overall bill discount controls, configurable
invoice/receipt templates, scanner/printer configuration, invoice barcode return
scanning, CSV bulk import/export, inventory intelligence, analytics/reporting
foundations, and vertical packs are in place. The Tijara invoice/receipt
template configuration now renders through backend QWeb PDF/HTML reports for
customer invoices and POS orders, and the browser POS receipt screen consumes
the configured POS receipt profile during cashier checkout. The open-source
local hardware bridge foundation can accept signed dry-run jobs from Odoo
hardware records, and configured POS receipt printers can receive the rendered
browser receipt print payload through the bridge. The bridge now includes
adapter paths for ESC/POS receipt bytes, CUPS/raw TCP/file delivery, ZPL labels,
cash-drawer pulses, scale readings, scanner event persistence, and customer
display state output, while hardware certifications now keep physical evidence
attachments, observed serials, driver/firmware versions, operator signatures,
execution checks, bridge job ids, response codes, durations, and reproducible
evidence hashes. SaaS runtime enforcement can block B2B,
queue, promotion display, and customer display features when enabled. Public kiosk/display routes
serve menu, deal, promotion, customer-display, and queue screen payloads. Payment
settlement closeout now has finance approval actions that can create guarded
draft Odoo journal entries from configured provider clearing, fee, refund,
chargeback, write-off, and counterpart accounts, including bulk draft-move
creation from settlement batches and dispute cases. Approved refund actions can
also create customer refund credit notes and draft outbound Odoo refund
payments from configured refund journals, outstanding accounts, and customer
receivable accounts. The
kiosk route now includes a real self-ordering cart and checkout foundation that
creates auditable kiosk orders, queue tickets when the tenant has the queue
feature, and linked Odoo POS orders/payments when a kiosk profile is mapped to a
POS register and payment method. Customer-display routes can publish live
POS/customer-facing order state with lines and totals, and the POS frontend now
has a best-effort live publisher for continuous cart updates. The FBR queue now
has dry-run/live HTTP adapter modes plus certified-provider metadata,
certification environment, payload hash, and compliance status tracking.
Analytics can collect daily KPI snapshots from POS, inventory alerts, queue
tickets, and promotions.
Offline POS now includes a cashier-facing queue button, back-office conflict
review workbench, retry/cancel/duplicate/merge resolution actions, replay audit
pivots/graphs, pilot attention metrics for queue age/failure buckets/recovery
owners/runbook notes, and seeded staging exports for POS UI, receipt report,
refund barcode scan, offline review, and print-to-bridge browser harnesses.
Committed Odoo transaction/HTTP tests now cover SaaS enforcement, tenant
provisioning state flow, FBR dry-run/live guard behavior, analytics collectors,
public display route entitlement/data behavior, kiosk checkout, customer-display
live state, linked kiosk POS payment sync, offline POS queue validation,
offline POS browser capture/replay, payment-provider payload normalization,
payment webhook application, and dunning
suspension. Subscription billing now has an Odoo invoice-generation foundation,
signed/secret-guarded payment webhook event records, provider-aware JazzCash,
Easypaisa, and Stripe normalization, external payment status tracking, billing
sync, native signature verification hooks, provider-readiness adapter reports,
refund/chargeback/settlement audit records, provider fees/net amounts,
settlement batch import/reconciliation records, refund/chargeback operator
cases with evidence hashing and
subscription impact actions, dunning, and suspension actions. Tenant database
provisioning has an operator script for database-per-tenant module install plus
DNS/ingress/admin/backup/monitoring operations manifests, generated
Kubernetes/Nginx/DNS/TLS/backup/admin/smoke-test artifacts, and tenant
operations evidence that can be attached to release sign-off; the staging
release wrapper can include that evidence automatically when tenant artifact
paths are supplied. The repo also includes Playwright browser E2E seed,
seed-evidence, and checkout scaffolds, hardware certification records/profiles,
Prometheus/Blackbox/Alertmanager/Grafana/Loki monitoring config, staging
monitoring drill script, restore-drill scripts, and container/dependency scan
hooks. Authenticated staging browser evidence now includes an integrated POS
enterprise journey that creates a paid browser/offline order, replays it into
POS, verifies receipt rendering, exercises print-to-bridge, checks
customer-display state when configured, scans the generated refund barcode, and
proves duplicate replay handling. Direct cashier POS UI click-through selectors
now cover seeded product search, add-to-cart, payment navigation, optional sale
validation/receipt print, and refund barcode form entry for prepared staging
registers.
Remaining enterprise phases include real target-hardware certification, full
authenticated browser POS click-through coverage in staging, production FBR
provider certification, secret-manager rollout, offline POS pilot
certification, PSP certification/settlement-file API sign-off for real
gateways, finance posting/tax policy sign-off for each provider, and deeper
receipt line/tax/payment layout controls.

Odoo 19 compatibility has been handled for this scaffold, including security
group privileges, product form inheritance, and `list` view declarations.

See `docs/MVP_SPEC.md` for the first pilot scope and acceptance criteria.

An optional `tijara_demo_pos` module seeds dev/test cashier data for browser
smoke testing. See `docs/POS_DEMO_SEED.md`.

## Retail Operations and Data Exchange

The retail operations layer now includes:

- Invoice and receipt template customization for POS receipts, customer
  invoices, refund/exchange documents, and quotations.
- Backend QWeb PDF/HTML rendering for Tijara POS receipt and customer invoice
  templates.
- First-pass live browser POS receipt rendering from Tijara receipt profiles,
  including Urdu text, custom body tokens, QR/barcode values, return policy, and
  footer content.
- Browser POS receipt print-to-bridge support for configured local bridge
  receipt printers, with POS order audit fields for bridge print status, job id,
  result JSON, and printed timestamp.
- Invoice barcode/QR scanning on refund and exchange requests.
- Scanner, printer, customer-display, scale, cash-drawer, and fiscal-device
  metadata with configuration testing.
- Local hardware bridge foundation with signed dry-run jobs for receipt print,
  label print, cash drawer, scale, scanner event, and customer display routes,
  including ESC/POS, ZPL, CUPS/raw TCP/file, cash drawer, scale, scanner event,
  and customer-display adapter foundations for validation.
- SaaS runtime enforcement foundation for B2B sales, queue system, promotion
  display/menu/deals boards, and POS customer display.
- Public browser routes for kiosk, menu board, deals board, promotion display,
  customer display, and queue display screens.
- Kiosk self-ordering checkout foundation with cart, customer/mobile capture,
  B2B/B2C price selection, dine-in/takeaway/pickup selection, kiosk order
  records, queue-ticket creation when entitled, and optional linked Odoo POS
  order/payment creation from mapped kiosk profiles.
- Customer-display live order state records with line/totals payloads for POS
  customer-facing screens plus best-effort POS frontend live publishing.
- Provider-aware payment webhook normalization for JazzCash, Easypaisa, Stripe,
  and generic/manual payment flows.
- PSP provider adapter readiness matrix for native signature configuration,
  secret-presence checks, certification references, refund/chargeback mapping,
  and provider-specific settlement parser defaults.
- Payment settlement parser profiles for JSON/CSV provider statements, finance
  accounting action records, approval gates, and audit hashes for payout
  clearing, provider fees, refunds, chargebacks, and write-off review.
- Finance account mapping on the company record plus guarded draft Odoo journal
  move creation for approved provider fee, payout clearing, refund,
  chargeback, and write-off accounting actions, with bulk draft-move creation
  from settlement batches, settlement lines, and refund/chargeback cases.
- Specialized refund accounting actions that create customer refund credit
  notes and draft outbound refund payments with refund journal, outstanding
  account, customer receivable, approval, posting, and audit-hash guardrails.
- FBR dry-run/live HTTP adapter foundation for queued invoices with certified
  provider metadata and compliance evidence fields.
- Offline POS queue foundation with payload hashing, validation, duplicate
  conflict detection, authenticated browser capture endpoints, POS frontend
  localStorage capture/replay, cashier queue status/retry button, server-side
  replay into `pos.order`/payments, disabled-by-default replay cron, conflict
  review actions, duplicate/merge/cancel outcomes, replay audit measures, and
  error tracking.
- Automated daily analytics collector for core POS, inventory, queue, and
  promotion KPI snapshots.
- Odoo transaction/HTTP tests for SaaS enforcement, FBR queue behavior,
  analytics collection, and display route payloads.
- SaaS subscription invoice-generation and external payment tracking
  foundation, including webhook event records and dunning/suspension actions.
- Tenant database provisioning script plus operations manifest generation for
  DNS, ingress, admin, backup, monitoring, Kubernetes ingress, external DNS,
  cert-manager TLS, admin bootstrap, backup policy, and tenant smoke rollout,
  with tenant operations evidence extraction for sign-off.
- Hardware certification records for physical printer/scanner/scale/display
  model evidence capture.
- Playwright E2E scaffolds and seed script for public display, kiosk checkout,
  customer-display, authenticated offline POS replay, receipt report rendering,
  print-to-bridge method coverage, refund barcode scanning, offline review
  route coverage, and POS/refund/report staging paths.
- CSV import/export operations for products/prices, inventory quantities,
  contacts, hardware devices, invoice/receipt templates, storage positions, and
  promotions/deals.

See `docs/RETAIL_OPERATIONS_DATA.md` for CSV schemas, hardware notes, return
scan behavior, and current runtime gaps.

## Open Source Policy

Tijara Suite is being built for a public community repository. The root project
license notice is `LGPL-3.0`, and all current Odoo addon manifests use
`LGPL-3`.

Core product behavior must stay on Odoo Community and open-source tooling.
Avoid Odoo Enterprise modules, proprietary dependencies, private assets, and
vendor-locked services unless they are isolated as optional external adapters
with clear licensing notes.

The detailed policy and dependency intake checklist are maintained in
`docs/OPEN_SOURCE_POLICY.md`.

## DevOps and Configuration

- `.env.example` is the central non-secret configuration template.
- `secrets/.env.secrets.example` is the central secret configuration template.
- `deploy/config/odoo.conf.template` is safe to commit and contains no raw
  secrets.
- `deploy/bin/start-odoo.sh` renders the real Odoo config inside the container at
  runtime.
- `hardware-bridge/` contains the first shop-machine bridge service and example
  device config. POS configurations can select a local bridge receipt printer
  for browser receipt print submission.
- `.github/workflows/tijara-ci.yml`, `scripts/security_audit.sh`, and
  `scripts/js_check.sh` provide the first public-repo CI and security baseline.
  CI now also runs the local release-candidate gate, generates a strict
  CI sign-off package with release retention, secret-manager, Browser E2E
  readiness, and warning-mode production operations readiness evidence, checks
  `release-readiness.json`, and uploads release evidence artifacts with an
  explicit 30-day CI retention setting. A manual protected-runner job is also
  available for strict staging/production evidence on `[self-hosted,
  tijara-protected]`; see `deploy/config/github-protected-vars.example` and
  `secrets/github-protected-secrets.example` for setup templates.
- `deploy/postgres/backup.sh` and `scripts/load_smoke.k6.js` provide backup and
  load-smoke starting points for pilots.
- `scripts/export_load_evidence.py` and `make load-evidence` collect k6/load
  test evidence, threshold decisions, and non-secret load profiles under
  `deploy/runtime/load-evidence/`.
- `scripts/run_load_profile.sh`, `scripts/load_smoke.k6.js`, and
  `scripts/load_enterprise_surfaces.k6.js` run reusable k6 profiles for Odoo
  smoke, POS shell, public display, customer display, kiosk data, and optional
  kiosk checkout load evidence.
- `deploy/config/load-profile-matrix.json`,
  `scripts/export_load_profile_matrix.py`, and
  `make load-profile-matrix-evidence` record tenant-size and vertical-specific
  load profile thresholds for release-owner approval and sign-off extraction.
- `scripts/run_odoo_tests.sh`, `tests/e2e/`, and `playwright.config.mjs`
  provide committed Odoo and browser regression scaffolds. The Odoo test
  runner performs a redacted database credential preflight before the module
  test boot.
- `scripts/run_staging_e2e.sh` and `make e2e-staging` provide guarded staging
  browser evidence runs for POS, refund, print, customer display, offline
  replay, kiosk, public display coverage, and the authenticated enterprise POS
  journey spec.
- `scripts/export_e2e_execution_evidence.py`, `make e2e-execution-evidence`,
  and `npm run test:e2e:execution` correlate seed, profile, readiness,
  Playwright JSON, E2E summary, sign-off readiness, and staging orchestration
  evidence under one Browser E2E execution decision.
- `scripts/export_staging_e2e_profile.py`, `make staging-e2e-profile`, and
  `npm run test:e2e:profile` validate live staging E2E profile readiness,
  including seed env/evidence, required credentials, selected specs, optional
  direct-POS flags, ownership references, HTTPS posture, and optional Odoo login
  probing.
- `scripts/run_staging_ops_checks.sh` and `make ops-staging` gather staging
  monitoring, restore, load-smoke, dependency scan, and container scan evidence
  under `deploy/runtime/ops-evidence/`. Load checks now export k6 summary JSON
  and nested structured load evidence for sign-off extraction.
- `scripts/run_release_candidate_gate.sh` and `make release-candidate` assemble
  local, Odoo, browser, and operations checks into a release-candidate evidence
  report under `deploy/runtime/release-evidence/`.
- `scripts/collect_certification_evidence.py` and `make certification-evidence`
  collect PSP, FBR, and hardware certification metadata, reject secret-like
  metadata fields, fingerprint external evidence files, directories, or
  provider artifact manifests, validate expected SHA-256 hashes, enforce
  minimum evidence counts, approvals, validity dates, and required manifests,
  and write sign-off-ready summaries under
  `deploy/runtime/certification-evidence/`.
- `scripts/export_psp_readiness.py` and `make psp-readiness-evidence` export
  redacted PSP readiness evidence from the committed provider adapter matrix,
  including secret-presence status, certification status, event coverage, and
  parser profile checks under `deploy/runtime/psp-readiness/`.
- `scripts/export_fbr_readiness.py` and `make fbr-readiness-evidence` export
  redacted FBR readiness evidence for certified-provider endpoint, credential,
  sandbox/reference, POS ID, branch code, and payload-hash checks under
  `deploy/runtime/fbr-readiness/`.
- `scripts/fbr_provider_fixture_smoke.py` and `make fbr-fixture-smoke`
  validate committed certified-provider response fixtures without requiring a
  live Odoo database, including accepted/rejected response coverage, invoice
  number, QR payload, certification reference, secret-like key checks, and
  fixture/response hashes.
- `scripts/psp_settlement_fixture_smoke.py` and `make psp-fixture-smoke`
  validate committed JazzCash, Easypaisa, and Stripe settlement fixtures without
  requiring a live Odoo database, including event coverage, secret-like key
  checks, totals, and fixture/line hashes.
- `scripts/export_release_retention_evidence.py` and
  `make release-retention-evidence` export release artifact retention,
  certification evidence retention, evidence fingerprinting, and secret-manager
  reference checks under `deploy/runtime/release-retention-evidence/`.
- `scripts/export_secret_manager_evidence.py` and
  `make secret-manager-evidence` validate runtime secret-manager readiness,
  non-secret template safety, secret example placeholders, Compose secret
  guardrails, startup secret checks, and committed-secret-file hygiene under
  `deploy/runtime/secret-manager-evidence/`.
- `scripts/export_secret_runtime_evidence.py` and
  `make secret-runtime-evidence` validate runtime secret delivery probes from
  `env:`, `file:`, and `command:` sources without writing secret values to
  evidence under `deploy/runtime/secret-runtime-evidence/`.
- `scripts/export_deployment_environment_evidence.py` and
  `make deployment-environment-evidence` validate deployment environment
  protection, required approvers, branch policy, promotion/rollback runbooks,
  deployment gate, monitoring, backup, change-ticket, and release-window
  references under `deploy/runtime/deployment-environments/`.
- `scripts/generate_signoff_pack.py` and `make signoff-pack` generate release
  approval templates, an evidence summary, machine-readable readiness JSON, and
  an evidence manifest for PSP, FBR, hardware, finance, security, and go/no-go
  review under `deploy/runtime/signoff-packages/`, with optional
  required-evidence group guardrails for release, E2E, operations, security,
  hardware, FBR, and PSP evidence. PSP/FBR readiness manifests, FBR fixture
  smoke evidence, certification evidence, E2E seed/profile/execution/readiness
  evidence, monitoring, incident runbook, release retention, secret manager,
  secret runtime, deployment environment, and load evidence are extracted into
  readiness reviews for approvers and CI.
- `scripts/check_release_readiness.py` and `make check-release-readiness` let
  CI/CD fail on `release-readiness.json` decisions of `blocked` and optionally
  on `warning`.
- `scripts/run_staging_release_signoff.sh` and `make staging-release-signoff`
  sequence optional E2E seeding, optional staging E2E profile preflight,
  staging release-candidate evidence, browser E2E evidence, operations evidence,
  deployment environment evidence, sign-off package generation, readiness
  checking, optional E2E execution evidence, and artifact path reporting under
  one run ID.
- `scripts/export_e2e_readiness.py`, used by `make e2e-staging`, writes
  authenticated POS/refund/print browser readiness evidence with secret-masked
  required-variable checks before Playwright starts.
- `scripts/export_e2e_seed_evidence.py`, used by `make seed-e2e`, writes
  sourceable non-secret staging seed exports plus seed status, summary, and
  release sign-off JSON for POS checkout, refund, receipt print, display,
  kiosk, customer display, and offline replay browser setup.
- `scripts/run_production_deployment_gate.py` and
  `make production-deployment-gate` generate deployment gate evidence from a
  staging sign-off package, including required deployment environment evidence,
  tenant rollout reviews, tenant smoke reviews, backup, rollback, monitoring,
  approver, pre-cutover, and rollback checklists.
- `scripts/run_production_rollback.py` and `make production-rollback` provide
  dry-run-first rollback hooks for manifest, Docker Compose, and Kubernetes
  providers, with command logs and rollback decision evidence.
- `scripts/run_production_smoke.py` and `make production-smoke` capture
  post-deploy/post-rollback endpoint smoke evidence and a machine-readable
  smoke decision.
- `scripts/run_tenant_smoke.py` and `make tenant-smoke` execute per-tenant
  smoke checks from tenant operations artifacts, including web/login endpoint
  probes, database-isolation request headers, smoke checklist coverage, and
  tenant-level release blockers under `deploy/runtime/tenant-smoke/`.
- `scripts/run_tenant_rollout.py` and `make tenant-rollout` dry-run or execute
  tenant DNS/ingress/TLS/Nginx/monitoring/backup rollout actions from tenant
  operations artifacts, including provider-aware DNS apply/rollback command
  templates, writing auditable rollout and rollback evidence under
  `deploy/runtime/tenant-rollouts/`.
- `scripts/export_monitoring_evidence.py` and `make monitoring-evidence`
  collect post-deploy monitoring evidence from production smoke, tenant rollout,
  tenant smoke, deployment, rollback, and Prometheus/Alertmanager/Grafana
  endpoint probes under `deploy/runtime/monitoring-evidence/`.
- `scripts/export_incident_runbook_evidence.py` and
  `make incident-runbook-evidence` collect release owner, DevOps, support,
  business, on-call, alert-route, runbook, backup, restore, rollback, and
  monitoring references under `deploy/runtime/incident-runbooks/`.
- `scripts/run_operations_release_bundle.py` and
  `make operations-release-bundle` combine load profile matrix, enterprise load,
  production smoke, optional tenant rollout, optional tenant smoke, monitoring,
  and incident runbook evidence under one operations run ID for release sign-off.
- `scripts/export_production_ops_readiness.py` and
  `make production-ops-readiness` combine operations bundle, monitoring,
  incident, load, retention, secret-manager/runtime, deployment environment,
  tenant operations, backup/restore, and scan references into one production
  operations verdict under `deploy/runtime/production-ops-readiness/`.
- `scripts/export_ops_tool_evidence.py` and `make ops-tool-evidence` turn
  actual restore-drill logs, security-audit logs, dependency scan logs, Trivy
  JSON, npm audit JSON, pip-audit JSON, and k6 summaries into structured
  Operations evidence under `deploy/runtime/ops-tool-evidence/`.
- `scripts/seed_e2e_odoo.sh` creates stable staging slugs for display, kiosk,
  customer-display, POS checkout, refund barcode, receipt print, and offline
  POS replay browser tests, then writes E2E seed evidence under
  `deploy/runtime/e2e-seed/`.
- `scripts/provision_tenant_db.sh` provisions isolated tenant databases through
  the Odoo container module install path.
- `scripts/generate_tenant_ops_manifest.py` generates tenant DNS, ingress,
  admin, backup, and monitoring artifacts for DevOps handoff.
- `deploy/monitoring/`, `deploy/logging/`, and `deploy/postgres/restore-drill.sh`
  provide Prometheus, Blackbox, Alertmanager, Grafana, Loki, logging, and
  restore-drill baselines.
- `scripts/container_scan.sh` and `scripts/dependency_scan.sh` provide
  production security scan hooks for Trivy, npm audit, and pip-audit.
- `DEPLOY.md` is the maintained deployment runbook.

## Touch and Browser Support

The product standard is touch-first, responsive, cross-device, and
cross-browser. The first shared baseline stylesheet is included in
`tijara_pos_experience/static/src/scss/touch_responsive.scss`.

The first touch-friendly POS overlay is the overall bill discount dialog. It
supports discount percentage and discount amount entry on the same bill; when
the cashier changes one value, the other recalculates automatically before the
standard Odoo global discount line is applied.

The POS action menu also includes first-pass B2B/B2C and
dine-in/takeaway/pickup controls. B2B/B2C switching reprices existing ticket
lines from the Tijara product B2C/B2B fields.

The acceptance matrix is maintained in `docs/FRONTEND_DEVICE_QA.md` and covers
POS, kiosk, customer display, queue display, promotion/deals display, menu
display, back office, Urdu rendering, scanner input, and common mobile/tablet/
desktop/kiosk viewports.

## SaaS Feature Flags

The POS experience layer is packaged as separate SaaS capabilities:

- `b2b_sales`
- `queue_system`
- `promotion_display`
- `customer_display`
- `inventory_intelligence`
- `analytics_reporting`

These features can be enabled by plan or added to an individual subscription.
Set `TIJARA_SAAS_ENFORCEMENT_ENABLED=True` or the Odoo system parameter
`tijara.saas.enforcement_enabled=1` to actively block unavailable POS
experience features.

## Iteration Tracking

Every implementation iteration must update:

- `README.md` when setup, architecture, modules, usage, or project structure
  changes.
- `PROGRESS.md` with completed work, validation results, risks, and the next
  planned build step.

This keeps the product record clear as Tijara Suite grows from scaffold to
pilot-ready SaaS.
