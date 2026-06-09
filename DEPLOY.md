# Deploy Guide

This guide is the operational entry point for deploying Tijara Suite. Keep it
updated whenever deployment, configuration, secrets, observability, backup, or
release behavior changes.

Every implementation iteration must keep the public operator record aligned:
update `README.md` for product/setup/module changes, this `DEPLOY.md` for
deployment/runtime/release changes, `PROGRESS.md` for completed work and
validation, `docs/DIAGRAMS.md` for topology/flow changes, and
`docs/USER_GUIDE_ALL_USERS.md` plus `docs/TEST_CREDENTIALS.csv` whenever
personas, credentials, or workflows change.

## Deployment Layout

```text
.env.example                         Central non-secret environment template
secrets/.env.secrets.example          Central secret environment template
deploy/config/odoo.conf.template      Secret-free Odoo runtime config template
deploy/bin/start-odoo.sh              Renders the runtime Odoo config
deploy/logging/                       Logging aggregation and retention notes
deploy/monitoring/                    Prometheus and Blackbox Exporter baseline
deploy/nginx/tijara.conf              Reverse proxy baseline
deploy/postgres/                      Database backup, restore drill, operations
hardware-bridge/                      Local shop-machine bridge service
docs/CONFIGURATION_AND_SECRETS.md      Central config/secret source-of-truth
docs/RETAIL_OPERATIONS_DATA.md        Hardware, templates, scanning, CSV notes
docs/DIAGRAMS.md                      Deployment, system, UML, module,
                                      component, activity, and user-flow diagrams
docs/diagrams/png/                    Rendered PNG exports of architecture diagrams
docs/COMMANDS_QUICKREF.md             Generated local and staging command sheet
docs/SETUP_STEP_BY_STEP.md            Step-by-step setup guide
docs/HOW_TO_USE_GUIDELINES.md         Daily usage guidelines
docs/PRODUCTION_READINESS_CHECKLIST.md Go-live checklist
docs/SPEC_MAP.json                    Machine-readable app/persona/screen map
docs/TEST_CREDENTIALS.csv             Public-safe demo/staging account matrix
docker-compose.yml                    Development and small deployment runtime
scripts/dev-start.sh                  Local bootstrap/start script
scripts/dev-stop.sh                   Local stop and port verification script
scripts/dev-restart.sh                Local restart wrapper
scripts/tijara_host.py                Python server host/bootstrap script
scripts/tijara_services.py            Python service manager for PC/server
Makefile                              Operator shortcuts
```

Do not put passwords, API keys, database passwords, backup keys, FBR credentials,
payment credentials, or JWT/session material in committed configuration files.

Deployment topology and runtime flow diagrams are maintained in
`docs/DIAGRAMS.md`. Use that pack during DevOps handoff, architecture review,
tenant onboarding, release readiness review, and incident exercises.
Rendered PNG exports are maintained in `docs/diagrams/png/` for slide decks,
customer handoff documents, and tools that do not render Mermaid. Regenerate
them with `npm run docs:diagrams:png`.

## Environment Files

Use exactly two centered runtime files per local or staging environment:

- `.env`: non-secret runtime configuration, copied from `.env.example`.
- `secrets/.env.secrets`: secret runtime configuration, copied from
  `secrets/.env.secrets.example`.

All new runtime variables must be added to one of those two templates. Do not
add `.env.local`, `.env.production`, shell export files, or service-specific
secret files for application runtime. Template consumers such as
`docker-compose.yml`, `deploy/config/odoo.conf.template`, protected-runner
examples, monitoring config, and nginx config may reference variables, but they
must not become stores for raw secrets.

For production, plain env files should be replaced by a secret manager such as
Vault, SOPS, Kubernetes Secrets, Docker secrets, Doppler, 1Password Secrets
Automation, AWS Secrets Manager, Azure Key Vault, or Google Secret Manager.
Use the same variable names documented in `.env.example` and
`secrets/.env.secrets.example`.

The full ownership, rotation, and variable-addition checklist is maintained in
`docs/CONFIGURATION_AND_SECRETS.md`.

Local bootstrap:

```bash
cp .env.example .env
mkdir -p secrets
cp secrets/.env.secrets.example secrets/.env.secrets
```

Generate strong values for production secrets:

```bash
openssl rand -base64 48
```

The Python hosting script can generate local random placeholder replacements
for shared staging or demo servers:

```bash
python3 scripts/tijara_host.py init-config --environment staging --generate-secrets
```

For production, prefer the selected secret manager and run with
`--production` so placeholder secrets are blocked before deployment.

## Python Hosting And Service Manager

Use `scripts/tijara_host.py` when preparing a new server or production-like
host. It creates the central `.env` and `secrets/.env.secrets` files when they
are missing, applies public URL/domain defaults, optionally generates local
random secret values for non-production use, validates Docker Compose, pulls or
builds services, starts profiles, and can install or seed the Odoo modules.

Common server flow:

```bash
python3 scripts/tijara_host.py preflight --all-profiles
python3 scripts/tijara_host.py init-config \
  --environment staging \
  --public-url https://staging.example.com \
  --generate-secrets
python3 scripts/tijara_host.py deploy \
  --with-hardware \
  --with-monitoring \
  --install-suite \
  --db tijara_dev
```

Production-style flow with placeholders blocked:

```bash
python3 scripts/tijara_host.py init-config \
  --production \
  --domain tijara.example.com
python3 scripts/tijara_host.py deploy \
  --production \
  --domain tijara.example.com \
  --with-monitoring \
  --install-suite \
  --db tijara_prod
```

Use `scripts/tijara_services.py` for day-to-day service control on a local PC,
demo machine, or server:

```bash
python3 scripts/tijara_services.py start --all-profiles
python3 scripts/tijara_services.py status
python3 scripts/tijara_services.py logs odoo --tail 200
python3 scripts/tijara_services.py restart --with-monitoring
python3 scripts/tijara_services.py stop --force-kill-ports
```

Both Python scripts use the same central runtime files documented in
`docs/CONFIGURATION_AND_SECRETS.md`; they do not introduce separate secret
stores.

## Compose Commands

The Makefile automatically includes `.env` and `secrets/.env.secrets` when they
exist.

```bash
make validate
make js-check
make py-start
make py-status
make py-stop
make py-config
make host-preflight
make host-init-config
make host-deploy
make security-audit
make dev-start
make dev-stop
make config
make up
make ps
make logs
make install-suite
make upgrade-pkr-gst
make verify-pkr-gst
make seed-pos-demo
make seed-demo-users
make seed-e2e DB=tijara_dev
make local-e2e-evidence
make test-odoo
make e2e
make browser-e2e-matrix
make protected-browser-e2e-matrix
make bridge-up
make bridge-logs
make backup-db
make restore-drill BACKUP=deploy/runtime/backups/file.dump
make provision-tenant TENANT_DB=tijara_customer_001 TENANT_NAME="Customer 001"
make provision-tenant-ops TENANT_DB=tijara_customer_001 TENANT_DOMAIN=customer.example.com ADMIN_EMAIL=admin@example.com
make hardware-cert-smoke
make monitoring-up
make load-smoke
make load-enterprise-surfaces
make load-profile-matrix-evidence
make release-candidate
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
make protected-evidence-bundle-score
make protected-evidence-bundle-drift
make github-step-summary
```

For a developer workstation or sales-engineer demo, prefer the generated
pipeline:

```bash
bash scripts/dev-start.sh
node scripts/capture-screenshots.js
python3 scripts/generate_screenshot_user_guide.py
node scripts/record-demo.js
python3 scripts/generate_customer_demo_video.py
bash scripts/assemble-video.sh
bash scripts/dev-stop.sh
```

Use `TIJARA_DEV_START_HARDWARE=1` to include the local hardware bridge profile
and `TIJARA_DEV_START_MONITORING=1` to include Prometheus, Alertmanager, Loki,
and Grafana. The scripts keep generated logs and runtime process metadata under
`logs/`, which is intentionally ignored by git.

For customer-facing sales handoff, run `make customer-demo-video` on macOS with
Chrome, `say`, `afconvert`, Node, and Node dependencies installed. It writes
`docs/PRODUCT_DEMO_CUSTOMER.webm` with generated voiceover; keep that generated
media out of git and share it as a release, sales, or customer deliverable.

## Ecommerce Delivery Operations Runtime

The `tijara_ecommerce` module includes a production-layer delivery operations
foundation for open-source/local/staging execution:

- Provider-specific assumed fixtures for in-house riders and Pakistan courier
  profiles such as TCS, Leopards, PostEx, M&P, BlueEx, Trax, Rider, and Call
  Courier.
- Adapter payload classes for shipment create/cancel, label, manifest, and
  assumed response mapping. All real endpoints and token references remain
  dummy/open-source safe until certified courier onboarding replaces them.
- `tijara.ecommerce.delivery.retry` for retry/backoff queue evidence.
- `tijara.ecommerce.delivery.exception` for SLA breaches, failed deliveries,
  webhook errors, and retry exhaustion review.
- `tijara.ecommerce.delivery.reconciliation` for COD, delivery charge,
  provider fee, and net receivable reporting by provider/date range.
- Public customer order history at `/tijara/ecommerce/<slug>/orders` and JSON
  lookup at `/tijara/ecommerce/<slug>/orders/list`.
- Authenticated customer account routes at `/tijara/ecommerce/<slug>/account`
  with JSON endpoints for account payload, saved addresses, and portal-created
  return/exchange requests.
- Daily KPI collectors for ecommerce order pipeline, delivery SLA breach rate,
  retry aging, courier success rate, COD receivable aging, and delivery
  reconciliation variance.
- Prometheus/Alertmanager delivery alert rules in
  `deploy/monitoring/tijara-delivery-alerts.yml`, with dummy metric examples in
  `deploy/monitoring/tijara-delivery-metrics.example.prom`.
- Token-protected Prometheus business metrics at
  `/tijara/monitoring/metrics`, using `TIJARA_METRICS_TOKEN` or Odoo system
  parameter `tijara.monitoring.prometheus_token`.

The retry queue and SLA monitor are installed as Odoo crons. In local/demo mode
they process assumed HTTP JSON responses without making live courier network
calls. Before production, replace dry-run endpoints, payload mappings,
credentials, webhook secret-manager entries, and provider fee assumptions with
certified courier/API details.

After changing delivery operations code or fixtures, upgrade ecommerce and run
focused tests before the protected browser matrix:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets run --rm odoo bash /usr/local/bin/tijara-start-odoo -d tijara_dev -u tijara_ecommerce --without-demo --stop-after-init
make test-odoo
make seed-e2e DB=tijara_dev
make protected-browser-e2e-matrix
```

Direct Compose usage should include both env files:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets up -d
docker compose --env-file .env --env-file secrets/.env.secrets ps
```

`make test-odoo` runs a redacted database credential preflight before the Odoo
test boot. If the preflight fails, verify `POSTGRES_PASSWORD` and
`ODOO_DB_PASSWORD` in the active secret source. For local Docker volumes,
changing the env file after the database volume was created does not rotate the
stored Postgres password; rotate the password inside Postgres or intentionally
recreate the local database volume.

Install the custom module suite into a fresh database with the Makefile target:

```bash
make install-suite
```

The equivalent direct Compose command is:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets run --rm odoo bash /usr/local/bin/tijara-start-odoo -d tijara_dev -i tijara_base,tijara_retail_core,tijara_inventory_intelligence,tijara_pos_pk,tijara_saas_control,tijara_pos_experience,tijara_analytics,tijara_ecommerce,tijara_vertical_pharmacy,tijara_vertical_restaurant,tijara_vertical_garments,tijara_vertical_electronics,tijara_vertical_cloth,tijara_vertical_superstore,tijara_vertical_grocery,tijara_vertical_bakery --without-demo --stop-after-init
```

For the local Pakistan demo/readiness path after a PKR/GST or demo-data change:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets up -d
make upgrade-pkr-gst
make verify-pkr-gst
make seed-pos-demo
make seed-demo-users
make verify-enterprise-seed
make capture-screenshots
make screenshot-user-guide
```

For a single repeatable local/staging-style evidence pass, run:

```bash
make local-e2e-evidence
```

The harness starts Compose, waits for Odoo, upgrades `tijara_base`,
`tijara_retail_core`, `tijara_pos_experience`, `tijara_analytics`,
`tijara_ecommerce`, and `tijara_demo_pos`, verifies Pakistan country/PKR/GST
18%, seeds demo users from
`docs/TEST_CREDENTIALS.csv`, seeds the authenticated browser E2E profile, runs
the full Playwright browser suite, and exports the correlated execution
decision. The latest local run
`local-e2e-20260609T073524Z` passed with no blockers; generated evidence is
ignored under `deploy/runtime/local-e2e/`,
`deploy/runtime/e2e-evidence/`, and `deploy/runtime/e2e-execution/`.

For protected/staging cross-browser and touch evidence, seed the staging E2E
profile, load the generated non-secret seed env plus the real password from the
secret manager, then run:

```bash
make browser-e2e-matrix
```

By default this runs the Playwright projects `chromium-desktop`,
`mobile-touch`, `firefox-desktop`, `webkit-desktop`, and `tablet-touch`, then
writes aggregate evidence under `deploy/runtime/browser-e2e-matrix/<run-id>/`.
Limit the matrix when debugging with:

```bash
TIJARA_BROWSER_E2E_PROJECTS="chromium-desktop mobile-touch" make browser-e2e-matrix
```

Protected runners can include the matrix in the existing protected browser lane
with:

```bash
TIJARA_PROTECTED_E2E_MATRIX=1 make protected-browser-e2e
```

`make verify-pkr-gst` writes ignored runtime evidence under
`deploy/runtime/pkr-gst-verification/`, and `make seed-demo-users` writes
ignored runtime evidence under `deploy/runtime/demo-users/`.

## Runtime Config

`deploy/config/odoo.conf.template` is safe to commit because it contains
placeholders only. `deploy/bin/start-odoo.sh` renders the real Odoo config inside
the container at runtime using environment variables. The generated file is not
committed and should not be copied out to source control.

Compose requires these secret values before startup:

- `POSTGRES_PASSWORD`
- `ODOO_DB_PASSWORD`
- `ODOO_MASTER_PASSWORD`
- `TIJARA_BRIDGE_SHARED_SECRET` for hardware bridge deployments
- `TIJARA_PAYMENT_WEBHOOK_SECRET` for public payment webhook validation
- `TIJARA_METRICS_TOKEN` for the Odoo Prometheus business metrics endpoint
- Delivery webhook secrets for certified providers, loaded into the Odoo config
  parameter namespace `tijara.delivery.webhook.<PROVIDER_CODE>.secret`
- `GRAFANA_ADMIN_PASSWORD` for the monitoring profile

The startup script refuses to start production if placeholder or development
secret values are still present. It also refuses production startup when
`TIJARA_METRICS_TOKEN` is set to a dummy or placeholder value.

For single-database local development, `POSTGRES_PASSWORD` and
`ODOO_DB_PASSWORD` should match the active password for the `POSTGRES_USER` role.
For production, keep both values in the secret manager and rotate them through a
planned database credential rotation, not by editing committed templates.

## Ecommerce Deployment Notes

The ecommerce module is part of the standard Tijara suite install. It uses Odoo
Community website/sale/stock foundations plus Tijara SaaS, B2B/B2C pricing,
promotion, queue, analytics, loyalty, and Pakistan charge-policy fields.

Production ecommerce rollout must include:

- HTTPS domain routing for each tenant storefront path or domain.
- SaaS plan entitlement for `ecommerce_store`; B2B online pricing also requires
  the `b2b_sales` feature when enforcement is enabled.
- Published online products with SKU/barcode, Urdu/English names where needed,
  B2C/B2B prices, tax policy, and stock visibility reviewed by inventory.
- Payment provider configuration and webhook certification before accepting
  live JazzCash, Easypaisa, Stripe, or card payments.
- Pickup/delivery operating procedures, queue display checks, delivery charges,
  cafe-only service charge, and cafe/restaurant card/cash tax policy review.
- Delivery-provider setup under Ecommerce Configuration > Delivery Providers.
  The seeded `Tijara In-House Delivery` provider is dry-run/assumption mode for
  demos only; production requires certified courier/provider contracts,
  credentials, webhook signing, reconciliation, and support runbooks.
- Delivery-provider adapter settings now include adapter mode, create/cancel/
  status/label/manifest endpoints, supported capabilities, label format,
  webhook reference/status/ETA field names, and webhook signature mode.
- For HMAC SHA256 delivery webhooks, keep raw secrets outside source control.
  The current Odoo-side lookup uses the config parameter
  `tijara.delivery.webhook.<PROVIDER_CODE>.secret`, which should be populated
  from the environment secret manager during tenant/provider onboarding.
- Customer order tracking routes:
  `/tijara/ecommerce/<slug>/track`,
  `/tijara/ecommerce/<slug>/track/<token>`, and
  `/tijara/ecommerce/<slug>/track/status`.
- Delivery-provider webhook route:
  `/tijara/ecommerce/delivery/webhook/<provider_code>`.
- Public-route security controls at the reverse proxy, including rate limits,
  request-size limits, bot controls where needed, and log retention.
