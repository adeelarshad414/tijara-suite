# Deploy Guide

This guide is the operational entry point for deploying Tijara Suite. Keep it
updated whenever deployment, configuration, secrets, observability, backup, or
release behavior changes.

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
docs/RETAIL_OPERATIONS_DATA.md        Hardware, templates, scanning, CSV notes
docker-compose.yml                    Development and small deployment runtime
Makefile                              Operator shortcuts
```

Do not put passwords, API keys, database passwords, backup keys, FBR credentials,
payment credentials, or JWT/session material in committed configuration files.

## Environment Files

Use two centered files per environment:

- `.env`: non-secret runtime configuration, copied from `.env.example`.
- `secrets/.env.secrets`: secret runtime configuration, copied from
  `secrets/.env.secrets.example`.

For production, plain env files should be replaced by a secret manager such as
Vault, SOPS, Kubernetes Secrets, Docker secrets, Doppler, 1Password Secrets
Automation, AWS Secrets Manager, Azure Key Vault, or Google Secret Manager.

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

## Compose Commands

The Makefile automatically includes `.env` and `secrets/.env.secrets` when they
exist.

```bash
make validate
make js-check
make security-audit
make config
make up
make ps
make logs
make install-suite
make seed-e2e DB=tijara_dev
make test-odoo
make e2e
make bridge-up
make bridge-logs
make backup-db
make restore-drill BACKUP=deploy/runtime/backups/file.dump
make provision-tenant TENANT_DB=tijara_customer_001 TENANT_NAME="Customer 001"
make provision-tenant-ops TENANT_DB=tijara_customer_001 TENANT_DOMAIN=customer.example.com ADMIN_EMAIL=admin@example.com
make hardware-cert-smoke
make monitoring-up
make load-smoke
make release-candidate
make psp-readiness-evidence
make psp-fixture-smoke
make fbr-readiness-evidence
make monitoring-evidence
make incident-runbook-evidence
make signoff-pack
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
docker compose --env-file .env --env-file secrets/.env.secrets run --rm odoo bash /usr/local/bin/tijara-start-odoo -d tijara_dev -i tijara_base,tijara_retail_core,tijara_pos_pk,tijara_saas_control,tijara_pos_experience,tijara_vertical_pharmacy,tijara_vertical_restaurant,tijara_vertical_garments,tijara_vertical_electronics,tijara_vertical_cloth,tijara_vertical_superstore,tijara_vertical_grocery,tijara_vertical_bakery --without-demo --stop-after-init
```

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
- `GRAFANA_ADMIN_PASSWORD` for the monitoring profile

The startup script refuses to start production if placeholder or development
secret values are still present.

For single-database local development, `POSTGRES_PASSWORD` and
`ODOO_DB_PASSWORD` should match the active password for the `POSTGRES_USER` role.
For production, keep both values in the secret manager and rotate them through a
planned database credential rotation, not by editing committed templates.

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
- Receipt printer and customer display hardware paths where available.

See `docs/FRONTEND_DEVICE_QA.md` for the acceptance standard.

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

This writes a tenant operations manifest, Nginx location snippet, and Prometheus
Blackbox target under `deploy/runtime/tenants/<tenant_db>/`. The matching Odoo
provisioning request can also generate an operations manifest from SaaS Admin.
Production DNS changes, certificate issuance, admin-user creation, and smoke
execution still need provider-specific automation.

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
summary under `deploy/runtime/ops-evidence/<run-id>/`. Set
`TIJARA_OPS_STRICT=1` when skipped checks, missing tools, or missing backup paths
should fail the release drill.

## Display Routes

Public display routes are available for store screens:

```text
/tijara/display/<slug>
/tijara/display/<slug>/data
/tijara/kiosk/<slug>
/tijara/kiosk/<slug>/data
/tijara/kiosk/<slug>/checkout
```

Use HTTPS and reverse-proxy rate limiting in production. The baseline Nginx file
already rate-limits login, database, JSON-RPC, display, and kiosk paths.

Seed staging browser data:

```bash
TIJARA_E2E_PASSWORD=<staging-test-password> make seed-e2e DB=tijara_dev
export TIJARA_DISPLAY_SLUG=tijara-e2e-menu
export TIJARA_KIOSK_SLUG=tijara-e2e-kiosk
export TIJARA_CUSTOMER_DISPLAY_SLUG=tijara-e2e-customer
export TIJARA_E2E_PRODUCT_ID=<printed-by-seed>
export TIJARA_E2E_PRODUCT_NAME=<printed-by-seed>
export TIJARA_E2E_PAYMENT_METHOD_ID=<printed-by-seed>
export TIJARA_E2E_PAYMENT_METHOD_NAME=<printed-by-seed>
export TIJARA_E2E_REFUND_REASON_ID=<printed-by-seed>
export TIJARA_E2E_POS_ORDER_ID=<printed-by-seed>
export TIJARA_E2E_REFUND_BARCODE=<printed-by-seed>
export TIJARA_REFUND_ACTION_URL=<printed-by-seed>
export TIJARA_REPORT_ORDER_URL=<printed-by-seed>
export TIJARA_OFFLINE_QUEUE_ACTION_URL=<printed-by-seed>
export ODOO_USERNAME=<printed-by-seed>
export ODOO_PASSWORD=<staging-test-password>
export ODOO_DATABASE=tijara_dev
export TIJARA_RUN_POS_UI_E2E=1
export TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1
ODOO_BASE_URL=http://127.0.0.1:8069 npm run test:e2e
```

For staging sign-off, run the guarded evidence harness instead of a raw
Playwright command:

```bash
TIJARA_E2E_SCOPE=full ODOO_BASE_URL=https://staging.example.com make e2e-staging
```

The harness verifies the required slugs, credentials, POS config/product/payment
IDs, refund barcode, report URL, and offline review URL before running. Evidence
is written to `deploy/runtime/e2e-evidence/<run-id>/` with an environment
summary, Playwright output, JSON results, and a Markdown summary. Use
`TIJARA_E2E_SCOPE=public` for display/kiosk/customer-display only or
`TIJARA_E2E_SCOPE=authenticated` for POS/refund/offline-report routes.
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
TIJARA_SIGNOFF_RUN_ID=ci-local \
TIJARA_SIGNOFF_ENVIRONMENT=ci \
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/ci-local \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
make signoff-pack
make check-release-readiness READINESS=deploy/runtime/signoff-packages/ci-local/release-readiness.json
```

