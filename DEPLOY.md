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
present under `secrets/`. It writes `secret-manager-evidence.json`,
`status.tsv`, `env-summary.txt`, and `summary.md` under
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
- Run `make production-ops-readiness` or
  `scripts/export_production_ops_readiness.py --strict --fail-on-warning`
  after the supporting evidence is attached to create one release-blocking
  operations verdict for monitoring, restore drills, load, secrets, deployment
  protection, tenant operations, and security scan references.
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
TIJARA_SIGNOFF_EVIDENCE_PATHS=deploy/runtime/release-evidence/2026-06-05-rc1,deploy/runtime/e2e-seed/2026-06-05-rc1,deploy/runtime/e2e-profile/2026-06-05-rc1,deploy/runtime/e2e-evidence/2026-06-05-rc1,deploy/runtime/ops-evidence/2026-06-05-rc1,deploy/runtime/certification-evidence/2026-06-05-rc1/psp,deploy/runtime/certification-evidence/2026-06-05-rc1/fbr,deploy/runtime/certification-evidence/2026-06-05-rc1/hardware \
TIJARA_SIGNOFF_REQUIRED_EVIDENCE_GROUPS=release,e2e,ops,psp,fbr,hardware \
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
  status-table, PSP/FBR readiness, FBR fixture smoke, monitoring, incident
  runbook, production operations readiness, release retention, secret manager,
  secret runtime, tenant operations, tenant smoke, tenant rollout, deployment
  environment, load evidence, load profile matrix evidence, and non-secret
  environment summaries for approvers.
- `release-readiness.json` with `ready`, `warning`, or `blocked` decision,
  CI status, blockers, warnings, evidence group counts, summary reviews, and
  check rows for dashboards or release automation. When PSP readiness evidence
  is attached, provider-level readiness reviews are included under
  `psp_readiness_reviews`; when FBR readiness evidence is attached,
  certified-provider readiness is included under `fbr_readiness_reviews`; when
  FBR fixture smoke evidence is attached, response fixture coverage is included
  under `fbr_fixture_reviews`; when browser E2E seed, profile, execution, or
  readiness evidence is attached, reviews are included under
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
  reviews are included under `production_ops_readiness_reviews`; when release
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
