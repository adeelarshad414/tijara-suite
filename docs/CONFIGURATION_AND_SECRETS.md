# Configuration And Secrets Guide

Version: 2026-06-09

Tijara Suite uses one central non-secret configuration file and one central
secret file for every local, staging, and production-like runtime.

## Source Of Truth

| Purpose | Committed template | Local/staging runtime file | Production runtime source |
|---|---|---|---|
| Non-secret environment variables | `.env.example` | `.env` | CI/CD or platform variables using the same names |
| Secret environment variables | `secrets/.env.secrets.example` | `secrets/.env.secrets` | Vault, Doppler, SOPS, Kubernetes Secrets, Docker secrets, GitHub Environment Secrets, or cloud secret manager |

The Makefile and developer scripts load `.env` first and
`secrets/.env.secrets` second. Secret values therefore override any accidental
duplicate from a local non-secret file, but duplicates should not be added.

## Rules

- Put ports, image names, feature toggles, dry-run modes, URLs, db hosts, and
  public tenant settings in `.env.example`.
- Put passwords, API keys, tokens, webhook secrets, salts, client credentials,
  encryption keys, session secrets, FBR credentials, PSP credentials, hardware
  bridge shared secrets, and metrics tokens in `secrets/.env.secrets.example`.
- Do not create repo-level `.env.local`, `.env.production`, random shell export
  files, or service-specific secret files for runtime settings.
- Do not put secrets in `docker-compose.yml`, `deploy/config/*.template`,
  `deploy/monitoring/*.yml`, `deploy/nginx/*.conf`, docs, screenshots, logs, or
  generated evidence.
- Keep real production values outside git. Production should inject the same
  variable names from the selected secret manager or deployment platform.
- Dummy values are allowed for local demos only. Production startup and release
  gates must reject placeholder secrets.

## Template Consumers

These files may read or reference variables, but they are not secret stores:

- `docker-compose.yml`
- `Makefile`
- `scripts/dev-start.sh`
- `scripts/tijara_host.py`
- `scripts/tijara_services.py`
- `scripts/tijara-start.sh`
- `scripts/tijara-stop.sh`
- `scripts/tijara-deploy.sh`
- `scripts/tijara-production-infra.sh`
- `scripts/tijara-start.ps1`
- `scripts/tijara-stop.ps1`
- `scripts/tijara-deploy.ps1`
- `scripts/tijara-production-infra.ps1`
- `scripts/seed_prometheus_demo_metrics.py`
- `scripts/run_production_infra_automation.py`
- `scripts/capture-grafana-evidence.js`
- `deploy/bin/start-odoo.sh`
- `deploy/config/odoo.conf.template`
- `deploy/nginx/tijara.conf`
- `deploy/monitoring/*.yml`
- `hardware-bridge/config/devices.example.json`
- `deploy/config/protected-runner-bootstrap.env.example`
- `deploy/config/github-protected-vars.example`
- `secrets/github-protected-secrets.example`

Protected-runner and GitHub example files document CI/CD setup contracts only.
They do not replace `.env` and `secrets/.env.secrets` for application runtime.
The secret-manager evidence check fails git-tracked non-example secret files
under `secrets/` and records ignored local runtime secret files without reading
or printing their values.

## Adding A New Variable

Use this checklist whenever code, deployment, tests, or docs need a new
environment variable:

1. Decide whether the value is secret.
2. Add non-secrets only to `.env.example`.
3. Add secrets only to `secrets/.env.secrets.example` with a placeholder value.
4. Wire the variable through `docker-compose.yml`, `Makefile`, scripts, Odoo
   config, hardware bridge, or monitoring only where the runtime actually needs
   it.
5. Document the variable in `DEPLOY.md` and this guide when operators must set
   it.
6. Update `docs/SPEC_MAP.json` when the variable belongs to the public runtime
   contract.
7. Add a validation, evidence, or startup guard for production-only secrets.
8. Update `README.md` and `PROGRESS.md` for the iteration.

## Secret Classes

| Secret class | Example variables | Owner |
|---|---|---|
| Database | `POSTGRES_PASSWORD`, `ODOO_DB_PASSWORD`, `ODOO_MASTER_PASSWORD` | DevOps |
| Application security | `ODOO_SESSION_SECRET`, `BACKUP_ENCRYPTION_KEY` | DevOps/security |
| Monitoring | `TIJARA_METRICS_TOKEN`, Grafana password | DevOps/SRE |
| Hardware bridge | `TIJARA_BRIDGE_SHARED_SECRET` | Store ops/DevOps |
| Payment providers | JazzCash, Easypaisa, Stripe, generic PSP webhook secrets | Finance/DevOps |
| FBR | `FBR_CLIENT_ID`, `FBR_CLIENT_SECRET` | Tax/finance/DevOps |
| Courier webhooks | Provider webhook shared secrets | Ecommerce ops/DevOps |