- Browser tests for catalog, checkout, sale-order creation, queue handoff, and
  customer order tracking, delivery label/manifest actions, dry-run webhook
  sync, plus receipt/invoice print paths after each staging upgrade.
- `TIJARA_ECOMMERCE_SLUG` configured in the Browser E2E environment. The seeded
  local/demo channel exports `tijara-demo-web`.

## Production Checklist

- Pin Docker image versions and record the Odoo version used for each release.
- Use HTTPS at the reverse proxy and keep `proxy_mode=True`.
- Disable public database listing in production with `ODOO_LIST_DB=False`.
- Use database-per-tenant isolation for SaaS customers.
- Use separate staging and production databases.
- Run `make validate` before every release.
- Install or upgrade modules in staging before production.
- Take a database backup before module upgrades.
- Keep PostgreSQL backups encrypted and restore-tested.
- Run `make restore-drill BACKUP=...` after backup process changes and at least
  monthly in production.
- Configure monitoring for Odoo HTTP, long polling/websocket, PostgreSQL health,
  disk usage, worker memory, and queue latency.
- Configure audit logging for refunds, exchanges, discounts, voids, stock
  adjustments, SaaS entitlement changes, and admin settings.
- Rotate secrets when staff access changes or after any suspected exposure.

## Backup Baseline

Minimum backup policy for pilots:

- Nightly PostgreSQL logical backup.
- Daily filestore backup.
- Seven-day local retention.
- Thirty-day offsite encrypted retention.
- Monthly restore drill.

Production SaaS should move to continuous WAL archiving or managed PostgreSQL
point-in-time recovery.

Restore drill:

```bash
CONFIRM_RESTORE_DRILL=YES bash deploy/postgres/restore-drill.sh deploy/runtime/backups/latest.dump
```

The restore drill creates a temporary database, restores the backup into it,
runs a simple query, and drops the temporary database on exit.

## Touch, Device, and Browser Readiness

Production release cannot rely on desktop-only behavior. Validate the POS,
kiosk, customer display, queue display, promotion display, menu display, and
back-office workflows against:

- Touch screens and mouse/keyboard devices.
- Android Chrome, iOS Safari, desktop Chrome, desktop Edge, desktop Firefox, and
  desktop Safari.
- 360 px, 390 px, 768 px, 1024 px, 1366 px, and 1920 px viewport widths.
- Urdu and English layouts.
- Barcode scanner keyboard-wedge input.
- Keyboard-only POS cashier operation for product lookup, Enter flow, payment,
  receipt print, quantity changes, B2B/B2C switching, and service-mode cycling.
- Receipt printer and customer display hardware paths where available.

See `docs/FRONTEND_DEVICE_QA.md` for the acceptance standard.

For Urdu PDF and label printing, install and verify open-source Urdu/Arabic
fonts in the Odoo report-rendering runtime before staging sign-off, for example
Noto Naskh Arabic or Noto Nastaliq Urdu. Confirm generated POS receipts,
customer invoices, refund/exchange slips, quotations, and inventory labels show
Urdu text correctly in browser print, PDF, ESC/POS raster, ZPL/image-label, and
CUPS paths where those paths are used.

## Hardware Bridge Readiness

The current Odoo layer stores scanner/printer/customer-display/cash-drawer/scale
configuration and can validate required connection metadata. The first
open-source local bridge foundation lives in `hardware-bridge/` and can run as a
Docker Compose `hardware` profile service:

```bash
make bridge-up
make bridge-logs
```

The foundation accepts signed jobs for receipt print, label print, cash drawer,
scale read, scanner event, and customer-display routes. It can build ESC/POS
receipt bytes, ZPL label bytes, cash-drawer pulse bytes, customer-display JSON,
scanner-event JSON, and dry-run scale readings. Non-dry-run delivery supports
CUPS queues, raw TCP devices, and file output, but every physical device path
still needs target-hardware validation before pilot rollout.

For POS receipt printing through the bridge:

1. Set `TIJARA_BRIDGE_SHARED_SECRET` in the Odoo runtime environment or the
   `tijara.bridge.shared_secret` Odoo system parameter.
2. Register a `receipt_printer` hardware device with `browser_bridge`
   connection type, `escpos` printer language where appropriate, and the local
   bridge endpoint.
3. Run `Bridge Health` and `Send Bridge Test Job` from the hardware device form.
4. Select that device in the POS configuration as the Tijara receipt printer.
5. Complete a POS order and use the POS receipt print action; the order should
   record bridge print status, job id, result JSON, and printed timestamp.

Bridge deployment rules:

- Keep bridge configuration separate from Odoo database secrets.
- Use signed local HTTP or websocket requests between Odoo/POS and bridge.
- Restrict bridge network binding to localhost or the trusted store LAN.
- Log print/scan/display test results for support and audit.
- Support keyboard-wedge scanner fallback where no driver is required.
- Validate ESC/POS, ZPL, CUPS/browser print, QR/barcode output, and Urdu text
  rendering with the target hardware before pilot go-live.

See `docs/RETAIL_OPERATIONS_DATA.md` for the current device registry fields and
runtime gaps.

Run dry-run certification profiles before physical QA:

```bash
make hardware-cert-smoke
```

Then repeat the same profile categories on target hardware and record model,
firmware, connection type, paper/label size, Urdu rendering, barcode/QR scan
success, cash drawer pulse, scale readings, and customer-display behavior.
Use Hardware Certifications in Retail Configuration to store evidence per
physical printer, scanner, scale, drawer, and display model.
Use `Prepare Checks` on each Hardware Certification to create execution checks
for the device type, then run or manually pass each check with observed bridge
job id, response code, duration, and evidence hash. A certification with
execution checks cannot be marked passed until every check is passed.

## Tenant Provisioning

For database-per-tenant SaaS rollout, create or approve a provisioning request
in SaaS Admin, then run:

```bash
make provision-tenant TENANT_DB=tijara_customer_001 TENANT_NAME="Customer 001"
```

The script validates the database name, runs the Tijara module install command
inside the Odoo container, and leaves the SaaS operator to mark the matching
provisioning request as provisioned.

Generate tenant operations artifacts after database provisioning:

```bash
make provision-tenant-ops TENANT_DB=tijara_customer_001 TENANT_DOMAIN=customer.example.com ADMIN_EMAIL=admin@example.com
```

This writes a tenant operations bundle under
`deploy/runtime/tenants/<tenant_db>/`:

- `ops-manifest.json` with tenant, DNS, ingress, admin, backup, monitoring,
  and smoke-check metadata.
- `nginx-location.conf` for database isolation headers.
- `k8s-ingress.yaml` for Kubernetes ingress rollout.
- `external-dns-record.json` for DNS provider/manual record creation.
- `cert-manager-certificate.yaml` for TLS certificate issuance.
- `backup-policy.json` for backup retention and restore-drill linkage.
- `prometheus-blackbox-target.json` for tenant uptime monitoring.
- `admin-bootstrap.md` with non-secret admin bootstrap instructions.
- `smoke-checklist.md` for tenant go-live checks.

The matching Odoo provisioning request can also generate a compatible
operations manifest from SaaS Admin. Production DNS changes, certificate
issuance, admin-user creation, and smoke execution still need provider-specific
automation, but the required rollout artifacts are now machine-checkable.

Export tenant operations evidence before pilot, staging, or production
sign-off:

```bash
python3 scripts/export_tenant_ops_evidence.py \
  --run-id 2026-06-05-prod \
  --target-environment production \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --minimum-tenants 1 \
  --require-dns-provider \
  --require-admin-email \
  --require-restore-drill \
  --require-monitoring \
  --require-all-artifacts \
  --strict
```

The exporter writes `tenant-ops-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/tenant-ops-evidence/<run-id>/`. Attach that directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS` and require the `ops` evidence group for
production sign-off; the sign-off package extracts tenant readiness under
`tenant_ops_reviews`.

Dry-run tenant rollout actions before DNS/TLS cutover:

```bash
python3 scripts/run_tenant_rollout.py \
  --run-id 2026-06-05-prod \
  --target-environment production \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --platform kubernetes \
  --minimum-tenants 1 \
  --require-all-artifacts \
  --strict
```

The runner reads `ops-manifest.json` and the generated tenant artifacts, builds
Kubernetes ingress/cert-manager, Nginx, external-dns, monitoring, and backup
rollout actions, and writes `tenant-rollout-evidence.json`, `status.tsv`,
`rollback-plan.md`, `summary.md`, and `env-summary.txt` under
`deploy/runtime/tenant-rollouts/<run-id>/`. It is dry-run-first; real
infrastructure commands require both `--execute` and
`CONFIRM_TENANT_ROLLOUT=YES`. Attach this directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS`; the sign-off package extracts it under
`tenant_rollout_reviews`. Keep `rollback-plan.md` with the deployment gate so
operators can reverse DNS, ingress, TLS, Nginx, monitoring, and backup-policy
changes with named release-owner approval.

For provider-specific DNS command evidence, pass non-secret CLI templates and
template values. Template placeholders can use `hostname`, `target`,
`record_type`, `ttl`, `tenant_db`, and operator-provided non-secret values such
as `zone_id`, `record_id`, or `domain`. Secret-like template keys are rejected.

```bash
python3 scripts/run_tenant_rollout.py \
  --run-id 2026-06-05-prod-dns \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --platform external-dns \
  --dns-apply-command-template 'cloudflare dns record create --zone-id {zone_id} --type {record_type} --name {hostname} --content {target} --ttl {ttl}' \
  --dns-rollback-command-template 'cloudflare dns record delete --zone-id {zone_id} --record-id {record_id}' \
  --dns-template-value zone_id=zone-public-ref \
  --dns-template-value record_id=record-public-ref \
  --strict
```

For Route53 or DigitalOcean, use the same template mechanism with the relevant
CLI syntax, for example `aws route53 change-resource-record-sets ...` or
`doctl compute domain records delete ...`. Store provider tokens in the secret
manager or runner environment; do not put them in rollout evidence.

## Subscription Billing

Subscriptions can generate draft Odoo customer invoices from the selected plan
price or a billing override amount. Operators can:

- Set billing customer, cycle, price override, billing product, and provider.
- Generate the customer invoice from the subscription form.
- Sync invoice/payment state.
- Record external payment confirmation for manual, JazzCash, Easypaisa, Stripe,
  or other provider flows.
- Receive signed/secret-guarded provider webhook payloads at
  `/tijara/saas/payment/webhook/<provider>`.
- Store webhook events, normalize JazzCash/Easypaisa/Stripe/manual payloads,
  track provider reference, transaction id, settlement batch, provider event
  type, refund reference, chargeback reference, signature status, audit hash,
  provider fee, net amount, reconciliation status, and run dunning/suspension
  actions from the subscription form.
- Keep settlement batch, refund, and chargeback events as auditable
  reconciliation records. Operators can mark matched events as reconciled or
  flag mismatches for PSP follow-up.
- Import provider or bank settlement statements into Payment Settlements using
  JSON or CSV with parser profiles for JazzCash, Easypaisa, Stripe balance
  transactions, manual bank statements, or generic statements. The settlement
  import normalizes provider references, transaction ids, invoice/subscription
  hints, event type, gross amount, fee, net amount, settlement date, raw line
  JSON, and deterministic line hash, then matches each line to existing webhook
  events, subscriptions, or invoices.
- Create refund/chargeback cases from webhook events or settlement lines. Cases
  track due date, provider reference, transaction id, amount, fee, reason,
  assigned operator, evidence summary/JSON/attachments, evidence hash, outcome,
  and the accounting action still required.
- Generate finance accounting actions from settlement lines and dispute cases.
  Actions cover payout clearing, provider fees, refund credit notes/refund
  payments, chargeback receivables, chargeback fees, write-off review, and
  manual review. Settlement batches cannot be marked reconciled while finance
  approval is required and generated actions are missing or unapproved.
- Configure finance accounts on the company record and create draft Odoo
  journal entries, customer refund credit notes, or draft outbound refund
  payments from approved accounting actions. The system refuses draft move or
  refund document creation until the payment accounting journal, refund payment
  journal, outstanding payment account, customer receivable account, and
  required clearing, counterpart, fee, refund, chargeback, and write-off
  accounts are configured.

Set `TIJARA_PAYMENT_WEBHOOK_SECRET` in the secret store or set the Odoo system
parameter `tijara.saas.payment_webhook_secret`. Provider requests must include
`X-Tijara-Webhook-Secret`.

Native provider signature secrets can be supplied through the secret manager or
matching Odoo system parameters:

```text
TIJARA_STRIPE_WEBHOOK_SECRET / tijara.saas.stripe_webhook_secret
TIJARA_JAZZCASH_INTEGRITY_SALT / tijara.saas.jazzcash_integrity_salt
TIJARA_EASYPAISA_WEBHOOK_SECRET / tijara.saas.easypaisa_webhook_secret
```

Set `TIJARA_PAYMENT_REQUIRE_NATIVE_SIGNATURES=True` or system parameter
`tijara.saas.payment_require_native_signatures = 1` after provider contracts are
validated in staging. When enabled, webhooks with unchecked or invalid native
provider signatures are rejected. Production still needs PSP certification,
exact settlement-file mapping, refund/chargeback SLAs, and tax configuration.

The provider adapter service
`tijara.saas.payment.provider.adapter` exposes redacted readiness reports for
manual/bank, JazzCash, Easypaisa, Stripe, and other PSP profiles. It checks the
webhook route, native signature secret presence, refund/chargeback/settlement
event coverage, provider-specific settlement parser profile, and certification
reference/status without returning secret values. It also validates a webhook
payload against the provider signature verifier and normalized payload mapping
before the payload is applied.

Provider certification references can be recorded through system parameters or
environment variables:

```text
tijara.saas.stripe_certification_reference / TIJARA_STRIPE_CERTIFICATION_REFERENCE
tijara.saas.stripe_certification_status / TIJARA_STRIPE_CERTIFICATION_STATUS
tijara.saas.jazzcash_certification_reference / TIJARA_JAZZCASH_CERTIFICATION_REFERENCE
tijara.saas.jazzcash_certification_status / TIJARA_JAZZCASH_CERTIFICATION_STATUS
tijara.saas.easypaisa_certification_reference / TIJARA_EASYPAISA_CERTIFICATION_REFERENCE
tijara.saas.easypaisa_certification_status / TIJARA_EASYPAISA_CERTIFICATION_STATUS
```

Use `approved`, `passed`, or `certified` for approved certification status.
Provider readiness reports should be captured in staging evidence before
including PSP certification folders in the final sign-off package.

Export PSP readiness evidence without exposing secrets:

```bash
python3 scripts/export_psp_readiness.py \
  --run-id 2026-06-05-rc1 \
  --target-environment staging \
  --provider stripe \
  --require-native-signatures \
  --secret-present stripe=true \
  --certification-reference stripe=STRIPE-UAT-001 \
  --certification-status stripe=approved
```

The exporter reads the committed provider adapter contracts and writes
`psp-readiness.json`, `status.tsv`, `env-summary.txt`, and `summary.md` under
`deploy/runtime/psp-readiness/<run-id>/`. Include this directory in
`TIJARA_SIGNOFF_EVIDENCE_PATHS` with the other PSP certification evidence.

Settlement import flow:

1. Run `make psp-fixture-smoke` to validate the committed provider fixture
   shape for JazzCash, Easypaisa, and Stripe before onboarding real statements.
2. Open SaaS Control > Payment Settlements.
3. Create a batch with provider, provider batch reference, settlement date, and
   expected gross/fee/net amounts when available. The selected provider sets
   the default parser profile for JazzCash, Easypaisa, Stripe, or manual bank
   statements.
4. Select statement format and parser profile, then paste the provider
   statement payload in `Statement Payload`.
5. Run `Import Statement`, then `Match Lines`.
6. Review mismatches in Settlement Lines and correct references or mark
   mismatch for PSP follow-up.
7. Run `Create Dispute Cases` for refund/chargeback lines.
8. Run `Generate Finance Actions` and review payout clearing, fee, refund,
   chargeback, write-off, or manual-review actions.
9. Run `Approve Finance` after finance review.
10. Run `Create Draft Moves` from the settlement batch, settlement line, or
   refund/chargeback case after finance configuration is complete. Use the
   individual accounting action `Create Draft Move` button for exception cases.
   Review draft journal lines, refund credit notes, and draft outbound refund
   payments before posting.
11. Mark the batch reconciled only after all lines are matched, no mismatch
   remains, and finance approval status is approved.

Finance account setup:

1. Open Settings > Companies and edit the tenant company.
2. Configure `Tijara Payment Accounting Journal` as the general journal used
   for PSP settlement entries.
3. Configure `Tijara PSP Clearing Account` for provider settlement clearing.
4. Configure `Tijara Payment Counterpart Account` for the bank/suspense side of
   payout clearing.
5. Configure provider fee expense, refund/credit-note, chargeback receivable,
   chargeback fee expense, and write-off expense accounts.
6. Configure `Tijara Refund Payment Journal` as the bank/cash journal used for
   outbound customer refunds.
7. Configure the refund payment journal outbound payment-method outstanding
   account and customer receivable accounts for refund customers.
8. Run a staging settlement import and create draft moves, refund credit notes,
   and draft refund payments for every action type before enabling production
   closeout.

