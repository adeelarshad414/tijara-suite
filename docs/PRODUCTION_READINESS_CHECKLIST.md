# Tijara Suite Production Readiness Checklist

Version: 2026-06-09

Use this checklist before approving a tenant or platform production launch.
Local demo may pass with dummy/assumed external integrations. Production must
replace dummy values with real certified evidence.

## A. Product And Workflow

- [ ] POS checkout works for B2C.
- [ ] POS checkout works for B2B with separate prices.
- [ ] Bill discount works by amount and percentage.
- [ ] Refund/exchange works from invoice barcode or FBR QR.
- [ ] English, Urdu, and bilingual receipts are reviewed.
- [ ] Inventory import/export is tested.
- [ ] Low-stock alerts are reviewed.
- [ ] Expiry alerts are reviewed.
- [ ] Warehouse/store/shelf/rack/bin placement is configured.
- [ ] Customer management and loyalty are tested.
- [ ] Back-office expenses are tested.
- [ ] Salary/payroll evidence workflow is tested.
- [ ] Restaurant dine-in, takeaway, pickup, and delivery are tested.
- [ ] Kiosk ordering is tested.
- [ ] Queue display is tested.
- [ ] Customer display is tested.
- [ ] Promotion/menu/deal display screens are tested.
- [ ] Ecommerce storefront, checkout, order history, saved addresses, and
      returns are tested.

## B. Pakistan Localization

- [ ] Company country is Pakistan.
- [ ] Currency is PKR.
- [ ] GST 18% is configured where enabled.
- [ ] GST can be disabled by policy where required.
- [ ] Cafe/restaurant card tax policy is configured.
- [ ] Cafe/restaurant cash tax policy is configured.
- [ ] Cafe service charge policy is configured.
- [ ] Delivery charge policy is configured.
- [ ] NTN/STRN/POS ID/branch code are configured.
- [ ] Urdu labels and invoice text are reviewed.

## C. SaaS Controls

- [ ] Tenant plan is active.
- [ ] Feature flags are correct for POS, inventory, analytics, ecommerce, B2B,
      queue display, customer display, promotion display, and vertical modules.
- [ ] Runtime SaaS enforcement is enabled for staging/production.
- [ ] Disabled features are blocked in UI and backend.
- [ ] Subscription invoice/payment status is reviewed.
- [ ] Dunning/suspension workflow is tested or explicitly waived.

## D. External Integrations

Dummy allowed for local demo:

- [ ] Courier adapter uses dummy or assumed provider payload.
- [ ] FBR queue uses dry-run response.
- [ ] PSP uses fixture signatures and settlement samples.
- [ ] Hardware bridge uses dry-run devices.

Required for production:

- [ ] Courier provider contract/API credentials are attached.
- [ ] Courier live tracking, cancellation, label, manifest, webhook, and COD
      reconciliation are tested.
- [ ] Courier certification evidence is collected with
      `scripts/collect_certification_evidence.py --category courier`.
- [ ] FBR certified provider credentials are attached.
- [ ] FBR sandbox/UAT approval is attached.
- [ ] FBR live compliance test is approved.
- [ ] JazzCash certification is attached where used.
- [ ] Easypaisa certification is attached where used.
- [ ] Stripe/live card certification is attached where used.
- [ ] Payment signatures, refunds, settlements, and chargebacks are tested.
- [ ] Physical printer certification is attached.
- [ ] Scanner certification is attached.
- [ ] Cash drawer certification is attached.
- [ ] Scale certification is attached.
- [ ] Customer display certification is attached.

## E. Monitoring And Operations

- [ ] `TIJARA_METRICS_TOKEN` is non-placeholder in production.
- [ ] Odoo dbfilter or tenant host routing selects the production database for
      `/tijara/monitoring/metrics`.
- [ ] `/tijara/monitoring/metrics` returns Prometheus text format.
- [ ] Prometheus scrapes Odoo business metrics.
- [ ] Pushgateway demo metrics are disabled for production or isolated from
      production dashboards; `make prometheus-demo-metrics` is used only for
      demos/staging evidence.
