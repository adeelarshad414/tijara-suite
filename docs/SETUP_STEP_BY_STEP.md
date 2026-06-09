# Tijara Suite Step-by-Step Setup

Version: 2026-06-09

Use this guide to set up a local demo, staging pilot, or production-like
environment. Local/demo may use dummy hardware, courier, PSP, and FBR values.
Production must replace every dummy value with certified credentials and
evidence.

## 1. Prepare The Machine

1. Install Docker Desktop or Docker Engine with Compose v2.
2. Install Node.js and npm.
3. Install Python 3.
4. Install Make.
5. Optional for full evidence: install k6, Trivy, ffmpeg, and Chrome/Chromium.

## 2. Clone And Enter The Project

```bash
git clone https://github.com/adeelarshad414/tijara-suite.git
cd tijara-suite
```

For this local Codex workspace, the project directory is:

```text
/Users/adeel.arshad/Documents/Codex/2026-06-04/what-do-you-know-about-odoo/outputs/tijara-suite
```

## 3. Create Central Configuration Files

```bash
cp .env.example .env
mkdir -p secrets
cp secrets/.env.secrets.example secrets/.env.secrets
```

Edit `secrets/.env.secrets` and change at least:

- `POSTGRES_PASSWORD`
- `ODOO_DB_PASSWORD`
- `ODOO_MASTER_PASSWORD`
- `GRAFANA_ADMIN_PASSWORD`
- `TIJARA_METRICS_TOKEN`
- `TIJARA_BRIDGE_SHARED_SECRET`
- Payment/FBR secrets when testing real providers

Local demo can keep `TIJARA_METRICS_TOKEN=dummy-prometheus-token-change-me` if
Prometheus uses the committed local scrape config. Production must replace it.

## 4. Start Local Services

Fast local start:

```bash
bash scripts/dev-start.sh
```

Start with hardware bridge and monitoring:

```bash
TIJARA_DEV_START_HARDWARE=1 TIJARA_DEV_START_MONITORING=1 bash scripts/dev-start.sh
```

Start, install modules, and seed demo data:

```bash
TIJARA_DEV_INSTALL_SUITE=1 TIJARA_DEV_SEED_POS_DEMO=1 bash scripts/dev-start.sh
```

Open:

```text
http://localhost:8069/web/login?db=tijara_dev
```

## 5. Install Or Upgrade Modules

For a fresh local database:

```bash
make install-suite
```

For the Pakistan localization/demo refresh:

```bash
make upgrade-pkr-gst
make verify-pkr-gst
make seed-pos-demo
make seed-demo-users
```

## 6. Validate Core Workflows

```bash
make validate
make js-check
make test-odoo
make e2e
```

For protected/staging-style evidence:

```bash
make seed-e2e DB=tijara_dev
make protected-browser-e2e-matrix
```

## 7. Enable Monitoring

Start monitoring services:

```bash
make monitoring-up
```

Odoo business metrics endpoint:

```text
http://localhost:8069/tijara/monitoring/metrics?db=tijara_dev&token=dummy-prometheus-token-change-me
```

Prometheus local config scrapes the same endpoint through Docker network target
`odoo:8069`. In staging or production, change the token and database parameter
in `deploy/monitoring/prometheus.yml`, or replace that file with an environment
specific secret-managed Prometheus config.

When scraping Odoo business metrics, make sure Odoo selects the target database
before custom module routes are mapped. Local smoke testing used
`ODOO_DB_FILTER=tijara_dev`. Staging/production should use one database per
service or a host-based tenant dbfilter.

## 8. Configure Business Data

1. Log in as Tenant Admin.
2. Configure company name, branch, NTN/STRN, POS ID, and receipt language.
3. Configure GST 18% and PKR.
4. Configure vertical policy: superstore, grocery, bakery, restaurant, cafe,
   garments, cloth, shoes, cosmetics, pharmacy, electronics, or mobile shop.
5. Create warehouses, stores, shelves, racks, bins, and expiry rules.
6. Create B2C and B2B prices for every saleable product.
7. Configure POS registers, payment methods, cash shifts, and printers.
8. Configure invoice/receipt templates for English, Urdu, or bilingual output.
9. Configure ecommerce storefront, pickup/delivery, and customer account portal.
10. Configure SaaS features per tenant plan.

## 9. Use Dummy External Integrations For Demo

Allowed for local demo and community repo testing:

- Courier providers using assumed adapter payloads.
- Hardware bridge dry-run devices.
- FBR dry-run queue responses.
- JazzCash/Easypaisa/Stripe fixture payloads.
- Dummy Prometheus metrics token.

Not acceptable for production go-live:

- Dummy courier tokens or tracking endpoints.
- Dummy FBR provider credentials.
- Dummy PSP signatures or settlement files.
- Dry-run-only printer/scanner/cash drawer/scale/display certification.
- Placeholder Odoo/Postgres/Grafana/metrics secrets.

## 10. Stop Services

```bash
bash scripts/dev-stop.sh
```

If known Tijara ports are stuck:

```bash
TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh
```

## 11. Production Cutover Checklist

Before customer production:

1. Replace all placeholders in secret manager.
2. Run Odoo tests, browser E2E, load smoke, security audit, and backup restore
   drill.
3. Attach physical hardware certification records.
4. Attach PSP, FBR, courier, and finance sign-off evidence.
5. Confirm monitoring, alerting, logging, backups, rollback, and incident
   runbooks.
6. Generate a sign-off package and approve release readiness.