Month-end settlement close SOP:

1. Import final PSP/bank statements for JazzCash, Easypaisa, Stripe, and manual
   bank transfers.
2. Match all settlement lines to webhooks, subscriptions, invoices, or approved
   manual references.
3. Open refund/chargeback cases, attach evidence, and resolve won/lost/refunded
   outcomes before finance close.
4. Generate and approve finance accounting actions.
5. Create draft accounting moves, refund credit notes, and refund payments from
   approved actions.
6. Review draft moves, credit notes, and refund payments against provider
   statements, bank statements, tax treatment, and write-off policy.
7. Post reviewed moves/payments through normal Odoo accounting controls.
8. Mark settlement batches reconciled and archive provider statements, evidence
   hashes, and closeout notes.

Refund and chargeback workflow:

- Webhook refund/chargeback events can create cases automatically when applied.
- Settlement refund/chargeback lines can create cases during settlement review.
- Open cases move the subscription to past due so a disputed/refunded tenant is
  not treated as cleanly paid.
- Evidence submission refreshes a deterministic evidence hash for audit.
- Winning a case restores the subscription to paid/active.
- Losing a case or completing a refund keeps the subscription past due and
  records the accounting action required.
- `Generate Finance Actions` creates auditable action rows for the required
  refund, chargeback fee, chargeback receivable, and write-off workflow.
- `Approve Finance` stamps the approval user/time and refreshes action hashes.

Production still needs real PSP statement samples for parser certification,
full finance sign-off for posting policy, tax treatment, PSP certification,
and formal finance reconciliation SOP sign-off.

## SaaS Enforcement

Feature flags are modeled in `tijara_saas_control`. Runtime enforcement can be
enabled with either:

```bash
TIJARA_SAAS_ENFORCEMENT_ENABLED=True
```

or the Odoo system parameter:

```text
tijara.saas.enforcement_enabled = 1
```

When enforcement is on, POS configuration blocks unavailable B2B sales, queue
system, promotion/menu/deals display, and customer-display settings unless the
active subscription includes the matching feature code.

## FBR Adapter

The FBR queue supports:

- `dry_run` mode for pilots and public-repo validation.
- `live` mode posting JSON to `FBR_ADAPTER_ENDPOINT` or the
  `tijara.fbr.endpoint` system parameter.
- Credentials from `FBR_CLIENT_SECRET` or `tijara.fbr.client_secret`.
- HTTPS-only live endpoints by default.
- Client ID and idempotency headers.
- Submission attempt tracking and response-status validation.
- Certification environment, certified provider name, provider credential
  reference, provider invoice UUID, sandbox/certification reference, signed
  payload hash, and compliance status fields.

Keep FBR credentials in the secret store. Enable the queued FBR cron only after
validating the adapter endpoint in staging.

Set `FBR_ALLOW_INSECURE_ENDPOINT=True` only for local/staging mock adapters.
Production certified adapters must use HTTPS.

Export redacted FBR readiness evidence before sign-off:

```bash
python3 scripts/export_fbr_readiness.py \
  --run-id 2026-06-05-rc1 \
  --target-environment production \
  --adapter-mode live \
  --certification-environment production \
  --provider-name CertifiedFBRProvider \
  --endpoint https://fbr-provider.example/api/invoices \
  --client-id client-001 \
  --credential-reference vault:fbr/client-secret \
  --sandbox-reference FBR-SANDBOX-001 \
  --fbr-pos-id POS-123 \
  --branch-code KHI-01 \
  --payload-hash <signed-payload-hash>
```

The exporter writes `fbr-readiness.json`, `status.tsv`, `env-summary.txt`, and
`summary.md` under `deploy/runtime/fbr-readiness/<run-id>/`. Include this
directory in `TIJARA_SIGNOFF_EVIDENCE_PATHS` and require the `fbr` evidence
group for production release sign-off.

Validate committed and sandbox certified-provider response fixtures before
FBR release sign-off:

```bash
python3 scripts/fbr_provider_fixture_smoke.py \
  --run-id 2026-06-05-rc1 \
  --target-environment production
```

The fixture smoke writes `fbr-fixture-smoke.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/fbr-fixture-smoke/<run-id>/`. Include this directory in
`TIJARA_SIGNOFF_EVIDENCE_PATHS`; the sign-off package extracts it under
`fbr_fixture_reviews` so approvers can see accepted/rejected fixture coverage,
provider names, sandbox/live environments, QR payload presence, and fixture
hashes.

## Kiosk POS Sync and Offline Queue

Kiosk profiles can optionally create linked Odoo POS orders when checkout is
submitted. Configure:

- `POS Register` on the kiosk profile.
- Payment capture mode: pay at counter, record paid, terminal reference, or
  provider webhook.
- Cash/card/bank POS payment method mappings.

When configured, kiosk orders store the linked POS session/order/payment method,
payment record, terminal/provider reference, sync timestamp, and any sync error.
If not configured, the kiosk can still submit an auditable kiosk order and queue
ticket for counter payment.

Offline POS browser capture now has three layers:

- POS frontend localStorage queueing for the active order when browser sync
  fails or the register is offline, plus a cashier-facing POS queue button that
  shows queued/blocked counts and triggers a replay check.
- Authenticated browser endpoints:
  - `POST /tijara/offline-pos/capture` to capture and optionally replay one
    offline order.
  - `POST /tijara/offline-pos/replay` to replay pending queue records for one
    device or all devices.
  - `GET /tijara/offline-pos/status` to return queue counts by state.
- Server-side replay into `pos.order`, POS order lines, POS payments, paid-order
  workflow, duplicate detection, replay attempts, and linked replayed order
  audit fields.
- Per-register advisory locking so replay into the same POS configuration is
  serialized before POS sequence/session/payment creation.
- Back-office review surfaces under POS Experience:
  - Offline Conflict Review for failed/conflict/queued/validated records.
  - Retry, cancel, mark duplicate, merge, manual mark replayed, and fail
    actions.
  - Reviewer, reviewed time, review note, duplicate/merge target, payload line
    count, payment count, total delta, replay attempts, and replay latency.
  - Offline Replay Audit pivot/graph views for operational reporting.
  - Offline Pilot Dashboard for queue age, attention state, failure bucket,
    outage reference, recovery owner, and cashier runbook notes.

The `Tijara Replay Offline POS Orders` cron is installed inactive by default.
Enable it only after staging proves product, payment-method, tax, stock-picking,
and duplicate handling for the target POS configuration. Full production offline
readiness still needs store-network pilots, physical payment-terminal/device
certification, load testing, and signed operational runbooks. The default
Playwright offline replay smoke runs on desktop; set
`TIJARA_RUN_MOBILE_OFFLINE_E2E=1` only for staging environments prepared to test
concurrent replay into the same POS register.

Before each offline pilot shift, assign a recovery owner and outage reference
for the target store/register. During drills, refresh pilot metrics and review
blocked/watch queues by failure bucket. Use the runbook note to record cashier
recovery actions such as paper receipt fallback, terminal reference capture,
manual duplicate review, and end-of-shift reconciliation.

## Monitoring and Logging

Start the open-source monitoring baseline:

```bash
make monitoring-up
```

This launches Prometheus, Blackbox Exporter, Alertmanager, Loki, and Grafana
with Odoo login and hardware bridge health checks. See
`deploy/monitoring/README.md`.

The local Prometheus config also scrapes Odoo business metrics:

```text
http://localhost:8069/tijara/monitoring/metrics?db=tijara_dev&token=dummy-prometheus-token-change-me
```

For production, replace `dummy-prometheus-token-change-me`, restrict the route
at the reverse proxy or network layer, and set the database/query/token values
in an environment-specific Prometheus config or secret-managed scrape config.
Odoo must also select the target tenant database before module routes are
mapped. Use a single-database deployment, `ODOO_DB_FILTER=<tenant_db>`, or a
host-based dbfilter per tenant; do not rely on the `db=` query parameter alone
when one Odoo service exposes multiple databases.

Logging guidance is in `deploy/logging/README.md`. Production should centralize
Odoo, PostgreSQL, Nginx/ingress, hardware bridge, FBR adapter, and backup job
logs with searchable retention. Loki is included as the first open-source log
aggregation baseline; production still needs log shippers and retention tuning.

Run the staging monitoring drill after bringing up Odoo, the hardware bridge,
monitoring services, and a backup artifact:

```bash
make monitoring-drill
```

The drill checks Odoo web, offline POS status, hardware bridge health,
Prometheus readiness, Alertmanager readiness, Grafana health, and the optional
`TIJARA_BACKUP_DRILL_FILE`. Override URLs with `TIJARA_STAGING_BASE_URL`,
`TIJARA_HARDWARE_BRIDGE_URL`, `TIJARA_PROMETHEUS_URL`,
`TIJARA_ALERTMANAGER_URL`, and `TIJARA_GRAFANA_URL`.

For release sign-off evidence, run the grouped operations harness:

```bash
TIJARA_OPS_CHECKS=monitoring,load,dependency make ops-staging
```

Use the full scope when restore and container scans are ready:

```bash
TIJARA_OPS_CHECKS=full TIJARA_RESTORE_DRILL_BACKUP=deploy/runtime/backups/latest.dump make ops-staging
```

The harness writes per-check logs, status, environment summary, and a Markdown
summary under `deploy/runtime/ops-evidence/<run-id>/`, plus a machine-readable
`ops-evidence.json` manifest. The harness exits non-zero when any status row is
failed. Set `TIJARA_OPS_STRICT=1` when skipped checks, missing tools, or missing
backup paths should fail the release drill. Set `TIJARA_OPS_REQUIRED_CHECKS` to
force specific checks to run and pass even in non-strict mode:

```bash
TIJARA_OPS_CHECKS=monitoring,restore,load,dependency,container \
TIJARA_OPS_REQUIRED_CHECKS=monitoring,restore,load,dependency,container \
TIJARA_RESTORE_DRILL_BACKUP=deploy/runtime/backups/latest.dump \
make ops-staging
```

Attach the whole `deploy/runtime/ops-evidence/<run-id>/` folder to sign-off.
`ops-evidence.json` is extracted into `ops_harness_reviews` with requested
checks, required checks, pass/fail/skipped/warning counts, and failed/skipped
check names.
When `load` is included, the harness writes `k6-load-summary.json`, runs
`scripts/export_load_evidence.py`, and stores structured load evidence under
`deploy/runtime/ops-evidence/<run-id>/load-evidence/` so release sign-off can
extract `load_reviews` without a separate manual step.

For release-owner review, generate a combined operations bundle after the
staging target, slugs, monitoring URLs, and owner references are configured:

```bash
TIJARA_OPS_BUNDLE_RUN_ID=2026-06-05-rc1 \
TIJARA_BASE_URL=https://staging.example.com \
TIJARA_DISPLAY_SLUG=tijara-e2e-menu \
TIJARA_KIOSK_SLUG=tijara-e2e-kiosk \
TIJARA_CUSTOMER_DISPLAY_SLUG=tijara-e2e-customer \
TIJARA_LOAD_MATRIX_APPROVED_BY="Release Owner" \
TIJARA_LOAD_MATRIX_APPROVAL_REF=LOAD-MATRIX-UAT-001 \
TIJARA_RELEASE_OWNER="Release Owner" \
TIJARA_DEVOPS_OWNER="DevOps Owner" \
TIJARA_SUPPORT_OWNER="Support Owner" \
TIJARA_BUSINESS_OWNER="Business Owner" \
TIJARA_ONCALL_CONTACT=oncall@example.com \
TIJARA_ALERT_ROUTE=alertmanager:tijara-staging \
TIJARA_INCIDENT_RUNBOOK_URL=https://runbooks.example.com/tijara/incident \
TIJARA_INCIDENT_BACKUP_REF=backup-2026-06-05 \
TIJARA_INCIDENT_RESTORE_DRILL_REF=restore-2026-06-05 \
TIJARA_INCIDENT_ROLLBACK_REF=odoo:previous \
make operations-release-bundle
```

The bundle writes `operations-release-bundle.json`, nested evidence
directories, logs, `status.tsv`, `env-summary.txt`, and `summary.md` under
`deploy/runtime/operations-release-bundle/<run-id>/`. Attach that directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence. Use
`TIJARA_OPS_BUNDLE_STRICT=1` and `TIJARA_OPS_BUNDLE_FAIL_ON_WARNING=1` for
production release drills where missing evidence or warnings must block.

On a protected runner, convert real command outputs into structured operations
tool evidence. Capture logs or JSON from the tools first, then export a single
machine-checkable evidence bundle:

```bash
mkdir -p deploy/runtime/ops-tool-raw/2026-06-05-rc1
CONFIRM_RESTORE_DRILL=YES bash deploy/postgres/restore-drill.sh deploy/runtime/backups/latest.dump \
  > deploy/runtime/ops-tool-raw/2026-06-05-rc1/restore-drill.log 2>&1
bash scripts/security_audit.sh \
  > deploy/runtime/ops-tool-raw/2026-06-05-rc1/security-audit.log 2>&1
npm audit --json \
  > deploy/runtime/ops-tool-raw/2026-06-05-rc1/npm-audit.json
pip-audit --format json \
  > deploy/runtime/ops-tool-raw/2026-06-05-rc1/pip-audit.json
trivy image --format json --severity HIGH,CRITICAL "${ODOO_IMAGE:-odoo:19.0}" \
  > deploy/runtime/ops-tool-raw/2026-06-05-rc1/trivy-odoo.json
k6 run --summary-export deploy/runtime/ops-tool-raw/2026-06-05-rc1/k6-summary.json \
  scripts/load_smoke.k6.js
TIJARA_BACKUP_DRILL_FILE=deploy/runtime/backups/latest.dump \
  python3 scripts/staging_monitoring_drill.py \
  > deploy/runtime/ops-tool-raw/2026-06-05-rc1/monitoring-drill.json
python3 scripts/export_ops_tool_evidence.py \
  --run-id 2026-06-05-rc1 \
  --target-environment production \
  --restore-drill-log deploy/runtime/ops-tool-raw/2026-06-05-rc1/restore-drill.log \
  --restore-drill-exit-code 0 \
  --backup-artifact-ref backup:2026-06-05-rc1 \
  --security-audit-log deploy/runtime/ops-tool-raw/2026-06-05-rc1/security-audit.log \
  --security-audit-exit-code 0 \
  --npm-audit-json deploy/runtime/ops-tool-raw/2026-06-05-rc1/npm-audit.json \
  --pip-audit-json deploy/runtime/ops-tool-raw/2026-06-05-rc1/pip-audit.json \
  --trivy-json deploy/runtime/ops-tool-raw/2026-06-05-rc1/trivy-odoo.json \
  --k6-summary-json deploy/runtime/ops-tool-raw/2026-06-05-rc1/k6-summary.json \
  --monitoring-drill-json deploy/runtime/ops-tool-raw/2026-06-05-rc1/monitoring-drill.json \
  --strict \
  --fail-on-warning
```

The exporter writes `ops-tool-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/ops-tool-evidence/<run-id>/`. Attach that directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS`; the sign-off package extracts
`ops_tool_reviews`. Production operations readiness can also consume it through
`--ops-tool-evidence`, and passed tool components satisfy restore, security,
dependency, container, monitoring-drill, and k6 load references.

Export the top-level production operations readiness gate after the operations
bundle and supporting evidence are available:

```bash
python3 scripts/export_production_ops_readiness.py \
  --run-id 2026-06-05-rc1 \
  --target-environment production \
  --operations-bundle deploy/runtime/operations-release-bundle/2026-06-05-rc1/operations-release-bundle.json \
  --monitoring-evidence deploy/runtime/operations-release-bundle/2026-06-05-rc1/monitoring-evidence/monitoring-evidence.json \
  --incident-runbook-evidence deploy/runtime/operations-release-bundle/2026-06-05-rc1/incident-runbook/incident-runbook-evidence.json \
  --load-evidence deploy/runtime/operations-release-bundle/2026-06-05-rc1/load-enterprise/load-evidence.json \
  --load-profile-matrix deploy/runtime/operations-release-bundle/2026-06-05-rc1/load-profile-matrix/load-profile-matrix.json \
  --release-retention-evidence deploy/runtime/operations-release-bundle/2026-06-05-rc1/release-retention/release-retention-evidence.json \
  --secret-manager-evidence deploy/runtime/secret-manager-evidence/2026-06-05-rc1/secret-manager-evidence.json \
  --secret-runtime-evidence deploy/runtime/secret-runtime-evidence/2026-06-05-rc1/secret-runtime-evidence.json \
  --deployment-environment-evidence deploy/runtime/deployment-environments/2026-06-05-rc1/deployment-environment-evidence.json \
  --tenant-ops-evidence deploy/runtime/tenant-ops-evidence/2026-06-05-rc1/tenant-ops-evidence.json \
  --ops-tool-evidence deploy/runtime/ops-tool-evidence/2026-06-05-rc1/ops-tool-evidence.json \
  --ops-status deploy/runtime/ops-evidence/2026-06-05-rc1/status.tsv \
  --backup-artifact-ref backup:2026-06-05-rc1 \
  --restore-drill-ref restore:2026-06-05-rc1 \
  --security-audit-ref security-audit:2026-06-05-rc1 \
  --dependency-scan-ref dependency-scan:2026-06-05-rc1 \
  --container-scan-ref container-scan:2026-06-05-rc1 \
  --strict \
  --fail-on-warning
