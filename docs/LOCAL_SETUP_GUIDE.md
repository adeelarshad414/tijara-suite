# Local Setup Guide

For the complete operator path, also read `docs/SETUP_STEP_BY_STEP.md`.
For central configuration and secret handling, read
`docs/CONFIGURATION_AND_SECRETS.md`. For role workflows, read
`docs/HOW_TO_USE_GUIDELINES.md`. For production go-live checks, read
`docs/PRODUCTION_READINESS_CHECKLIST.md`.

## Prerequisites

Install these tools before running the suite locally:

| Tool | Purpose |
|---|---|
| Docker Desktop or Docker Engine with Compose v2 | Runs Odoo, PostgreSQL, hardware bridge, and monitoring profiles |
| Node.js and npm | Runs Playwright and capture scripts |
| Python 3 | Runs release evidence and operational scripts |
| Make | Provides operator shortcuts |
| Optional ffmpeg | Assembles recorded demo clips into `docs/PRODUCT_DEMO.mp4` |
| Optional k6 and Trivy | Load and container scans for production-readiness evidence |

## Environment Setup

The repo keeps non-secret and secret configuration in separate centered files:

```bash
cp .env.example .env
mkdir -p secrets
cp secrets/.env.secrets.example secrets/.env.secrets
```

For local development, update placeholder values in `secrets/.env.secrets`.
Never commit copied secret files, and do not create ad-hoc runtime env files
outside this two-file pattern.

## Start The App

The generated start script validates dependencies, creates missing env files,
starts Compose services, waits for Odoo, records runtime process metadata, and
prints service URLs:

```bash
bash scripts/dev-start.sh
```

Start optional profiles:

```bash
TIJARA_DEV_START_HARDWARE=1 bash scripts/dev-start.sh
TIJARA_DEV_START_MONITORING=1 bash scripts/dev-start.sh
```

Python service manager:

```bash
python3 scripts/tijara_services.py start --all-profiles
python3 scripts/tijara_services.py status
python3 scripts/tijara_services.py logs odoo --tail 200
```

Native Bash operator wrapper:

```bash
bash scripts/tijara-start.sh --all --install-suite --seed-demo
```

Install the suite and seed demo POS data during startup:

```bash
TIJARA_DEV_INSTALL_SUITE=1 TIJARA_DEV_SEED_POS_DEMO=1 bash scripts/dev-start.sh
```

Open:

```text
http://localhost:8069
```

## Stop Or Restart

```bash
bash scripts/dev-stop.sh
bash scripts/dev-restart.sh
```

Python equivalents:

```bash
python3 scripts/tijara_services.py stop --force-kill-ports
python3 scripts/tijara_services.py restart --all-profiles
```

Native Bash stop wrapper:

```bash
bash scripts/tijara-stop.sh --force-kill-ports
```

If a previous tool left local ports occupied, force free known Tijara ports:

```bash
TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh
```

## Seed Demo Data

```bash
make seed-pos-demo
```

The optional `tijara_demo_pos` module seeds POS config, demo products, B2B/B2C
customers, public display screens, kiosk profile, queue ticket, and promotion
records. Demo login users from `docs/TEST_CREDENTIALS.csv` should be created or
mapped in the local or staging database before authenticated browser E2E runs.

## Validate

```bash
make validate
make js-check
make security-audit
make test-odoo
make e2e
```

Run screenshot and video scaffolds against a live instance:

```bash
node scripts/capture-screenshots.js
node scripts/record-demo.js
bash scripts/assemble-video.sh
```

## Windows PowerShell

```powershell
powershell -File scripts/dev-start.ps1
powershell -File scripts/dev-stop.ps1
powershell -File scripts/dev-start.ps1 -Hardware -Monitoring
powershell -File scripts/tijara-start.ps1 -AllProfiles -InstallSuite -SeedDemo
powershell -File scripts/tijara-stop.ps1 -ForceKillPorts
powershell -File scripts/tijara-deploy.ps1 -Environment staging -GenerateSecrets -Monitoring -InstallSuite
pwsh -File scripts/tijara-production-infra.ps1 --tenant-artifact deploy/runtime/tenants/tijara_customer_001
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Compose asks for passwords | Copy and edit `secrets/.env.secrets.example` into `secrets/.env.secrets` |
| Odoo cannot connect to DB | Keep `POSTGRES_PASSWORD` and `ODOO_DB_PASSWORD` aligned for single-db local dev |
| Port 8069 is busy | Run `TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh` |
| Demo screens are empty | Install `tijara_demo_pos` with `make seed-pos-demo` |
| Playwright cannot open browser | Run `npx playwright install chromium` |
| Screenshot script cannot log in | Create or map the users listed in `docs/TEST_CREDENTIALS.csv` |
| Hardware bridge does not respond | Start it with `TIJARA_DEV_START_HARDWARE=1 bash scripts/dev-start.sh` |
| Grafana login fails | Set `GRAFANA_ADMIN_PASSWORD` in `secrets/.env.secrets` |
| Grafana panels show no demo data | Run `make prometheus-demo-metrics` after `make monitoring-up` and wait one scrape interval |
| Prometheus business scrape fails | Confirm `TIJARA_METRICS_TOKEN` matches the token in `deploy/monitoring/prometheus.yml` |
| Odoo modules do not appear | Run `make install-suite` against the target DB |
| Production secret warning appears | Replace all placeholder secret values before staging or production |
