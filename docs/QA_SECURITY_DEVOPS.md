# QA, Security, and DevOps

## QA Strategy

- Python unit tests for model constraints and workflows.
- Odoo transaction tests for returns, exchanges, stock movement, and cash shifts.
- Browser tests for POS and back office flows.
- Device QA for touch, kiosk, customer display, queue display, promotion display,
  menu display, and cross-browser behavior. See `docs/FRONTEND_DEVICE_QA.md`.
- Hardware integration tests with simulated ESC/POS printers and barcode input.
- CSV import/export tests for products, inventory, contacts, hardware devices,
  invoice templates, storage positions, and promotions.
- Return-scan tests for matched POS order, matched customer invoice, and
  not-found barcode paths.
- Migration tests for every module version.
- Urdu rendering tests for receipts and reports.
- CI baseline now runs scaffold validation, JavaScript syntax checks, security
  audit baseline, and Docker Compose config validation.
- Committed Odoo transaction/HTTP tests now cover SaaS enforcement, tenant
  provisioning state flow, FBR queue dry-run/live guard behavior, analytics
  collection, and display route entitlement/data behavior.
- Playwright scaffolds now cover public display/kiosk routes and provide
  environment-gated authenticated POS checkout, refund/exchange, and report
  route smoke tests for staging.
- Load-smoke foundation is available in `scripts/load_smoke.k6.js`.

## Security Controls

- Database-per-tenant isolation.
- Least-privilege Odoo groups.
- Strong admin password and rotated secrets.
- Separation between non-secret config (`.env`) and secret config
  (`secrets/.env.secrets`), with production secrets supplied by a managed
  secret store where possible.
- Audit logs for refunds, discounts, voids, stock adjustments, and settings.
- Encrypted backups.
- TLS at the reverse proxy.
- Rate limiting and WAF/CDN controls for public SaaS.
- Dependency and container scanning in CI.
- `scripts/container_scan.sh` provides Trivy config/image scanning hooks.
- `scripts/dependency_scan.sh` provides npm audit and pip-audit hooks where the
  tools are available.
- Baseline Nginx rate limiting for login, database, JSON-RPC, display, and
  kiosk routes.
- `scripts/security_audit.sh` checks for committed secret files, generated
  Python cache artifacts, and Odoo Enterprise references in the open-source
  core.

## DevOps Baseline

- Docker Compose for development and small deployments.
- `DEPLOY.md` is the maintained deployment runbook.
- `deploy/config/odoo.conf.template` is the secret-free Odoo config template.
- `deploy/bin/start-odoo.sh` renders runtime config from environment and secret
  variables.
- Kubernetes or Nomad for larger SaaS deployments.
- PostgreSQL managed service where possible.
- Prometheus, Grafana, Loki, and uptime checks.
- Blue/green or rolling deployments after MVP.
- Release channels for staging, pilot, and production.
- `.github/workflows/tijara-ci.yml` provides the first public-repo CI workflow,
  including local release evidence, release retention evidence, strict
  readiness checking, and 30-day CI artifact retention.
- `deploy/postgres/backup.sh` provides a logical backup starting point for pilot
  restore drills.
- `deploy/postgres/restore-drill.sh` creates a temporary database, restores a
  backup, verifies access, and drops the temporary database on exit.
- `deploy/monitoring/` provides Prometheus and Blackbox Exporter availability
  checks for Odoo and the hardware bridge.
- `deploy/logging/README.md` documents log sources, open-source aggregation
  options, and retention expectations.
- `scripts/provision_tenant_db.sh` provides the first database-per-tenant
  provisioning automation path.
- `make validate`, `make js-check`, `make security-audit`, `make backup-db`, and
  `make load-smoke` are the baseline operator shortcuts. `make test-odoo`,
  `make e2e`, `make provision-tenant`, `make hardware-cert-smoke`,
  `make restore-drill`, `make monitoring-up`, `make container-scan`, and
  `make dependency-scan` extend the production-readiness command set.