```

The exporter writes `production-ops-readiness.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/production-ops-readiness/<run-id>/`. Attach that directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS`; the sign-off package extracts
`production_ops_readiness_reviews`, and production readiness blocks when this
gate is blocked or failed.

Warnings remain release blockers in the protected workflow because
`export_production_ops_readiness.py` is called with `--fail-on-warning`. To
approve a temporary production-ops warning without weakening the default gate,
set all of these protected GitHub Environment variables for that run:

```bash
TIJARA_PROD_OPS_ALLOW_WARNING_EXCEPTION=1
TIJARA_PROD_OPS_WARNING_EXCEPTION_REF=change:TIJARA-PROD-EXCEPTION-001
TIJARA_PROD_OPS_WARNING_EXCEPTION_APPROVED_BY=ReleaseOwner
TIJARA_PROD_OPS_WARNING_EXCEPTION_REASON="Temporary approved exception for one monitored warning."
TIJARA_PROD_OPS_WARNING_EXCEPTION_EXPIRES_AT=2026-06-30
TIJARA_PROD_OPS_WARNING_EXCEPTION_AUDIT_REF=audit:prod-ops-warning-2026-06-05
```

The exporter records the exception in `production-ops-readiness.json`,
`summary.md`, and the sign-off package. The readiness decision remains
`warning`/`pass_with_warnings`; missing, incomplete, or expired exception
metadata still blocks when `--fail-on-warning` is active.

The protected operator handoff also records the exception operating procedure in
`warning-exception-runbook.md`. When an exception is enabled, the strict handoff
requires reference, approver, reason, future expiry, and audit reference before
the release-owner go/no-go review can pass. The runbook includes approval,
expiry, and audit steps so the exception is removed or re-approved before it
expires.

## Display Routes

Public display routes are available for store screens:

```text
/tijara/display/<slug>
/tijara/display/<slug>/data
/tijara/kiosk/<slug>
/tijara/kiosk/<slug>/data
/tijara/kiosk/<slug>/checkout
/tijara/ecommerce/<slug>
/tijara/ecommerce/<slug>/catalog
/tijara/ecommerce/<slug>/checkout
/tijara/ecommerce/<slug>/track
/tijara/ecommerce/<slug>/orders
/tijara/ecommerce/<slug>/account
```

Use HTTPS and reverse-proxy rate limiting in production. The baseline Nginx file
already rate-limits login, database, JSON-RPC, display, and kiosk paths.

Seed staging browser data:

```bash
TIJARA_E2E_SEED_RUN_ID=staging-pos-seed-001 \
TIJARA_E2E_PASSWORD=<staging-test-password> \
make seed-e2e DB=tijara_dev

source deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed.env
export ODOO_PASSWORD=<staging-test-password>
export TIJARA_RUN_POS_UI_E2E=1
export TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1
ODOO_BASE_URL=http://127.0.0.1:8069 npm run test:e2e
```

`make seed-e2e` writes `seed-output.log`, `e2e-seed.env`, `status.tsv`,
`summary.md`, and `e2e-seed-evidence.json` under
`deploy/runtime/e2e-seed/<run-id>/`. The env file contains only non-secret
exports; load `ODOO_PASSWORD` from the staging secret manager before browser
E2E. Attach the seed evidence folder to sign-off packages as Browser E2E
evidence.

Validate the live staging E2E profile before browser execution:

```bash
TIJARA_E2E_PROFILE_RUN_ID=staging-pos-seed-001 \
TIJARA_E2E_PROFILE_STRICT=1 \
TIJARA_E2E_PROFILE_REQUIRE_SEED=1 \
TIJARA_E2E_SEED_ENV=deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed.env \
TIJARA_E2E_SEED_EVIDENCE=deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed-evidence.json \
TIJARA_E2E_OWNER="QA Owner" \
TIJARA_E2E_RUNBOOK_REF=docs:DEPLOY.md#display-routes \
TIJARA_E2E_CHANGE_REF=change:TIJARA-STAGE-E2E-001 \
make staging-e2e-profile
```

Set `TIJARA_E2E_PROFILE_PROBE_BASE_URL=1` only when the staging Odoo URL is
reachable from the runner and `/web/login` should be probed. The profile writes
`staging-e2e-profile.json`, `status.tsv`, `env-summary.txt`, and `summary.md`
under `deploy/runtime/e2e-profile/<run-id>/`; attach that directory to sign-off
packages as Browser E2E evidence. Secret values are masked.

For staging sign-off, run the guarded evidence harness instead of a raw
Playwright command:

```bash
TIJARA_E2E_SCOPE=full ODOO_BASE_URL=https://staging.example.com make e2e-staging
```

The harness verifies the required slugs, credentials, POS config/product/payment
IDs, refund barcode, report URL, and offline review URL before running. Evidence
is written to `deploy/runtime/e2e-evidence/<run-id>/` with an environment
summary, Playwright output, JSON results, and a Markdown summary. Use
`TIJARA_E2E_SCOPE=public` for display/kiosk/customer-display/ecommerce routes
or `TIJARA_E2E_SCOPE=authenticated` for POS/refund/offline-report routes.
Public scope requires `TIJARA_ECOMMERCE_SLUG`; with seeded demo data use
`TIJARA_ECOMMERCE_SLUG=tijara-demo-web`. Ecommerce browser coverage verifies
catalog payloads, PKR/Urdu/B2B/B2C pricing, storefront pickup checkout,
delivery checkout, charge policy, queue handoff, and authenticated online-order
review when ecommerce manager credentials are exported.
Authenticated and full scopes also run the integrated enterprise POS journey:
paid browser/offline order capture, POS replay, receipt report rendering,
print-to-bridge method coverage, optional customer-display state assertion,
refund barcode matching from the generated receipt, duplicate replay handling,
and offline status reporting.
Direct cashier POS UI product search, add-to-cart, payment navigation, optional
sale validation/receipt print, and refund barcode form selectors are available
with `TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1`,
`TIJARA_RUN_DIRECT_POS_VALIDATE_E2E=1`, and
`TIJARA_RUN_DIRECT_REFUND_FORM_E2E=1`.

Correlate seed, profile, browser E2E, and sign-off evidence after a staging run:

```bash
TIJARA_E2E_EXECUTION_RUN_ID=staging-pos-seed-001 \
TIJARA_E2E_EXECUTION_STRICT=1 \
TIJARA_E2E_EXECUTION_SEED_EVIDENCE=deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed-evidence.json \
TIJARA_E2E_EXECUTION_PROFILE_EVIDENCE=deploy/runtime/e2e-profile/staging-pos-seed-001/staging-e2e-profile.json \
TIJARA_E2E_EXECUTION_E2E_DIR=deploy/runtime/e2e-evidence/staging-pos-seed-001 \
TIJARA_E2E_EXECUTION_SIGNOFF_READINESS=deploy/runtime/signoff-packages/staging-pos-seed-001/release-readiness.json \
make e2e-execution-evidence
```

The combiner writes `e2e-execution-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/e2e-execution/<run-id>/`. Because it references final
`release-readiness.json`, it normally runs after the sign-off package is
generated; attach it to a follow-up/final sign-off package when release owners
want one Browser E2E execution decision for the whole chain.

## CI, Security, and Load Smoke

The first GitHub Actions workflow is `.github/workflows/tijara-ci.yml`. Local
operators can run:

```bash
make validate
make js-check
make security-audit
make config
```

CI also runs a local release-candidate evidence path:

```bash
TIJARA_RELEASE_RUN_ID=ci-local TIJARA_RELEASE_CHECKS=local make release-candidate
python3 scripts/export_release_retention_evidence.py \
  --run-id ci-local \
  --target-environment ci \
  --output deploy/runtime/release-retention-evidence/ci-local \
  --artifact-store-reference github-actions:tijara-ci-release-evidence \
  --artifact-retention-policy-ref github-actions:retention-days-30 \
  --certification-retention-policy-ref docs:DEPLOY.md#external-certification-evidence-intake \
  --secret-manager-provider github-actions-secrets \
  --secret-manager-reference github-actions:tijara-ci \
  --secret-rotation-policy-ref docs:DEPLOY.md#secret-handling \
  --ci-artifact-retention-days 30 \
  --release-evidence-retention-days 365 \
  --certification-evidence-retention-days 365 \
  --log-retention-days 30 \
  --backup-retention-days 30 \
  --evidence-path deploy/runtime/release-evidence/ci-local \
  --strict
python3 scripts/export_secret_manager_evidence.py \
  --run-id ci-local \
  --target-environment ci \
  --output deploy/runtime/secret-manager-evidence/ci-local \
  --secret-manager-provider github-actions-secrets \
  --secret-manager-reference github-actions:tijara-ci \
  --secret-rotation-policy-ref docs:DEPLOY.md#secret-handling \
  --secret-access-review-ref docs:DEPLOY.md#secret-handling \
  --strict
python3 scripts/export_e2e_readiness.py \
  --run-id ci-local \
  --scope ci-browser-baseline \
  --base-url http://localhost:8069 \
  --output deploy/runtime/e2e-evidence/ci-local \
  --spec tests/e2e/pos-checkout-print.spec.mjs \
  --spec tests/e2e/refunds-reports.spec.mjs \
  --spec tests/e2e/pos-enterprise-journey.spec.mjs
python3 scripts/export_production_ops_readiness.py \
  --run-id ci-local \
  --target-environment ci \
  --output deploy/runtime/production-ops-readiness/ci-local \
  --release-retention-evidence deploy/runtime/release-retention-evidence/ci-local/release-retention-evidence.json \
  --secret-manager-evidence deploy/runtime/secret-manager-evidence/ci-local/secret-manager-evidence.json \
  --backup-artifact-ref github-actions:tijara-ci/no-production-backup \
  --restore-drill-ref github-actions:tijara-ci/no-production-restore \
  --security-audit-ref github-actions:tijara-ci/security-audit \
  --dependency-scan-ref github-actions:tijara-ci/dependency-scan
TIJARA_SIGNOFF_RUN_ID=ci-local \
TIJARA_SIGNOFF_ENVIRONMENT=ci \
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/ci-local,deploy/runtime/e2e-evidence/ci-local,deploy/runtime/release-retention-evidence/ci-local,deploy/runtime/secret-manager-evidence/ci-local,deploy/runtime/production-ops-readiness/ci-local \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops,security \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
make signoff-pack
make check-release-readiness READINESS=deploy/runtime/signoff-packages/ci-local/release-readiness.json
```

The workflow uploads `deploy/runtime/release-evidence/ci-local`,
`deploy/runtime/e2e-evidence/ci-local`,
`deploy/runtime/release-retention-evidence/ci-local`,
`deploy/runtime/secret-manager-evidence/ci-local`,
`deploy/runtime/production-ops-readiness/ci-local`, and
`deploy/runtime/signoff-packages/ci-local` as the
`tijara-ci-release-evidence` artifact with `retention-days: 30` and
`if-no-files-found: error`. This is not a substitute for staging release
evidence, but it prevents PRs from merging with a broken local release gate,
malformed readiness package, missing CI artifact retention evidence, or missing
runtime secret-manager evidence. The public CI production-ops readiness step is
warning-mode by design until a protected staging/production runner has live
monitoring, restore, load, scan, and secret-runtime access.

Prepare the self-hosted protected runner before staging or production drills.
The bootstrap tool is dry-run by default and writes a secret-free install plan,
current tool/version scan, exact protected preflight command, and GitHub
environment notes:

```bash
bash scripts/bootstrap_protected_runner.sh \
  --config deploy/config/protected-runner-bootstrap.env.example \
  --target-os ubuntu \
  --dry-run \
  --output deploy/runtime/protected-runner-bootstrap/2026-06-05-rc1
```

Review `install-plan.sh` with the DevOps owner, then run it during runner
maintenance only when approved:

```bash
bash scripts/bootstrap_protected_runner.sh \
  --config deploy/config/protected-runner-bootstrap.env.example \
  --target-os ubuntu \
  --apply \
  --output deploy/runtime/protected-runner-bootstrap/2026-06-05-rc1
```

The generated plan installs or verifies open-source runner prerequisites:
`python3`, `node`, `npm`, Docker with the Compose plugin, `trivy`, `k6`,
`psql`, `pg_dump`, `pg_restore`, optional `pip-audit`, and optional GitHub CLI.
After applying the plan, run the generated `preflight-command.sh`; its output
must satisfy `scripts/export_protected_runner_preflight.py` before dispatching
the protected release. Keep package installation outside the release workflow
itself so production evidence runs only prove readiness and do not mutate the
runner.

After bootstrap and preflight evidence both exist, correlate them:

```bash
python3 scripts/export_protected_runner_bootstrap_verification.py \
  --run-id 2026-06-05-rc1 \
  --target-environment staging \
  --bootstrap-evidence deploy/runtime/protected-runner-bootstrap/2026-06-05-rc1 \
  --preflight-evidence deploy/runtime/protected-runner-preflight/2026-06-05-rc1/protected-runner-preflight.json \
  --output deploy/runtime/protected-runner-bootstrap-verification/2026-06-05-rc1 \
  --strict
```

The verifier writes `protected-runner-bootstrap-verification.json`,
`tool-correlation.tsv`, `status.tsv`, `env-summary.txt`, and `summary.md`.
Protected CI also runs the verifier after preflight. By default it warns when
no external bootstrap evidence path is attached; set
`TIJARA_BOOTSTRAP_VERIFICATION_BOOTSTRAP_EVIDENCE` and
`TIJARA_BOOTSTRAP_VERIFICATION_STRICT=1` after the real runner bootstrap has
been executed and archived.

For staging or production drills, use the manual `workflow_dispatch` profile in
the same workflow:

1. Configure a self-hosted runner with labels `self-hosted` and
   `tijara-protected`.
   Install the protected toolchain before dispatching a release:
   `python3`, `node`, `npm`, Docker with the Compose plugin, `trivy`, `k6`,
   `psql`, `pg_dump`, and `pg_restore`. `pip-audit` and the GitHub CLI (`gh`)
   are optional by default but are reported by preflight when present or
   missing. Override `TIJARA_PREFLIGHT_REQUIRED_TOOLS` and
   `TIJARA_PREFLIGHT_OPTIONAL_TOOLS` per environment if your runner contract is
   stricter. Use `deploy/config/protected-runner-bootstrap.env.example` and
   `make protected-runner-bootstrap` to generate the install plan and the exact
   preflight command for that runner image.
2. Configure the GitHub environment named `staging` or `production` with the
   required secrets and variables for Odoo, Playwright, backup restore drills,
   artifact storage, secret manager references, runtime secret probes,
   deployment approvers/gates, tenant operations artifacts, monitoring/incident
   references, PSP/FBR/hardware certification evidence paths, Trivy, k6, npm,
   and optional pip-audit.
   Use `deploy/config/github-protected-vars.example` for non-secret environment
   variables and `secrets/github-protected-secrets.example` for the required
   secret names. Use the JSON templates under
   `deploy/config/certification-manifests/` as starting points for PSP, FBR,
   and hardware evidence bundles.
3. Start the workflow manually with `protected_release=true`,
   `target_environment=staging` or `production`, and an optional `run_id`.