## New Operations Variables

| Area | Non-secret examples | Secret handling |
|---|---|---|
| Demo metrics | `TIJARA_PUSHGATEWAY_URL`, `TIJARA_DEMO_METRICS_FILE`, `TIJARA_DEMO_METRICS_JOB`, `TIJARA_DEMO_METRICS_TIMEOUT` | None for public demo metrics; production exporters must use secret-managed scrape tokens. |
| Grafana evidence | `TIJARA_GRAFANA_URL`, `TIJARA_OPS_BUNDLE_GRAFANA_DASHBOARD_TIMEOUT` | `GRAFANA_ADMIN_PASSWORD` stays in `secrets/.env.secrets` or the platform secret manager. |
| Production infra wrappers | `TIJARA_PRODUCTION_INFRA_TENANT_ARTIFACTS`, `TIJARA_PRODUCTION_INFRA_MODE`, `TIJARA_PRODUCTION_INFRA_TEMPLATE`, `TIJARA_PRODUCTION_INFRA_TEMPLATE_FILE`, `TIJARA_DNS_APPLY_COMMAND_TEMPLATE`, `TIJARA_TLS_APPLY_COMMAND_TEMPLATE`, `TIJARA_BACKUP_COMMAND_TEMPLATE`, `CONFIRM_PROVIDER_ACTION`, `CLOUDFLARE_ZONE_ID`, `CLOUDFLARE_RECORD_ID`, `ROUTE53_HOSTED_ZONE_ID`, `ROUTE53_PREVIOUS_TARGET` | `CLOUDFLARE_API_TOKEN`, AWS access keys/session tokens, kubeconfig/service-account credentials, database passwords, and backup encryption keys stay in `secrets/.env.secrets` or the platform secret manager. |
| Infrastructure provider readiness | `TIJARA_INFRA_PROVIDER_READINESS_PROVIDERS`, `TIJARA_INFRA_PROVIDER_READINESS_PRODUCTION_INFRA_EVIDENCE`, `TIJARA_INFRA_PROVIDER_READINESS_DEPLOYMENT_DECISION`, `TIJARA_INFRA_PROVIDER_READINESS_ROLLBACK_DECISION`, `TIJARA_INFRA_PROVIDER_READINESS_REQUIRE_REAL_APPROVALS`, `TIJARA_PROD_OPS_PRODUCTION_INFRA_EVIDENCE`, `TIJARA_PROD_OPS_INFRA_PROVIDER_READINESS_EVIDENCE` | Provider credentials and protected-runner approval evidence stay in the secret manager or protected artifact store. Local assumption mode must stay disabled for production. |

## Rotation And Promotion

- Rotate secrets before moving from local to staging and again before
  production.
- Rotate after staff access changes, suspected exposure, provider credential
  refresh, or incident response.
- Never promote a local `.env` or `secrets/.env.secrets` file into production.
  Promote variable names and reviewed values through the secret manager.
- Keep evidence redacted. Evidence may record whether a variable was present,
  which secret manager reference was used, and who approved it, but never the
  resolved value.

## Local Bootstrap

```bash
cp .env.example .env
mkdir -p secrets
cp secrets/.env.secrets.example secrets/.env.secrets
```

For local demos, placeholders can remain for dry-run FBR, PSP, courier, and
hardware behavior. For shared staging or production, replace every placeholder
with an approved value or secret-manager reference before startup.

The Python hosting helper uses the same files:

```bash
python3 scripts/tijara_host.py init-config --environment staging --generate-secrets
python3 scripts/tijara_host.py deploy --with-monitoring
```

The native wrappers are thin entrypoints over the same centralized files:

```bash
bash scripts/tijara-start.sh --all
bash scripts/tijara-deploy.sh --environment staging --generate-secrets --monitoring
```

```powershell
powershell -File scripts/tijara-start.ps1 -AllProfiles
powershell -File scripts/tijara-deploy.ps1 -Environment staging -GenerateSecrets -Monitoring
```

Generated local secrets from this helper are for controlled demo/staging use.
Production should still inject approved values through the selected secret
manager.
