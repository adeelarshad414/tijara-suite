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