The protected job first exports an operator handoff runbook under
`deploy/runtime/protected-runbook-handoff/<run-id>/`, then exports a first-run
checklist under `deploy/runtime/protected-first-run/<run-id>/`, exports
redacted runner preflight evidence under
`deploy/runtime/protected-runner-preflight/<run-id>/`, including required and
optional toolchain availability/version checks, exports protected runner
bootstrap verification under
`deploy/runtime/protected-runner-bootstrap-verification/<run-id>/`, runs the
authenticated service checks under
`deploy/runtime/protected-service-checks/<run-id>/`, exports protected PSP/FBR
provider readiness under
`deploy/runtime/protected-provider-readiness/<run-id>/`, exports protected
payment lifecycle evidence under
`deploy/runtime/protected-payment-lifecycle/<run-id>/`, runs the
release-candidate gate, runs protected Browser E2E
seed/profile/browser/execution evidence under
`deploy/runtime/protected-e2e/<run-id>/`, exports protected offline POS replay
evidence under `deploy/runtime/protected-offline-replay/<run-id>/`, captures raw
restore, security, dependency, container, npm audit, optional pip-audit, Trivy
JSON, k6, and monitoring-drill outputs under
`deploy/runtime/ops-tool-raw/<run-id>/`, exports strict operations tool
evidence, runs the operations release bundle under
`deploy/runtime/operations-release-bundle/<run-id>/`, exports standalone
monitoring evidence under `deploy/runtime/monitoring-evidence/<run-id>/`,
incident runbook evidence under `deploy/runtime/incident-runbooks/<run-id>/`,
runtime secret delivery evidence under
`deploy/runtime/secret-runtime-evidence/<run-id>/`, deployment environment
protection evidence under `deploy/runtime/deployment-environments/<run-id>/`,
and tenant operations evidence under
`deploy/runtime/tenant-ops-evidence/<run-id>/`. It then collects strict
PSP/FBR/hardware certification evidence when the matching `TIJARA_CERT_*`
variables are configured, exports retention and secret-manager evidence, runs
strict production operations readiness with all of those inputs attached,
generates the protected sign-off package, checks `release-readiness.json`, and
exports a post-run evidence verifier under
`deploy/runtime/protected-post-run-verification/<run-id>/`. It then prepares a
pre-upload GitHub artifact metadata placeholder under
`deploy/runtime/github-artifact-metadata/<run-id>/`, writes the final protected
artifact summary, writes a protected run decision under
`deploy/runtime/protected-run-decision/<run-id>/`, publishes a compact GitHub
Actions step summary with release-readiness, production-ops, post-run,
artifact-summary, run-decision, blocker, warning, and component status, and
uploads the main evidence bundle as
`tijara-protected-release-evidence-<environment>-<run>`. After that upload, the
workflow records the real upload action outputs such as artifact ID, artifact
URL, digest, and retention metadata, writes a protected evidence retention
manifest under `deploy/runtime/protected-evidence-retention/<run-id>/`, then
uploads a sidecar artifact named
`tijara-protected-artifact-metadata-<environment>-<run>`. After the sidecar
upload, the workflow verifies the sidecar artifact ID, URL, digest, retention
days, expected evidence files, and retention-manifest consistency under
`deploy/runtime/protected-sidecar-verification/<run-id>/`, exports a protected
evidence replay report under
`deploy/runtime/protected-evidence-replay/<run-id>/`, writes one protected
release evidence index under
`deploy/runtime/protected-release-evidence-index/<run-id>/`, exports the final
protected release closure gate under
`deploy/runtime/protected-release-closure/<run-id>/`, appends a final GitHub
Actions summary, and uploads
`tijara-protected-sidecar-verification-<environment>-<run>`. After that final
upload, it verifies the returned artifact ID, URL, digest, retained closure
decision, promotion checklist, evidence index, replay report, and sidecar
verification under
`deploy/runtime/protected-closure-result-verification/<run-id>/`, exports a
protected release archive manifest under
`deploy/runtime/protected-release-archive/<run-id>/`, appends a
closure-result summary including the archive verdict, and uploads
`tijara-protected-closure-result-<environment>-<run>`. It then verifies that
final closure-result artifact upload under
`deploy/runtime/protected-archive-upload-verification/<run-id>/`, appends a
protected archive upload summary with the protected evidence bundle score, and uploads
`tijara-protected-archive-upload-<environment>-<run>`. After the main
upload metadata is recorded, the workflow also appends a second GitHub Actions
summary and writes `github-step-summary-post-upload.md` under
`deploy/runtime/github-artifact-metadata/<run-id>/`, including artifact ID,
URL, digest, retention days, and the retention-manifest verdict. If a strict
evidence step fails, the job still tries to build the final sign-off package so
the release-readiness JSON explains the blocker.

Set `TIJARA_PROTECTED_CERTIFICATION_GROUPS=psp,fbr,hardware` in the protected
GitHub environment when external certification must be mandatory for the
release. The protected sign-off package will append certification evidence
directories to `TIJARA_SIGNOFF_EVIDENCE_PATHS` and require the selected groups;
missing, expired, unapproved, or hash-mismatched certification evidence becomes
a release-readiness blocker.

`make protected-certification-evidence` also writes root execution evidence at
`deploy/runtime/certification-evidence/<run-id>/certification-execution.json`,
`status.tsv`, `env-summary.txt`, and `summary.md`. Any group listed in
`TIJARA_PROTECTED_CERTIFICATION_GROUPS` must be configured through its matching
`TIJARA_CERT_*` variables; otherwise the protected certification runner exits
failed instead of silently skipping it. Unrequested categories are recorded as
skipped optional groups.

The protected workflow also exports
`deploy/runtime/certification-evidence/<run-id>/result-matrix/` with
`certification-result-matrix.json`, `status.tsv`, `env-summary.txt`, and
`summary.md`. The matrix merges root certification execution, PSP/FBR/hardware
evidence, approvals, validity dates, evidence counts, and optional PSP/FBR
provider-readiness evidence into one release-owner review. Set
`TIJARA_CERTIFICATION_MATRIX_REQUIRE_PROVIDER_READINESS=1` when PSP/FBR
provider readiness must be attached to the matrix, and set
`TIJARA_CERTIFICATION_MATRIX_FAIL_ON_WARNING=1` when warning rows should block
the protected release.

Generate the protected operator handoff before the first live staging run so
the release owner, DevOps, QA, support, security, and business reviewers have
the exact commands and review order in one evidence folder:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
TIJARA_FIRST_RUN_GITHUB_ENVIRONMENT=staging \
TIJARA_FIRST_RUN_RUNNER_LABELS=self-hosted,tijara-protected \
TIJARA_FIRST_RUN_RELEASE_OWNER=ReleaseOwner \
TIJARA_FIRST_RUN_DEVOPS_OWNER=DevOpsOwner \
TIJARA_FIRST_RUN_QA_OWNER=QAOwner \
TIJARA_FIRST_RUN_BUSINESS_OWNER=BusinessOwner \
TIJARA_FIRST_RUN_SECURITY_OWNER=SecurityOwner \
TIJARA_FIRST_RUN_SUPPORT_OWNER=SupportOwner \
TIJARA_FIRST_RUN_STAGING_URL=https://staging.example.com \
TIJARA_FIRST_RUN_CHANGE_TICKET_REF=change:protected-staging-first-run \
TIJARA_FIRST_RUN_ROLLBACK_PLAN_REF=runbook:rollback-protected-staging \
TIJARA_FIRST_RUN_INCIDENT_CHANNEL_REF=slack:tijara-incidents \
TIJARA_FIRST_RUN_BACKUP_REF=backup:staging-latest \
TIJARA_FIRST_RUN_PROTECTED_WORKFLOW_REF=workflow:tijara-ci/protected-release-evidence \
python3 scripts/export_protected_runbook_handoff.py \
  --output deploy/runtime/protected-runbook-handoff/2026-06-05-rc1 \
  --strict
```

The handoff writes `operator-runbook.md`, `artifact-review-order.md`,
`go-no-go-checklist.md`, `protected-runbook-handoff.json`, and `status.tsv`.
Attach it to `TIJARA_SIGNOFF_EVIDENCE_PATHS`; the protected workflow does this
automatically.

Run the first-run checklist locally before the first protected staging workflow
to confirm the non-secret handoff is complete:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
TIJARA_FIRST_RUN_GITHUB_ENVIRONMENT=staging \
TIJARA_FIRST_RUN_RUNNER_LABELS=self-hosted,tijara-protected \
TIJARA_FIRST_RUN_RELEASE_OWNER=ReleaseOwner \
TIJARA_FIRST_RUN_DEVOPS_OWNER=DevOpsOwner \
TIJARA_FIRST_RUN_QA_OWNER=QAOwner \
TIJARA_FIRST_RUN_BUSINESS_OWNER=BusinessOwner \
TIJARA_FIRST_RUN_SECURITY_OWNER=SecurityOwner \
TIJARA_FIRST_RUN_SUPPORT_OWNER=SupportOwner \
TIJARA_FIRST_RUN_STAGING_URL=https://staging.example.com \
TIJARA_FIRST_RUN_CHANGE_TICKET_REF=change:protected-staging-first-run \
TIJARA_FIRST_RUN_ROLLBACK_PLAN_REF=runbook:rollback-protected-staging \
TIJARA_FIRST_RUN_INCIDENT_CHANNEL_REF=slack:tijara-incidents \
TIJARA_FIRST_RUN_BACKUP_REF=backup:staging-latest \
TIJARA_FIRST_RUN_PROTECTED_WORKFLOW_REF=workflow:tijara-ci/protected-release-evidence \
python3 scripts/export_protected_first_run_checklist.py \
  --output deploy/runtime/protected-first-run/2026-06-05-rc1 \
  --strict
```

When `TIJARA_PROTECTED_CERTIFICATION_GROUPS` includes `psp`, `fbr`, or
`hardware`, also provide `TIJARA_FIRST_RUN_FINANCE_OWNER`,
`TIJARA_FIRST_RUN_TAX_OWNER`, and `TIJARA_FIRST_RUN_HARDWARE_OWNER`
respectively. The manifest rejects secret-like metadata keys and records only
owner names, refs, labels, expected artifact groups, and checklist decisions.

After a protected run, verify the final artifact folders before release-owner
review:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_post_run_verification.py \
  --output deploy/runtime/protected-post-run-verification/2026-06-05-rc1 \
  --strict
```

The verifier checks required artifact folders, failed/warning `status.tsv`
rows, JSON `decision`/`ci_status` values, and
`deploy/runtime/signoff-packages/<run-id>/release-readiness.json`. It writes
`protected-post-run-verification.json`, `evidence-overview.md`, `status.tsv`,
`env-summary.txt`, and `summary.md`.

Generate the final protected run decision after post-run verification and
protected artifact summary:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_run_decision.py \
  --output deploy/runtime/protected-run-decision/2026-06-05-rc1 \
  --required-components release-readiness,production-ops-readiness,protected-post-run-verification,protected-artifact-summary,certification-result-matrix,e2e-execution,protected-offline-pilot,operations-release-bundle,ops-tool-evidence \
  --strict \
  --fail-on-warning
```

The decision exporter reads the core protected evidence JSON files and writes
`protected-run-decision.json`, `status.tsv`, `env-summary.txt`, and
`summary.md`. Set `TIJARA_PROTECTED_RUN_DECISION_REQUIRED_COMPONENTS` to change
which components are mandatory, and set
`TIJARA_PROTECTED_RUN_DECISION_FAIL_ON_WARNING=0` only when a release owner has
approved warning-mode protected runs.

Capture GitHub artifact metadata locally or in a protected runner:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_github_artifact_metadata.py \
  --artifact-name tijara-protected-release-evidence-staging-123456 \
  --artifact-id 123456789 \
  --artifact-url https://github.com/org/repo/actions/runs/123456/artifacts/123456789 \
  --retention-days 30 \
  --stage post_upload \
  --output deploy/runtime/github-artifact-metadata/2026-06-05-rc1 \
  --strict
```

When a `gh api repos/<owner>/<repo>/actions/runs/<run-id>/artifacts` response
is available, pass it with `--artifacts-json` and the exporter will match by
artifact name and record ID, API URL, archive download URL, size, expiry, and
workflow context without writing token values.

Generate the protected evidence retention manifest after GitHub artifact
metadata has been recorded:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_evidence_retention_manifest.py \
  --output deploy/runtime/protected-evidence-retention/2026-06-05-rc1 \
  --required-components protected-run-decision,signoff-package,release-readiness,certification-result-matrix,github-artifact-metadata,protected-artifact-summary,release-retention-evidence \
  --strict \
  --fail-on-warning
```

The retention manifest fingerprints every retained file in the final decision,
sign-off package, release-readiness JSON, certification matrix, artifact
summary, release-retention evidence, and GitHub artifact metadata. It writes
`protected-evidence-retention-manifest.json`, `status.tsv`,
`env-summary.txt`, and `summary.md`. The post-upload protected sidecar artifact
includes this folder beside `github-artifact-metadata`.

Verify the protected metadata sidecar after the sidecar upload action has
returned artifact outputs:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_sidecar_verification.py \
  --output deploy/runtime/protected-sidecar-verification/2026-06-05-rc1 \
  --sidecar-artifact-name tijara-protected-artifact-metadata-staging-123456 \
  --sidecar-artifact-id 987654321 \
  --sidecar-artifact-url https://github.com/org/repo/actions/runs/123456/artifacts/987654321 \
  --sidecar-artifact-digest sha256:example \
  --sidecar-retention-days 30 \
  --minimum-retention-days 30 \
  --strict \
  --fail-on-warning
```

The sidecar verifier checks the local sidecar paths for
`github-artifact-metadata.json` and
`protected-evidence-retention-manifest.json`, confirms the sidecar upload
metadata is present, confirms retention days meet policy, and verifies the
retention manifest still matches the primary uploaded release artifact metadata.
It writes `protected-sidecar-verification.json`, `status.tsv`,
`env-summary.txt`, and `summary.md`.

Export a release-owner audit replay packet after sidecar verification:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_evidence_replay_report.py \
  --output deploy/runtime/protected-evidence-replay/2026-06-05-rc1 \
  --required-components release-readiness,protected-run-decision,github-artifact-metadata,protected-evidence-retention,protected-sidecar-verification \
  --strict \
  --fail-on-warning
```

The replay report consumes release-readiness, protected run decision, GitHub
artifact metadata, evidence retention, and sidecar verification JSON files. It
checks decision status, primary artifact consistency, sidecar artifact metadata,
and digest/url/id continuity, then writes
`protected-evidence-replay-report.json`, `audit-replay.md`, `status.tsv`,
`env-summary.txt`, and `summary.md`.

Build the final operator-facing protected release evidence index:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_release_evidence_index.py \
  --output deploy/runtime/protected-release-evidence-index/2026-06-05-rc1 \
  --required-components release-readiness,protected-run-decision,protected-evidence-retention,protected-sidecar-verification,protected-evidence-replay,signoff-package,certification-result-matrix,github-artifact-metadata \
  --strict \
  --fail-on-warning
```

The index writes `operator-index.md` for release owners and
`protected-release-evidence-index.json` for automation. It links the final
run-decision, release-readiness, sign-off package, certification matrix,
retention manifest, sidecar verification, replay report, and GitHub artifact
URLs in one page.

Export the final closure gate after the evidence index is available:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_release_closure_gate.py \
  --output deploy/runtime/protected-release-closure/2026-06-05-rc1 \
  --required-components release-readiness,protected-run-decision,protected-evidence-retention,protected-sidecar-verification,protected-evidence-replay,signoff-package,certification-result-matrix,github-artifact-metadata \
  --release-owner release:owner \
  --devops-owner devops:owner \
  --qa-owner qa:owner \
  --security-owner security:owner \
  --business-owner business:owner \
  --change-ticket-ref change:123 \
  --rollback-plan-ref runbook:rollback \
  --incident-channel-ref slack:tijara-incidents \
  --strict \
  --fail-on-warning \
  --require-approvals
```

The closure gate writes `protected-release-closure-decision.json`,
`promotion-checklist.md`, `status.tsv`, `env-summary.txt`, and `summary.md`.
It returns `promotion_ready` only when the evidence index is passing, required
artifact links and review files are present, approvals are attached, and no
warnings are being treated as blockers.

Verify the uploaded closure result after the final protected sidecar artifact
has uploaded:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_closure_result_verification.py \
  --output deploy/runtime/protected-closure-result-verification/2026-06-05-rc1 \
  --final-artifact-name tijara-protected-sidecar-verification-staging-123456 \
  --final-artifact-id 1122334455 \
  --final-artifact-url https://github.com/org/repo/actions/runs/123456/artifacts/1122334455 \
  --final-artifact-digest sha256:example \
  --final-retention-days 30 \
  --minimum-retention-days 30 \
  --strict \
  --fail-on-warning
```

The closure result verifier writes
`protected-closure-result-verification.json`, `closure-result.md`,
`status.tsv`, `env-summary.txt`, and `summary.md`. A `blocked` closure can
still pass this verifier when the blocked decision is captured and uploaded
correctly.

Export the long-term protected release archive after closure-result
verification:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_release_archive_manifest.py \
  --output deploy/runtime/protected-release-archive/2026-06-05-rc1 \
  --minimum-retention-days 30 \
  --strict \
  --fail-on-warning
```

The archive exporter writes `protected-release-archive-manifest.json`,
`archive-index.md`, `status.tsv`, `env-summary.txt`, and `summary.md`. It
correlates the primary GitHub artifact, retention manifest, sidecar artifact,
replay report, evidence index, closure gate, closure-result verification, and
release-retention policy so release owners can reconstruct the exact protected
decision later, including valid `promotion_ready`, `watch`, or `blocked`
outcomes.

Verify the final closure-result artifact upload after GitHub returns its
artifact metadata:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_archive_upload_verification.py \
  --output deploy/runtime/protected-archive-upload-verification/2026-06-05-rc1 \
  --final-artifact-name tijara-protected-closure-result-staging-123456 \
  --final-artifact-id 2233445566 \
  --final-artifact-url https://github.com/org/repo/actions/runs/123456/artifacts/2233445566 \
  --final-artifact-digest sha256:example \
  --final-retention-days 30 \
  --minimum-retention-days 30 \
  --strict \
  --fail-on-warning
```

The upload verifier writes `protected-archive-upload-verification.json`,
`archive-upload.md`, `status.tsv`, `env-summary.txt`, and `summary.md`. It
confirms the uploaded closure-result artifact metadata is present, the archive
manifest and closure-result verifier agree on the closure decision, and the
expected archive files were present in the final upload paths.

Export the protected evidence bundle score once archive-upload verification is
available:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_evidence_bundle_score.py \
  --output deploy/runtime/protected-evidence-bundle-score/2026-06-05-rc1 \
  --required-components protected-run-decision,protected-evidence-retention,protected-sidecar-verification,protected-evidence-replay,protected-release-evidence-index,protected-release-closure,protected-closure-result-verification,protected-release-archive,protected-archive-upload-verification \
  --minimum-score 90 \
  --strict \
  --fail-on-warning
```