- [ ] Delivery alert rules are loaded.
- [ ] Blackbox probes cover Odoo and hardware bridge.
- [ ] Grafana dashboards are reachable.
- [ ] Grafana `Tijara Suite` folder contains owner/DevOps, delivery, finance,
      and hardware/integration-risk dashboards.
- [ ] `make monitoring-dashboards-check` passes.
- [ ] `make grafana-dashboard-evidence` captured dashboard API and screenshot
      evidence, or `node scripts/capture-grafana-evidence.js --metadata-only`
      passed for a non-live CI validation.
- [ ] Alertmanager routes alerts to the support/on-call channel.
- [ ] Logs are collected for Odoo, PostgreSQL, Nginx/ingress, hardware bridge,
      FBR, PSP, and background jobs.
- [ ] Backup job runs successfully.
- [ ] Restore drill passes.
- [ ] Production DNS/TLS/backup wrapper plan is generated with
      `make production-infra` and provider-approved apply/rollback templates.
- [ ] Cloudflare or Route53 DNS template pack is selected and reviewed.
- [ ] cert-manager/Kubernetes TLS template pack is selected and reviewed.
- [ ] PostgreSQL backup/restore runner pack is selected and dry-run evidence
      passes before `CONFIRM_PROVIDER_ACTION=YES` is allowed.
- [ ] `make infra-provider-readiness` passes with real provider credentials,
      required CLIs, and real deployment/rollback approval evidence.
- [ ] `make production-ops-readiness` includes production-infra and
      infra-provider-readiness components as passed.
- [ ] `make signoff-pack` extracts `production_infra_reviews` and
      `infra_provider_readiness_reviews` into `release-readiness.json`.
- [ ] Incident runbook is reviewed.
- [ ] Rollback process is tested.

## F. Security

- [ ] `docs/CONFIGURATION_AND_SECRETS.md` has been reviewed for this release.
- [ ] Every runtime non-secret variable is defined in `.env.example` or the
      deployment platform variable set.
- [ ] Every runtime secret variable is defined in
      `secrets/.env.secrets.example` and supplied from the production secret
      manager.
- [ ] No ad-hoc `.env.local`, `.env.production`, shell export, service config,
      screenshot, log, or evidence file contains runtime secrets.
- [ ] Placeholder secrets are removed.
- [ ] Secret manager or protected secret store is used.
- [ ] Production startup refuses placeholder secrets.
- [ ] RBAC for admin, cashier, inventory, accounting, ecommerce, analytics, and
      display users is reviewed.
- [ ] Public routes are reviewed.
- [ ] Metrics endpoint requires token.
- [ ] Payment webhook signatures are enforced.
- [ ] Rate limits/reverse-proxy protections are configured.
- [ ] Dependency audit is clean or accepted by owner.
- [ ] Container scan is clean or accepted by owner.
- [ ] Security test evidence is attached.

## G. QA Evidence

- [ ] `make validate` passed.
- [ ] `make js-check` passed.
- [ ] `make test-odoo` passed.
- [ ] `make e2e` passed.
- [ ] `make protected-browser-e2e-matrix` passed.
- [ ] `make load-smoke` passed.
- [ ] `make monitoring-evidence` passed.
- [ ] `make production-ops-readiness` passed.
- [ ] `make signoff-pack` generated release package.
- [ ] Business owner reviewed dashboards and reports.
- [ ] Finance owner approved settlement/refund/chargeback workflow.
- [ ] Tax owner approved FBR workflow.
- [ ] DevOps owner approved deployment and rollback.
- [ ] Security owner approved hardening evidence.

## Go/No-Go

- [ ] No critical blocker remains.
- [ ] All dummy integrations are either replaced with certified live integrations
      or explicitly approved as not in scope for this launch.
- [ ] Production readiness owner signs off.
- [ ] Rollback owner signs off.
- [ ] Customer launch window is approved.