The workflow uploads `deploy/runtime/release-evidence/ci-local` and
`deploy/runtime/signoff-packages/ci-local` as the
`tijara-ci-release-evidence` artifact. This is not a substitute for staging
release evidence, but it prevents PRs from merging with a broken local release
gate or malformed readiness package.

Optional tools:

- Run `k6 run scripts/load_smoke.k6.js` for a simple HTTP load smoke.
- Run `make container-scan` when Trivy is installed.
- Run `make dependency-scan` for npm audit and pip-audit where available.
- Run `make test-odoo` for committed Odoo transaction/HTTP tests.
- Run `make e2e` after installing Playwright and setting staging environment
  variables for authenticated flows.
- Run `make ops-staging` for grouped staging evidence across monitoring, load,
  dependency, restore, and container checks.
- Run `make release-candidate` for the local release gate. Use
  `TIJARA_RELEASE_CHECKS=full make release-candidate` after staging E2E,
  operations evidence, Docker, and Odoo test prerequisites are ready.

Release candidate evidence is written to
`deploy/runtime/release-evidence/<run-id>/`. The default `local` scope runs
scaffold validation, JavaScript checks, security audit, and script syntax
checks. The `full` scope also requires a clean git worktree, Odoo transaction
tests, guarded staging browser E2E, and guarded staging operations evidence.

For a full staging release drill, use the orchestration wrapper after exporting
the staging E2E, Odoo, monitoring, restore, and provider/device variables:

```bash
TIJARA_STAGING_RELEASE_RUN_ID=2026-06-05-rc1 \
TIJARA_STAGING_RELEASE_CHECKS=full \
TIJARA_E2E_SCOPE=full \
TIJARA_OPS_CHECKS=full \
TIJARA_OPS_STRICT=1 \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
TIJARA_STAGING_RELEASE_FAIL_ON_WARNING=1 \
make staging-release-signoff
```

The wrapper keeps a single run ID across:

- `deploy/runtime/release-evidence/<run-id>/`
- `deploy/runtime/e2e-evidence/<run-id>/`
- `deploy/runtime/ops-evidence/<run-id>/`
- `deploy/runtime/signoff-packages/<run-id>/`
- `deploy/runtime/staging-release/<run-id>/`

It continues through package generation and readiness checking even if an
earlier step fails, so release owners get a complete blocked/ready decision
instead of only a partial log.

## External Certification Evidence Intake

Collect external certification evidence before the final sign-off package. The
collector does not copy provider or device evidence into the repo; it validates
required metadata, rejects secret-like metadata keys, records SHA-256
fingerprints, and writes release-ingestible evidence under
`deploy/runtime/certification-evidence/<run-id>/<category>/`.

PSP evidence example:

```bash
python3 scripts/collect_certification_evidence.py \
  --run-id 2026-06-05-rc1 \
  --category psp \
  --provider JazzCash \
  --reference JAZZ-UAT-001 \
  --owner Finance \
  --evidence-file /secure/evidence/jazzcash-settlement.csv \
  --metadata settlement_batch=JZ-001
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
  --metadata fbr_pos_id=123 \
  --metadata branch_code=KHI-01
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
  --evidence-file /secure/evidence/epson-tm-t88vi-certification/
```

Include the generated directories in the release sign-off package:

```bash
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/2026-06-05-rc1,deploy/runtime/e2e-evidence/2026-06-05-rc1,deploy/runtime/ops-evidence/2026-06-05-rc1,deploy/runtime/certification-evidence/2026-06-05-rc1/psp,deploy/runtime/certification-evidence/2026-06-05-rc1/fbr,deploy/runtime/certification-evidence/2026-06-05-rc1/hardware \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops,psp,fbr,hardware \
TIJARA_SIGNOFF_STRICT_REQUIRED_EVIDENCE=1 \
make signoff-pack
```

Generate the release sign-off package after collecting release, browser, and
operations evidence:

```bash
TIJARA_SIGNOFF_RUN_ID=2026-06-05-rc1 \
TIJARA_SIGNOFF_ENVIRONMENT=staging \
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/2026-06-05-rc1,deploy/runtime/e2e-evidence/2026-06-05-rc1,deploy/runtime/ops-evidence/2026-06-05-rc1 \
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
  status-table, PSP/FBR readiness, monitoring evidence, and non-secret
  environment summaries for approvers.
- `release-readiness.json` with `ready`, `warning`, or `blocked` decision,
  CI status, blockers, warnings, evidence group counts, summary reviews, and
  check rows for dashboards or release automation. When PSP readiness evidence
  is attached, provider-level readiness reviews are included under
  `psp_readiness_reviews`; when FBR readiness evidence is attached,
  certified-provider readiness is included under `fbr_readiness_reviews`; when
  monitoring evidence is attached, observability reviews are included under
  `monitoring_reviews`; when incident runbook evidence is attached, ownership
  and response references are included under `incident_runbook_reviews`.
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
TIJARA_DEPLOYMENT_APPROVER="Release Owner" \
TIJARA_DEPLOYMENT_FAIL_ON_WARNING=1 \
make production-deployment-gate READINESS=deploy/runtime/signoff-packages/2026-06-05-rc1/release-readiness.json
```

For `TIJARA_DEPLOYMENT_TARGET=production`, backup reference, rollback reference,
monitoring reference, sign-off package, and approver are required by default.
The gate writes `deployment-decision.json`, `status.tsv`, `summary.md`,
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

Capture monitoring evidence after deployment or rollback:

```bash
python3 scripts/export_monitoring_evidence.py \
  --run-id 2026-06-05-prod \
  --smoke-decision deploy/runtime/production-smoke/2026-06-05-prod/smoke-decision.json \
  --deployment-decision deploy/runtime/deployment-gates/2026-06-05-prod/deployment-decision.json \
  --rollback-decision deploy/runtime/rollback-runs/2026-06-05-prod/rollback-decision.json \
  --prometheus-url https://prometheus.example.com \
  --alertmanager-url https://alertmanager.example.com \
  --grafana-url https://grafana.example.com
```

Monitoring evidence is written under
`deploy/runtime/monitoring-evidence/<run-id>/` and can be included in
`TIJARA_SIGNOFF_EVIDENCE_PATHS` as Operations evidence.

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