The score exporter writes `protected-evidence-bundle-score.json`,
`release-owner-risk-matrix.md`, `scorecard.tsv`, `status.tsv`,
`env-summary.txt`, and `summary.md`. It separates evidence completeness from
release risk: a blocked closure can be fully traceable, but the scorecard still
marks the release outcome as blocked for release-owner review.

Compare the protected evidence bundle score against a previous approved
baseline before release-owner approval:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc2 \
TIJARA_TARGET_ENVIRONMENT=staging \
python3 scripts/export_protected_evidence_bundle_drift.py \
  --current-score deploy/runtime/protected-evidence-bundle-score/2026-06-05-rc2/protected-evidence-bundle-score.json \
  --baseline-score deploy/runtime/protected-evidence-bundle-score/2026-06-05-rc1/protected-evidence-bundle-score.json \
  --output deploy/runtime/protected-evidence-bundle-drift/2026-06-05-rc2 \
  --score-drop-threshold 5 \
  --strict
```

The drift exporter writes `protected-evidence-bundle-drift.json`,
`drift-report.md`, `comparison.tsv`, `status.tsv`, `env-summary.txt`, and
`summary.md`. Protected CI allows a missing baseline by default for the first
run using `TIJARA_PROTECTED_BUNDLE_DRIFT_ALLOW_MISSING_BASELINE=1`; once a
previous approved run exists, set `TIJARA_PROTECTED_BUNDLE_DRIFT_BASELINE_SCORE`
to the baseline score manifest path and optionally tighten
`TIJARA_PROTECTED_BUNDLE_DRIFT_FAIL_ON_WARNING=1`.

Run the protected preflight locally before a protected workflow if you want to
check the non-secret environment surface without executing release gates:

```bash
TIJARA_PROTECTED_RUN_ID=2026-06-05-rc1 \
TIJARA_TARGET_ENVIRONMENT=staging \
TIJARA_PROTECTED_CERTIFICATION_GROUPS=psp,fbr,hardware \
python3 scripts/export_protected_runner_preflight.py \
  --output deploy/runtime/protected-runner-preflight/2026-06-05-rc1 \
  --strict
```

The preflight manifest does not print secret values. It records presence,
placeholder status, and redacted previews for protected release variables,
certification groups, URL/load/E2E toggles, and required PSP/FBR/hardware
evidence fields. Attach that directory to `TIJARA_SIGNOFF_EVIDENCE_PATHS`; the
sign-off package reads `summary.md` and `status.tsv`, so strict preflight
failures appear as release-readiness blockers.

Run deeper authenticated service checks when the protected runner has service
credentials available:

```bash
TIJARA_SERVICE_CHECKS_PROBE=1
TIJARA_SERVICE_CHECKS_REQUIRE_PROBES=1
TIJARA_SERVICE_CHECKS_TIMEOUT=8
```

The service checker validates Odoo `/web/login`, Odoo
`/web/session/authenticate` with `ODOO_DATABASE`, `TIJARA_E2E_LOGIN`, and
`TIJARA_E2E_PASSWORD`, hardware bridge `/health`, signed hardware bridge
`/v1/test` using `TIJARA_BRIDGE_SHARED_SECRET`, Prometheus `/-/ready`,
Alertmanager `/-/ready`, and Grafana `/api/health`. It records redacted URLs,
status codes, auth header names, auth env names, and credential presence only.

Aggregate protected PSP/FBR provider readiness before the release-candidate
gate:

```bash
TIJARA_PROVIDER_READINESS_PSP_PROVIDERS=jazzcash,easypaisa,stripe
TIJARA_PROVIDER_READINESS_REQUIRE_PSP=0
TIJARA_PROVIDER_READINESS_REQUIRE_FBR=0
TIJARA_PROVIDER_READINESS_REQUIRE_LIVE_FBR=0
TIJARA_PROVIDER_READINESS_FAIL_ON_WARNING=0
```

Set `TIJARA_PROVIDER_READINESS_REQUIRE_PSP=1` when JazzCash, Easypaisa, and
Stripe native signature/webhook readiness plus approved provider certification
must block release readiness. Set `TIJARA_PROVIDER_READINESS_REQUIRE_FBR=1` and
`TIJARA_PROVIDER_READINESS_REQUIRE_LIVE_FBR=1` when a certified FBR provider
endpoint, credential reference, sandbox/live approval reference, POS ID, branch
code, and payload hash must be release blockers. The exporter writes
`protected-provider-readiness.json`, nested `psp-readiness/` and
`fbr-readiness/` evidence folders, `status.tsv`, `env-summary.txt`, and
`summary.md` without printing provider secrets.

Capture protected payment lifecycle evidence before the release-candidate gate:

```bash
TIJARA_PAYMENT_LIFECYCLE_PROVIDERS=jazzcash,easypaisa,stripe
TIJARA_PAYMENT_LIFECYCLE_REQUIRE_NATIVE_SIGNATURES=0
TIJARA_PAYMENT_LIFECYCLE_REQUIRE_PROVIDER_CERTIFICATION=0
TIJARA_PAYMENT_LIFECYCLE_FAIL_ON_WARNING=0
```

The exporter verifies the committed signed webhook route, provider signature
contracts, webhook normalization, settlement import/reconciliation, refund and
chargeback cases, finance accounting actions, PSP readiness, and settlement
fixture smoke coverage for payment, refund, chargeback, and settlement events.
Set `TIJARA_PAYMENT_LIFECYCLE_REQUIRE_NATIVE_SIGNATURES=1` and
`TIJARA_PAYMENT_LIFECYCLE_REQUIRE_PROVIDER_CERTIFICATION=1` when PSP sandbox
credentials and approved provider references must block release readiness. The
evidence writes `protected-payment-lifecycle-evidence.json`, nested
`psp-readiness/` and `psp-fixture-smoke/` folders, `status.tsv`,
`env-summary.txt`, and `summary.md` without writing secret values.

Enable optional URL probes when the protected runner should prove basic network
reachability before expensive evidence collection:

```bash
TIJARA_PREFLIGHT_PROBE_URLS=1
TIJARA_PREFLIGHT_REQUIRE_URLS=0
TIJARA_PREFLIGHT_PROBE_TIMEOUT=5
```

The probes use redacted URLs and no credentials. Default endpoints are
`ODOO_BASE_URL` or `TIJARA_BASE_URL` plus `/web/login`,
`TIJARA_HARDWARE_BRIDGE_URL` plus `/health`,
`TIJARA_PROMETHEUS_URL` plus `/-/ready`,
`TIJARA_ALERTMANAGER_URL` plus `/-/ready`, and `TIJARA_GRAFANA_URL` plus
`/api/health`. In strict preflight mode, configured but unreachable URLs become
blockers. Missing URL probe targets are warnings unless
`TIJARA_PREFLIGHT_REQUIRE_URLS=1`.

For protected endpoints that require a header, keep header names and value-env
names in GitHub Environment variables and the actual values in GitHub
Environment secrets:

```bash
TIJARA_PREFLIGHT_AUTH_PROBES=1
TIJARA_PREFLIGHT_REQUIRE_AUTH=1
TIJARA_PREFLIGHT_BRIDGE_AUTH_HEADER=X-Tijara-Bridge-Secret
TIJARA_PREFLIGHT_BRIDGE_AUTH_VALUE_ENV=TIJARA_BRIDGE_SHARED_SECRET
TIJARA_PREFLIGHT_GRAFANA_AUTH_HEADER=Authorization
TIJARA_PREFLIGHT_GRAFANA_AUTH_VALUE_ENV=TIJARA_PREFLIGHT_GRAFANA_AUTH_VALUE
```

The exporter records only whether the auth value was present and which env var
name supplied it. Header values such as `TIJARA_BRIDGE_SHARED_SECRET` and
`TIJARA_PREFLIGHT_GRAFANA_AUTH_VALUE` remain redacted.

Protected Browser E2E handoff is controlled with:

```bash
TIJARA_PROTECTED_E2E_SEED=0
TIJARA_PROTECTED_E2E_PROFILE=1
TIJARA_PROTECTED_E2E_RUN_BROWSER=1
TIJARA_PROTECTED_E2E_EXECUTION_EVIDENCE=1
TIJARA_PROTECTED_E2E_STRICT=1
```

The protected handoff calls the existing `seed-e2e`, `staging-e2e-profile`,
`e2e-staging`, and `e2e-execution-evidence` targets as requested. When Odoo
credentials, seeded POS data, Playwright browsers, or the staging URL are
missing, it still writes `summary.md`, `status.tsv`, and `env-summary.txt` under
`deploy/runtime/protected-e2e/<run-id>/`; strict failures then flow into the
release sign-off package as Browser E2E blockers.

Protected offline POS replay evidence is controlled with:

```bash
TIJARA_OFFLINE_REPLAY_REQUIRE_E2E=0
TIJARA_OFFLINE_REPLAY_REQUIRE_PLAYWRIGHT_PASS=0
TIJARA_OFFLINE_REPLAY_REQUIRE_DUPLICATE_PROOF=0
TIJARA_OFFLINE_REPLAY_FAIL_ON_WARNING=0
```

The exporter checks the committed offline capture/replay/status routes, queue
model, cashier localStorage replay frontend, conflict review/audit/pilot
dashboard views, Odoo transaction tests, and enterprise Browser E2E spec. When
staging credentials and seeded POS IDs are present, set
`TIJARA_OFFLINE_REPLAY_REQUIRE_E2E=1`,
`TIJARA_OFFLINE_REPLAY_REQUIRE_PLAYWRIGHT_PASS=1`, and
`TIJARA_OFFLINE_REPLAY_REQUIRE_DUPLICATE_PROOF=1` so missing or failed offline
replay browser evidence blocks release readiness. The evidence writes
`protected-offline-replay-evidence.json`, `status.tsv`, `env-summary.txt`, and
`summary.md` without printing Odoo passwords or secrets.

Protected offline queue snapshots can be collected automatically before the
pilot evidence gate:

```bash
TIJARA_OFFLINE_QUEUE_SNAPSHOT_PROBE=1
TIJARA_OFFLINE_QUEUE_SNAPSHOT_REQUIRE_PROBE=1
TIJARA_OFFLINE_QUEUE_SNAPSHOT_LIMIT=250
TIJARA_OFFLINE_QUEUE_SNAPSHOT_TIMEOUT=8
TIJARA_OFFLINE_QUEUE_SNAPSHOT_POS_CONFIG_ID=replace-with-pos-config-id
```

`make protected-offline-queue-snapshot` authenticates to Odoo with
`ODOO_BASE_URL`, `ODOO_DATABASE`, `ODOO_USERNAME`, and `ODOO_PASSWORD`, calls
`/tijara/offline-pos/status`, then reads safe `tijara.offline.pos.queue` fields
through `search_read`. It writes `offline-queue-snapshot.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/protected-offline-pilot/<run-id>/queue-snapshot/`. The protected
workflow passes that JSON into `protected-offline-pilot-evidence` so replay,
duplicate, blocked/watch, conflict/failed, unresolved, and queue-age metrics do
not need to be typed manually when staging is reachable.

Protected offline POS pilot evidence is controlled with:

```bash
TIJARA_OFFLINE_PILOT_OUTAGE_REF=outage:store-pilot-001
TIJARA_OFFLINE_PILOT_RECOVERY_OWNER=OpsLead
TIJARA_OFFLINE_PILOT_STORE_REF=Karachi-Branch
TIJARA_OFFLINE_PILOT_REGISTER_REF=POS-01
TIJARA_OFFLINE_PILOT_SOURCE_DEVICE_ID=karachi-pos-01
TIJARA_OFFLINE_PILOT_REPLAY_SUCCESS_COUNT=1
TIJARA_OFFLINE_PILOT_DUPLICATE_COUNT=1
TIJARA_OFFLINE_PILOT_BLOCKED_COUNT=0
TIJARA_OFFLINE_PILOT_WATCH_COUNT=0
TIJARA_OFFLINE_PILOT_CONFLICT_COUNT=0
TIJARA_OFFLINE_PILOT_FAILED_COUNT=0
TIJARA_OFFLINE_PILOT_MAX_QUEUE_AGE_MINUTES=5
TIJARA_OFFLINE_PILOT_REQUIRE_REPLAY_PASS=1
TIJARA_OFFLINE_PILOT_REQUIRE_RUNTIME_PROOF=1
TIJARA_OFFLINE_PILOT_REQUIRE_DUPLICATE_PROOF=1
TIJARA_OFFLINE_PILOT_FAIL_ON_WARNING=1
```

`make protected-offline-pilot-evidence` writes
`offline-pos-pilot-evidence.json`, `status.tsv`, `env-summary.txt`, and
`summary.md` under `deploy/runtime/protected-offline-pilot/<run-id>/`. Use
`TIJARA_OFFLINE_PILOT_QUEUE_STATUS_JSON` when the pilot exports a structured
queue snapshot; otherwise set the count variables directly from the staging
pilot dashboard. Strict protected runs require the outage reference, recovery
owner, store, register, source device, replay success proof, zero blocked/watch
queues, zero conflicts/failures, and queue age within
`TIJARA_OFFLINE_PILOT_MAX_QUEUE_AGE_THRESHOLD_MINUTES`. The sign-off package
adds `offline_pilot_reviews` to `release-readiness.json` and an Offline POS
Pilot Evidence section to `evidence-summary.md`.

After the protected readiness check, the workflow runs
`scripts/export_protected_artifact_summary.py`. The generated `summary.md`
points release owners at failed/warning rows across preflight, release,
provider readiness, payment lifecycle, Browser E2E, offline replay, offline
pilot, operations, certification, retention, secret-manager, production
operations readiness, and sign-off artifacts. Use it as the first file to open inside
`tijara-protected-release-evidence-<environment>-<run>`. In GitHub Actions, the
summary also records the workflow run URL, commit/ref metadata, and uploaded
artifact reference when those values are available.

Export release retention and secret-manager evidence before production
approval:

```bash
python3 scripts/export_release_retention_evidence.py \
  --run-id 2026-06-05-rc1 \
  --target-environment production \
  --artifact-store-reference s3://tijara-release-evidence/2026-06-05-rc1 \
  --artifact-retention-policy-ref policy:release-evidence-365d \
  --certification-retention-policy-ref policy:certification-evidence-365d \
  --secret-manager-provider vault \
  --secret-manager-reference vault:tijara/production \
  --secret-rotation-policy-ref policy:quarterly-secret-rotation \
  --ci-artifact-retention-days 30 \
  --release-evidence-retention-days 365 \
  --certification-evidence-retention-days 365 \
  --log-retention-days 30 \
  --backup-retention-days 30 \
  --evidence-path deploy/runtime/operations-release-bundle/2026-06-05-rc1 \
  --strict
```

The exporter fingerprints attached evidence files, records retention-day
baselines, confirms only secret-manager references are present, and writes
`release-retention-evidence.json`, `status.tsv`, `env-summary.txt`, and
`summary.md` under `deploy/runtime/release-retention-evidence/<run-id>/`.
Include that directory in `TIJARA_SIGNOFF_EVIDENCE_PATHS`; the sign-off package
extracts it under `release_retention_reviews`.

Export runtime secret-manager and committed configuration evidence before
production approval:

```bash
python3 scripts/export_secret_manager_evidence.py \
  --run-id 2026-06-05-rc1 \
  --target-environment production \
  --secret-manager-provider vault \
  --secret-manager-reference vault:tijara/production \
  --secret-rotation-policy-ref policy:quarterly-secret-rotation \
  --secret-access-review-ref review:2026-q2-production-secrets \
  --strict
```

The exporter checks that `.env.example` contains no secret-like assignments,
`secrets/.env.secrets.example` contains placeholder secret keys, critical
Compose secrets use required `:?` guards, the Odoo startup script refuses
missing or placeholder production secrets, and no non-example secret files are
tracked by git under `secrets/`. Ignored local runtime secret files such as
`secrets/.env.secrets` are recorded as path-only warnings without exposing
values. It writes `secret-manager-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/secret-manager-evidence/<run-id>/`. Include that directory in
`TIJARA_SIGNOFF_EVIDENCE_PATHS` and require the `security` evidence group for
production release sign-off; the sign-off package extracts it under
`secret_manager_reviews`.

Export runtime secret delivery evidence after selecting the production secret
provider. The exporter supports `env:`, `file:`, and `command:` probes and
never writes resolved secret values to evidence:

```bash
python3 scripts/export_secret_runtime_evidence.py \
  --run-id 2026-06-05-prod \
  --target-environment production \
  --secret-manager-provider vault \
  --secret-manager-reference vault:tijara/production \
  --secret-access-review-ref review:2026-q2-production-secrets \
  --probe ODOO_DB_PASSWORD=env:ODOO_DB_PASSWORD \
  --probe POSTGRES_PASSWORD=file:/run/secrets/postgres-password \
  --probe 'ODOO_MASTER_PASSWORD=command:vault kv get -field=value secret/tijara/odoo-master-password' \
  --expected-secret ODOO_DB_PASSWORD \
  --expected-secret POSTGRES_PASSWORD \
  --expected-secret ODOO_MASTER_PASSWORD \
  --minimum-probes 3 \
  --strict
```

The exporter writes `secret-runtime-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/secret-runtime-evidence/<run-id>/`. Attach that directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS` and require the `security` evidence group for
production sign-off; the sign-off package extracts it under
`secret_runtime_reviews`.

Export deployment environment protection evidence before staging or production
approval:

```bash
python3 scripts/export_deployment_environment_evidence.py \
  --run-id 2026-06-05-prod \
  --target-environment production \
  --platform github-actions \
  --environment-name production \
  --branch-policy-ref github:protected-branches/main \
  --approver "Release Owner" \
  --approver "DevOps Owner" \
  --approver-group-ref github:tijara-release-approvers \
  --minimum-approvers 2 \
  --promotion-runbook-ref docs:DEPLOY.md#production-deployment-gate \
  --rollback-runbook-ref docs:DEPLOY.md#production-rollback \
  --deployment-gate-ref deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json \
  --incident-runbook-ref docs:DEPLOY.md#monitoring-alerting-and-incident-readiness \
  --backup-policy-ref deploy/postgres/README.md \
  --monitoring-ref deploy/monitoring/README.md \
  --change-ticket-ref change:TIJARA-PROD-001 \
  --freeze-window-ref calendar:prod-freeze-window \
  --strict
```

The exporter writes `deployment-environment-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/deployment-environments/<run-id>/`. Include that directory in
`TIJARA_SIGNOFF_EVIDENCE_PATHS` and require the `ops` evidence group for
production release sign-off; the sign-off package extracts it under
`deployment_environment_reviews`.

Optional tools:

- Run `make tenant-ops-evidence` after generating tenant artifacts to export
  machine-checkable tenant DNS, ingress, admin, backup, monitoring, and smoke
  readiness evidence.
- Run `make tenant-smoke` after tenant URLs are reachable to execute
  tenant-aware endpoint smoke checks from tenant operations artifacts.
- Run `k6 run scripts/load_smoke.k6.js` for a simple HTTP load smoke.
- Run `make load-evidence` after k6 to export structured load evidence for
  release sign-off.
- Run `make load-enterprise-surfaces` for the reusable k6 profile covering the
  POS shell, public display data, customer display data, kiosk data, and
  optional kiosk checkout.
- Run `make load-profile-matrix-evidence` to export the approved load profile
  matrix for release sign-off.
- Run `make operations-release-bundle` to collect matrix, enterprise load,
  smoke, optional tenant smoke, monitoring, incident runbook, and release
  retention evidence under one Operations evidence directory. Set
  `TIJARA_OPS_BUNDLE_TENANT_SMOKE_ARTIFACTS` or
  `TIJARA_TENANT_SMOKE_ARTIFACTS` to include tenant smoke automatically.
- In the protected GitHub workflow, the operations bundle is now paired with
  standalone monitoring, incident runbook, runtime secret, deployment
  environment, and tenant operations evidence so
  `export_production_ops_readiness.py --strict --fail-on-warning` can block on
  a complete evidence set instead of a single coarse bundle verdict.
- Run `make ops-tool-evidence` or `scripts/export_ops_tool_evidence.py` after
  capturing restore, security, dependency, container, npm audit, optional
  pip-audit, Trivy JSON, k6, and monitoring-drill outputs to produce structured
  tool evidence for protected-runner sign-off.
- Run `make production-ops-readiness` or
  `scripts/export_production_ops_readiness.py --strict --fail-on-warning`
  after the supporting evidence is attached to create one release-blocking
  operations verdict for monitoring, restore drills, load, secrets, deployment
  protection, tenant operations, and security scan references.
- Run `make github-step-summary` or `scripts/export_github_step_summary.py`
  after production ops, post-run verification, artifact summary,
  protected-run-decision, protected evidence retention, and sign-off evidence
  exist to render the same Markdown summary that the protected GitHub workflow
  appends to `GITHUB_STEP_SUMMARY`. When artifact upload outputs are
  available, pass or export `TIJARA_UPLOADED_ARTIFACT_ID`,
  `TIJARA_UPLOADED_ARTIFACT_URL`, `TIJARA_UPLOADED_ARTIFACT_DIGEST`, and
  `TIJARA_GITHUB_ARTIFACT_RETENTION_DAYS` to include the post-upload metadata.
- Run `make release-retention-evidence` to export artifact-store,
  secret-manager, retention policy, and evidence-fingerprint readiness without
  running the full operations bundle.
- Run `make secret-manager-evidence` to validate runtime secret-manager
  references, config-template separation, required secret placeholders, and
  committed-secret-file hygiene.
- Run `make secret-runtime-evidence` to validate runtime secret delivery probes
  after the selected provider is available.
- Run `make deployment-environment-evidence` to validate required approvers,
  branch/deployment policy, promotion and rollback runbooks, deployment gate,
  monitoring, backup, change-ticket, and release-window references.
- Run `make container-scan` when Trivy is installed.
- Run `make dependency-scan` for npm audit and pip-audit where available.
- Run `make test-odoo` for committed Odoo transaction/HTTP tests.
- Run `make staging-e2e-profile` after seeding and loading staging secrets to
  validate the live POS/refund/print/offline browser profile before Playwright.
  The profile writes `staging-e2e-profile.json`, `status.tsv`,
  `env-summary.txt`, and `summary.md` under
  `deploy/runtime/e2e-profile/<run-id>/`; the sign-off package extracts
  readiness under `e2e_profile_reviews`.
- Run `make e2e-staging` after installing Playwright and setting staging
  environment variables for authenticated POS, refund, print, and offline
  replay flows. The guarded runner writes `e2e-readiness.json`, `status.tsv`,
  `env-summary.txt`, Playwright logs, and `summary.md` under
  `deploy/runtime/e2e-evidence/<run-id>/`; the sign-off package extracts
  readiness under `e2e_readiness_reviews`.
- Run `make ops-staging` for grouped staging evidence across monitoring, load,
  dependency, restore, and container checks. The load check automatically
  exports nested structured load evidence when k6 runs.
- Run `make release-candidate` for the local release gate. Use
  `TIJARA_RELEASE_CHECKS=full make release-candidate` after staging E2E,
  operations evidence, Docker, and Odoo test prerequisites are ready.

Structured load evidence can be captured from a k6 summary export:

```bash
mkdir -p deploy/runtime/load-evidence/2026-06-05-rc1
k6 run --summary-export deploy/runtime/load-evidence/2026-06-05-rc1/k6-summary.json scripts/load_smoke.k6.js
python3 scripts/export_load_evidence.py \
  --run-id 2026-06-05-rc1 \
  --summary-json deploy/runtime/load-evidence/2026-06-05-rc1/k6-summary.json \
  --base-url https://staging.example.com \
  --vus 5 \
  --duration 30s
```

Load evidence is written under `deploy/runtime/load-evidence/<run-id>/` and
can be included in `TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence.

Run the reusable enterprise surface profile when seeded display/kiosk/customer
display slugs are available:

```bash
TIJARA_LOAD_RUN_ID=2026-06-05-rc1-surfaces \
TIJARA_LOAD_VUS=5 \
TIJARA_LOAD_DURATION=2m \
TIJARA_BASE_URL=https://staging.example.com \
TIJARA_DISPLAY_SLUG=tijara-e2e-menu \
TIJARA_KIOSK_SLUG=tijara-e2e-kiosk \
TIJARA_CUSTOMER_DISPLAY_SLUG=tijara-e2e-customer \
make load-enterprise-surfaces
```

The enterprise profile is read-heavy by default. Set
`TIJARA_RUN_KIOSK_CHECKOUT_LOAD=1` only on a seeded staging tenant where kiosk
checkout order creation is expected and safe.

Export the load profile matrix before staging or production sign-off:

```bash
TIJARA_LOAD_MATRIX_RUN_ID=2026-06-05-rc1 \
TIJARA_LOAD_MATRIX_APPROVED_BY="Release Owner" \
TIJARA_LOAD_MATRIX_APPROVAL_REF=LOAD-MATRIX-UAT-001 \
make load-profile-matrix-evidence
```

The matrix evidence is written under
`deploy/runtime/load-profile-matrix/<run-id>/` and can be attached to
`TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence. For production release,
run with `TIJARA_LOAD_MATRIX_NON_STRICT=0` or `--strict` so missing approval
metadata blocks sign-off.

Release candidate evidence is written to
`deploy/runtime/release-evidence/<run-id>/`. The default `local` scope runs
scaffold validation, JavaScript checks, security audit, and script syntax
checks. The `full` scope also requires a clean git worktree, Odoo transaction
tests, guarded staging browser E2E, and guarded staging operations evidence.

For a full staging release drill, use the orchestration wrapper after exporting
the staging E2E, Odoo, monitoring, restore, and provider/device variables:

```bash
TIJARA_STAGING_RELEASE_RUN_ID=2026-06-05-rc1 \
TIJARA_STAGING_RELEASE_SEED_E2E=1 \
TIJARA_STAGING_RELEASE_PROFILE_E2E=1 \
TIJARA_STAGING_RELEASE_EXECUTION_EVIDENCE=1 \
TIJARA_E2E_PROFILE_STRICT=1 \
TIJARA_E2E_PROFILE_REQUIRE_SEED=1 \
TIJARA_STAGING_RELEASE_CHECKS=full \
TIJARA_E2E_SCOPE=full \
TIJARA_E2E_PASSWORD=<staging-test-password> \
TIJARA_E2E_OWNER="QA Owner" \
TIJARA_E2E_RUNBOOK_REF=docs:DEPLOY.md#display-routes \
TIJARA_E2E_CHANGE_REF=change:TIJARA-STAGE-E2E-001 \
TIJARA_OPS_CHECKS=full \
TIJARA_OPS_STRICT=1 \
TIJARA_STAGING_RELEASE_ENV_PROTECTION_STRICT=1 \
TIJARA_STAGING_RELEASE_TENANT_OPS_ARTIFACTS=deploy/runtime/tenants/tijara_customer_001 \
TIJARA_STAGING_RELEASE_TENANT_OPS_STRICT=1 \
TIJARA_TENANT_ROLLOUT_ARTIFACTS=deploy/runtime/tenants/tijara_customer_001 \
TIJARA_OPS_BUNDLE_TENANT_ROLLOUT_PLATFORM=kubernetes \
TIJARA_OPS_BUNDLE_TENANT_ROLLOUT_REQUIRE_ALL_ARTIFACTS=1 \
TIJARA_DEPLOYMENT_ENVIRONMENT_NAME=staging \
TIJARA_BRANCH_POLICY_REF=github:protected-branches/main \
TIJARA_DEPLOYMENT_APPROVERS="Release Owner,DevOps Owner" \
TIJARA_APPROVER_GROUP_REF=github:tijara-release-approvers \
TIJARA_MINIMUM_APPROVERS=2 \
TIJARA_PROMOTION_RUNBOOK_REF=docs:DEPLOY.md#production-deployment-gate \
TIJARA_ROLLBACK_RUNBOOK_REF=docs:DEPLOY.md#production-rollback \
TIJARA_DEPLOYMENT_GATE_REF=deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json \
TIJARA_ENV_INCIDENT_RUNBOOK_REF=docs:DEPLOY.md#monitoring-alerting-and-incident-readiness \
TIJARA_ENV_BACKUP_POLICY_REF=deploy/postgres/README.md \
TIJARA_ENV_MONITORING_REF=deploy/monitoring/README.md \
TIJARA_CHANGE_TICKET_REF=change:TIJARA-STAGE-001 \
TIJARA_FREEZE_WINDOW_REF=calendar:stage-release-window \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
TIJARA_STAGING_RELEASE_FAIL_ON_WARNING=1 \
make staging-release-signoff
```

The wrapper keeps a single run ID across:

- `deploy/runtime/release-evidence/<run-id>/`
- `deploy/runtime/e2e-seed/<run-id>/` when
  `TIJARA_STAGING_RELEASE_SEED_E2E=1` or
  `TIJARA_STAGING_RELEASE_INCLUDE_E2E_SEED=1`.
- `deploy/runtime/e2e-profile/<run-id>/` when
  `TIJARA_STAGING_RELEASE_PROFILE_E2E=1` or
  `TIJARA_STAGING_RELEASE_INCLUDE_E2E_PROFILE=1`.
- `deploy/runtime/e2e-evidence/<run-id>/`
- `deploy/runtime/e2e-execution/<run-id>/` when
  `TIJARA_STAGING_RELEASE_EXECUTION_EVIDENCE=1`.
- `deploy/runtime/ops-evidence/<run-id>/`
- `deploy/runtime/release-retention-evidence/<run-id>/` when exported
  separately or nested under an operations release bundle.
- `deploy/runtime/deployment-environments/<run-id>/`
- `deploy/runtime/tenant-ops-evidence/<run-id>/` when
  `TIJARA_STAGING_RELEASE_TENANT_OPS_ARTIFACTS` is set.
- `deploy/runtime/signoff-packages/<run-id>/`
- `deploy/runtime/staging-release/<run-id>/`

It continues through package generation and readiness checking even if an
earlier step fails, so release owners get a complete blocked/ready decision
instead of only a partial log.
When `TIJARA_STAGING_RELEASE_SEED_E2E=1`, the wrapper runs `make seed-e2e`,
sources the generated non-secret `e2e-seed.env`, maps `TIJARA_E2E_PASSWORD` to
`ODOO_PASSWORD` if the latter is not already set, and appends seed evidence to
the sign-off package.
When `TIJARA_STAGING_RELEASE_PROFILE_E2E=1`, the wrapper runs
`make staging-e2e-profile` after seed env sourcing and appends profile evidence
to the sign-off package.
When `TIJARA_STAGING_RELEASE_EXECUTION_EVIDENCE=1`, the wrapper runs
`make e2e-execution-evidence` after sign-off readiness checking so the combiner
can reference the final `release-readiness.json`.
Tenant operations evidence is opt-in for the wrapper. Set
`TIJARA_STAGING_RELEASE_TENANT_OPS_ARTIFACTS` to one or more comma-separated
tenant artifact directories, or set `TIJARA_STAGING_RELEASE_INCLUDE_TENANT_OPS=1`
with `TIJARA_TENANT_OPS_ARTIFACTS`. When enabled, the wrapper appends tenant
operations evidence to `TIJARA_SIGNOFF_EVIDENCE_PATHS`, and release readiness
includes `tenant_ops_reviews`.

## External Certification Evidence Intake

Collect external certification evidence before the final sign-off package. The
collector does not copy provider or device evidence into the repo; it validates
required metadata, rejects secret-like metadata keys, records SHA-256
fingerprints, validates optional provider artifact manifests, enforces approval
references and validity dates when requested, and writes release-ingestible
evidence under
`deploy/runtime/certification-evidence/<run-id>/<category>/`.

Artifact manifests should be JSON files with an `artifacts` list. Each artifact
can include `path`, `sha256`, and `required`; relative paths resolve beside the
manifest file so provider/export bundles can stay portable:

```json
{
  "metadata": {
    "provider": "JazzCash",
    "batch": "JZ-UAT-001"
  },
  "artifacts": [
    {
      "path": "jazzcash-settlement.csv",
      "sha256": "<64-character-sha256>",
      "required": true
    }
  ]
}
```

Copy the starter templates in `deploy/config/certification-manifests/` into a
secure evidence bundle outside the repo, replace the placeholder file names and
hashes, and point the protected runner variables such as
`TIJARA_CERT_PSP_ARTIFACT_MANIFEST`,
`TIJARA_CERT_FBR_ARTIFACT_MANIFEST`, and
`TIJARA_CERT_HARDWARE_ARTIFACT_MANIFEST` at those real manifest files.

PSP evidence example:

```bash
python3 scripts/collect_certification_evidence.py \
  --run-id 2026-06-05-rc1 \
  --category psp \
  --provider JazzCash \
  --reference JAZZ-UAT-001 \
  --owner Finance \
  --evidence-file /secure/evidence/jazzcash-settlement.csv \
  --artifact-manifest /secure/evidence/jazzcash-certification-manifest.json \
  --expected-sha256 /secure/evidence/jazzcash-settlement.csv=<64-character-sha256> \
  --minimum-evidence-files 1 \
  --approved-by "Finance Lead" \
  --approval-reference FIN-PSP-2026-001 \
  --valid-until 2027-06-05 \
  --require-artifact-manifest \
  --require-approval \
  --require-validity \
  --metadata settlement_batch=JZ-001 \
  --strict
```

FBR evidence example:

```bash
python3 scripts/collect_certification_evidence.py \
  --run-id 2026-06-05-rc1 \
  --category fbr \
  --provider CertifiedFBRProvider \
  --reference FBR-SANDBOX-001 \
  --owner Tax \
  --evidence-file /secure/evidence/fbr-sandbox-response.json \
  --artifact-manifest /secure/evidence/fbr-certification-manifest.json \
  --approved-by "Tax Lead" \
  --approval-reference FBR-SIGNOFF-2026-001 \
  --valid-until 2027-06-05 \
  --require-artifact-manifest \
  --require-approval \
  --require-validity \
  --metadata fbr_pos_id=123 \
  --metadata branch_code=KHI-01 \
  --strict
```

Hardware evidence example:

```bash
python3 scripts/collect_certification_evidence.py \
  --run-id 2026-06-05-rc1 \
  --category hardware \
  --owner Operations \
  --store "Karachi Branch" \
  --device-model "Epson TM-T88VI" \
  --device-serial "TEST-SERIAL-001" \
  --evidence-file /secure/evidence/epson-tm-t88vi-certification/ \
  --artifact-manifest /secure/evidence/epson-tm-t88vi-certification/manifest.json \
  --approved-by "Store Operations Lead" \
  --approval-reference HW-KHI-EPSON-2026-001 \
  --valid-until 2027-06-05 \
  --require-artifact-manifest \
  --require-approval \
  --require-validity \
  --strict
```

Include the generated directories in the release sign-off package:

```bash
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/2026-06-05-rc1,deploy/runtime/e2e-seed/2026-06-05-rc1,deploy/runtime/e2e-profile/2026-06-05-rc1,deploy/runtime/e2e-evidence/2026-06-05-rc1,deploy/runtime/ops-evidence/2026-06-05-rc1,deploy/runtime/certification-evidence/2026-06-05-rc1/psp,deploy/runtime/certification-evidence/2026-06-05-rc1/fbr,deploy/runtime/certification-evidence/2026-06-05-rc1/hardware \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops,psp,fbr,hardware \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
make signoff-pack
```

Also attach the root certification execution folder when reviewing operations
evidence, because it records which categories were passed, failed, or skipped:

```bash
python3 scripts/export_certification_result_matrix.py \
  --run-id 2026-06-05-rc1 \
  --target-environment staging \
  --certification-root deploy/runtime/certification-evidence/2026-06-05-rc1 \
  --provider-readiness deploy/runtime/protected-provider-readiness/2026-06-05-rc1/protected-provider-readiness.json \
  --output deploy/runtime/certification-evidence/2026-06-05-rc1/result-matrix \
  --strict
```

```bash
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/certification-evidence/2026-06-05-rc1,deploy/runtime/certification-evidence/2026-06-05-rc1/psp,deploy/runtime/certification-evidence/2026-06-05-rc1/fbr,deploy/runtime/certification-evidence/2026-06-05-rc1/hardware \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=psp,fbr,hardware \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
make signoff-pack
```

Generate the release sign-off package after collecting release, browser, and
operations evidence:

```bash
TIJARA_SIGNOFF_RUN_ID=2026-06-05-rc1 \
TIJARA_SIGNOFF_ENVIRONMENT=staging \
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/2026-06-05-rc1,deploy/runtime/e2e-seed/2026-06-05-rc1,deploy/runtime/e2e-profile/2026-06-05-rc1,deploy/runtime/e2e-evidence/2026-06-05-rc1,deploy/runtime/operations-release-bundle/2026-06-05-rc1 \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops \
make signoff-pack
```

The package is written to `deploy/runtime/signoff-packages/<run-id>/` unless
`TIJARA_SIGNOFF_OUTPUT` is set. It includes:

- `release-go-no-go.md` for product, operations, rollback, and exception review.
- `psp-certification.md` for JazzCash, Easypaisa, Stripe, bank, or other PSP
  signature, settlement, refund, chargeback, and reconciliation sign-off.
- `fbr-certification.md` for certified-provider sandbox/live evidence.
- `hardware-certification.md` for printer, drawer, scanner, scale, customer
  display, and label printer physical certification.
- `finance-tax-signoff.md` for accounting setup, refund, chargeback, write-off,
  and tax policy approval.
- `security-review-signoff.md` for scan results, RBAC, logs, rate limits,
  backup/restore, and exception handling.
- `evidence-summary.md` with extracted release, browser E2E, operations,
  status-table, PSP/FBR readiness, FBR fixture smoke, certification evidence,
  certification result matrix, monitoring, incident runbook, production
  operations readiness, release retention, secret manager, secret runtime,
  tenant operations, tenant smoke, tenant rollout, deployment environment, load
  evidence, load profile matrix evidence, and non-secret environment summaries
  for approvers.
- `release-readiness.json` with `ready`, `warning`, or `blocked` decision,
  CI status, blockers, warnings, evidence group counts, summary reviews, and
  check rows for dashboards or release automation. When PSP readiness evidence
  is attached, provider-level readiness reviews are included under
  `psp_readiness_reviews`; when FBR readiness evidence is attached,
  certified-provider readiness is included under `fbr_readiness_reviews`; when
  FBR fixture smoke evidence is attached, response fixture coverage is included
  under `fbr_fixture_reviews`; when external PSP, FBR, or hardware
  certification evidence is attached, manifest, hash, approval, validity, and
  device/provider reviews are included under `certification_evidence_reviews`;
  when the protected certification result matrix is attached, category-level
  pass/fail/warning/skipped reviews are included under
  `certification_result_matrix_reviews`;
  when browser E2E seed, profile, execution, or readiness evidence is attached,
  reviews are included under
  `e2e_seed_reviews`, `e2e_profile_reviews`, `e2e_execution_reviews`, and
  `e2e_readiness_reviews`; when monitoring evidence is attached,
  observability reviews are included under
  `monitoring_reviews`; when incident runbook evidence is attached, ownership
  and response references are included under `incident_runbook_reviews`; when
  load evidence is attached, threshold and profile reviews are included under
  `load_reviews`; when load profile matrix evidence is attached, approved
  tenant-size and vertical profile reviews are included under
  `load_matrix_reviews`; when operations release bundle evidence is attached,
  bundle step status and evidence references are included under
  `operations_bundle_reviews`; when production operations readiness evidence is
  attached, component status, backup/restore, scan, and required-reference
  reviews are included under `production_ops_readiness_reviews`; when
  operations tool evidence is attached, restore, security, dependency,
  container, Trivy, npm audit, pip-audit, and k6 component reviews are included
  under `ops_tool_reviews`; when release
  retention evidence is attached,
  artifact-store, secret-manager, retention, and evidence fingerprint reviews
  are included under `release_retention_reviews`; when secret-manager evidence
  is attached, runtime secret references, template separation, Compose guards,
  startup guards, and committed-secret hygiene are included under
  `secret_manager_reviews`; when secret runtime evidence is attached, runtime
  secret probe source and resolution reviews are included under
  `secret_runtime_reviews`; when tenant operations evidence is attached,
  per-tenant DNS, ingress, admin, backup, monitoring, smoke, and artifact
  reviews are included under `tenant_ops_reviews`; when tenant smoke evidence
  is attached, per-tenant endpoint execution, route counts, checklist coverage,
  and database-isolation header usage are included under
  `tenant_smoke_reviews`; when tenant rollout evidence is attached, per-tenant
  DNS, ingress, TLS, Nginx, monitoring, backup action status is included under
  `tenant_rollout_reviews`; when deployment environment evidence is attached,
  approver, branch-policy, promotion, rollback,
  deployment-gate, monitoring, backup, change-ticket, and freeze-window reviews
  are included under `deployment_environment_reviews`.
- `evidence-manifest.json` with SHA-256 fingerprints for attached evidence
  files.

Use `TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS` to require evidence groups by
alias, such as `release,e2e,ops,security,hardware,fbr,psp`. By default, missing
groups are written as warnings in the package. Set
`TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1` for production release drills where
missing required groups should make `make signoff-pack` exit non-zero after the
package is written.
CI/CD can read `release-readiness.json`; treat `decision=blocked` or
`ci_status=fail` as a stop condition, and require a named release-owner
exception for `decision=warning`.

Check readiness from CI or a release terminal:

```bash
make check-release-readiness READINESS=deploy/runtime/signoff-packages/2026-06-05-rc1/release-readiness.json
TIJARA_RELEASE_FAIL_ON_WARNING=1 python3 scripts/check_release_readiness.py deploy/runtime/signoff-packages/2026-06-05-rc1/release-readiness.json
```

The checker exits `0` for ready, `1` for blocked, `1` for warning when
`TIJARA_RELEASE_FAIL_ON_WARNING=1`, and `2` for missing or unreadable readiness
JSON.

Before a production cutover, generate a deployment gate package from the
staging sign-off readiness JSON:

```bash
TIJARA_DEPLOYMENT_RUN_ID=2026-06-05-prod \
TIJARA_DEPLOYMENT_TARGET=production \
TIJARA_DEPLOYMENT_BACKUP_REF=deploy/runtime/backups/2026-06-05-pre-prod.dump \
TIJARA_DEPLOYMENT_ROLLBACK_REF=ghcr.io/example/tijara-suite:previous \
TIJARA_DEPLOYMENT_MONITORING_REF=grafana-dashboard-prod-pos \
TIJARA_DEPLOYMENT_TENANT_ROLLOUT_REF=deploy/runtime/tenant-rollouts/2026-06-05-prod/tenant-rollout-evidence.json \
TIJARA_DEPLOYMENT_TENANT_SMOKE_REF=deploy/runtime/tenant-smoke/2026-06-05-prod/tenant-smoke-evidence.json \
TIJARA_DEPLOYMENT_APPROVER="Release Owner" \
TIJARA_DEPLOYMENT_FAIL_ON_WARNING=1 \
make production-deployment-gate READINESS=deploy/runtime/signoff-packages/2026-06-05-rc1/release-readiness.json
```

For `TIJARA_DEPLOYMENT_TARGET=production`, deployment environment protection
evidence in `release-readiness.json`, backup reference, rollback reference,
tenant rollout reviews in `release-readiness.json`, tenant rollout evidence
reference, tenant smoke reviews in `release-readiness.json`, tenant smoke
evidence reference, monitoring reference, sign-off package, and approver are
required by default. Set `TIJARA_DEPLOYMENT_REQUIRE_ENVIRONMENT_PROTECTION=0`,
`TIJARA_DEPLOYMENT_REQUIRE_TENANT_ROLLOUT=0`, or
`TIJARA_DEPLOYMENT_REQUIRE_TENANT_SMOKE=0` only for an explicitly approved
non-production drill. Set
`TIJARA_DEPLOYMENT_REQUIRE_TENANT_ROLLOUT_EXECUTION=1` when production cutover
must prove executed rollout actions rather than dry-run action plans. The gate
writes `deployment-decision.json`, `status.tsv`, `summary.md`,
`pre-cutover-checklist.md`, and `rollback-checklist.md` under
`deploy/runtime/deployment-gates/<run-id>/`. It exits non-zero when deployment
is blocked.

Rollback commands are dry-run by default and consume the deployment gate
decision:

```bash
make production-rollback DEPLOYMENT_GATE=deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json
TIJARA_ROLLBACK_PROVIDER=docker-compose TIJARA_ROLLBACK_SERVICE=odoo TIJARA_ROLLBACK_COMPOSE_IMAGE_ENV=ODOO_IMAGE make production-rollback DEPLOYMENT_GATE=deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json
TIJARA_ROLLBACK_PROVIDER=kubernetes TIJARA_ROLLBACK_NAMESPACE=tijara-prod TIJARA_ROLLBACK_DEPLOYMENT=tijara-odoo TIJARA_ROLLBACK_CONTAINER=odoo make production-rollback DEPLOYMENT_GATE=deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json
```

To execute provider commands instead of writing dry-run logs, set both
`TIJARA_ROLLBACK_EXECUTE=1` and `CONFIRM_PRODUCTION_ROLLBACK=YES`. Rollback
evidence is written under `deploy/runtime/rollback-runs/<run-id>/` with
`rollback-decision.json`, `status.tsv`, `env-summary.txt`, `summary.md`, and
per-step logs. The default `manifest` provider records a manual/provider
specific review command; `docker-compose` and `kubernetes` generate concrete
open-source runtime commands. The Docker Compose provider injects the rollback
reference through `TIJARA_ROLLBACK_COMPOSE_IMAGE_ENV`, defaulting to
`ODOO_IMAGE`, which matches `docker-compose.yml`.

After deployment or rollback, capture production smoke evidence:

```bash
TIJARA_SMOKE_RUN_ID=2026-06-05-prod \
TIJARA_SMOKE_BASE_URL=https://pos.example.com \
python3 scripts/run_production_smoke.py \
  --deployment-decision deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json \
  --url login=https://pos.example.com/web/login \
  --url display=https://pos.example.com/tijara/display/main/data
```

Smoke evidence is written under `deploy/runtime/production-smoke/<run-id>/`
with `smoke-decision.json`, `status.tsv`, `summary.md`, and
`env-summary.txt`. HTTP 2xx/3xx responses pass; 4xx/5xx responses and
unreachable endpoints block by default. Set `TIJARA_SMOKE_NON_STRICT=1` only
for exploratory drills where endpoint failures should be warnings.

Run tenant-aware smoke execution after tenant operations artifacts are
generated and DNS/ingress are available:

```bash
python3 scripts/run_tenant_smoke.py \
  --run-id 2026-06-05-prod \
  --target-environment production \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --route display=/tijara/display/main/data \
  --route queue=/tijara/queue/main/data \
  --minimum-tenants 1 \
  --minimum-routes-per-tenant 2 \
  --strict
```

The runner reads each tenant `ops-manifest.json`, probes the tenant web root and
login routes, optionally probes the manifest Blackbox URL and extra
operator-provided routes, sends an `X-Odoo-dbfilter` tenant-isolation header,
records smoke-checklist coverage, and writes `tenant-smoke-evidence.json`,
`status.tsv`, `summary.md`, and `env-summary.txt` under
`deploy/runtime/tenant-smoke/<run-id>/`. Attach that directory to
`TIJARA_SIGNOFF_EVIDENCE_PATHS`; the sign-off package extracts it under
`tenant_smoke_reviews`.

Capture monitoring evidence after deployment or rollback:

```bash
python3 scripts/export_monitoring_evidence.py \
  --run-id 2026-06-05-prod \
  --smoke-decision deploy/runtime/production-smoke/2026-06-05-prod/smoke-decision.json \
  --tenant-rollout-evidence deploy/runtime/tenant-rollouts/2026-06-05-prod/tenant-rollout-evidence.json \
  --tenant-smoke-evidence deploy/runtime/tenant-smoke/2026-06-05-prod/tenant-smoke-evidence.json \
  --deployment-decision deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json \
  --rollback-decision deploy/runtime/rollback-runs/2026-06-05-prod/rollback-decision.json \
  --prometheus-url https://prometheus.example.com \
  --alertmanager-url https://alertmanager.example.com \
  --grafana-url https://grafana.example.com
```

Monitoring evidence is written under
`deploy/runtime/monitoring-evidence/<run-id>/` and can be included in
`TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence. When tenant rollout
evidence is attached, the exporter records rollout decision status, rollback
action count, and whether `rollback-plan.md` is present next to the rollout
evidence.

Capture load-test evidence after the release candidate load smoke:

```bash
mkdir -p deploy/runtime/load-evidence/2026-06-05-prod
k6 run --summary-export deploy/runtime/load-evidence/2026-06-05-prod/k6-summary.json scripts/load_smoke.k6.js
python3 scripts/export_load_evidence.py \
  --strict \
  --run-id 2026-06-05-prod \
  --summary-json deploy/runtime/load-evidence/2026-06-05-prod/k6-summary.json \
  --base-url https://pos.example.com \
  --vus 10 \
  --duration 2m
```

Load evidence is written under `deploy/runtime/load-evidence/<run-id>/` and can
be included in `TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence.

## Assumption-Mode External Certification Evidence

When real shop hardware, certified FBR credentials, or PSP UAT/live references
are not available during local or public-repo validation, generate explicit
dummy evidence instead of leaving the release record blank:

```bash
TIJARA_ASSUMED_CERT_RUN_ID=local-assumed-2026-06-09 \
make assumed-certification-evidence
```

The exporter writes `assumed-certification-evidence.json`, `status.tsv`,
`env-summary.txt`, command logs, PSP readiness, PSP fixture smoke, FBR
readiness, FBR fixture smoke, and hardware dry-run smoke evidence under
`deploy/runtime/assumed-certification/<run-id>/`. Treat this as
`pass_with_warnings`: it proves adapters, fixture parsers, and bridge driver
output shape, but it is not production certification. Production sign-off still
requires physical printer/scanner/drawer/scale/display evidence, certified FBR
provider credentials, and JazzCash/Easypaisa/Stripe UAT or live references.

Capture incident runbook evidence before production cutover:

```bash
python3 scripts/export_incident_runbook_evidence.py \
  --run-id 2026-06-05-prod \
  --release-owner "Release Owner" \
  --devops-owner "DevOps Owner" \
  --support-owner "Support Owner" \
  --business-owner "Business Owner" \
  --oncall-contact oncall@example.com \
  --alert-route alertmanager:tijara-prod \
  --runbook-url https://runbooks.example.com/tijara/incident \
  --backup-reference backup-2026-06-05 \
  --restore-drill-reference restore-2026-06-05 \
  --rollback-reference odoo:previous \
  --monitoring-reference deploy/runtime/monitoring-evidence/2026-06-05-prod/monitoring-evidence.json
```

Incident runbook evidence is written under
`deploy/runtime/incident-runbooks/<run-id>/` and can be included in
`TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence.

## Rollback Baseline

For every production release, keep:

- The previous Docker image tags.
- The previous addon code bundle.
- A pre-upgrade database backup.
- A written migration note with installed/updated modules.
- A smoke checklist result for login, POS load, product search, checkout,
  receipt profile rendering, refund/exchange, inventory adjustment, and reports.
