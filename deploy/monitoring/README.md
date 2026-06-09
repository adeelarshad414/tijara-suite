# Tijara Monitoring

This profile uses open-source Prometheus, Blackbox Exporter, Alertmanager,
Grafana, and Loki for first-line availability checks, alert routing foundation,
dashboards, and log aggregation foundation.

Start it with:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets --profile monitoring up -d prometheus blackbox alertmanager loki grafana
```

For the Odoo business metrics scrape, run Odoo with a database filter that
selects the target database, for example `ODOO_DB_FILTER=tijara_dev` in local
demo or a host-based tenant dbfilter in staging/production. The `db=` query
parameter documents the target database but does not replace Odoo dbfilter
routing when one service exposes multiple databases.

Current checks:

- Odoo login endpoint availability.
- Odoo business metrics endpoint:
  `/tijara/monitoring/metrics?db=tijara_dev&token=dummy-prometheus-token-change-me`.
- Hardware bridge health endpoint availability.
- Endpoint latency warning above 3 seconds.
- Delivery operations alert rule pack for critical exceptions, retry backlog,
  retry aging, SLA breach rate, courier webhook failures, and COD
  reconciliation variance.
- Alertmanager local receiver baseline.
- Grafana Prometheus and Loki datasources.
- Grafana dashboard provider for the `Tijara Suite` folder.
- Loki local filesystem retention baseline.

Provisioned Grafana dashboards:

- `Tijara Owner And DevOps Overview`: Odoo availability, business scrape
  health, ecommerce order count/value, endpoint health, and external
  assumption-mode markers.
- `Tijara Ecommerce And Delivery Operations`: delivery orders, exceptions,
  retry backlog, retry age, SLA breach rate, courier webhook failures, and COD
  reconciliation variance.
- `Tijara Finance, PSP, And FBR Compliance`: payment webhook lifecycle,
  settlement variance, FBR queue state, certification environment, and PSP/FBR
  assumption markers.
- `Tijara Hardware And Integration Risk`: device inventory, certification
  results, bridge probe health, endpoint latency, and external certification
  assumptions.

Dashboard files live under `deploy/monitoring/grafana/dashboards/` and are
loaded by `deploy/monitoring/grafana-dashboards.yml`. Regenerate them with:

```bash
make monitoring-dashboards
make monitoring-dashboards-check
```

Capture API and browser screenshot evidence for the provisioned dashboards
after the monitoring profile is running:

```bash
make grafana-dashboard-evidence
```

The evidence writer reads `TIJARA_GRAFANA_URL`, `GRAFANA_ADMIN_USER`, and
`GRAFANA_ADMIN_PASSWORD` from the central runtime files or environment, writes
`grafana-dashboard-evidence.json`, `status.tsv`, `summary.md`, and dashboard
screenshots under `deploy/runtime/grafana-dashboard-evidence/<run-id>/`, and
supports `--metadata-only` when Grafana is not running.

Production teams should add:

- PostgreSQL exporter.
- Alertmanager routing to email, Slack, SMS, or on-call tooling.
- Promtail, Vector, Fluent Bit, or OpenTelemetry collectors for Odoo,
  PostgreSQL, Nginx/ingress, FBR adapter, and hardware bridge logs.
- Tenant-level SLO dashboards.
- A non-placeholder `TIJARA_METRICS_TOKEN` and reverse-proxy/network access
  control for `/tijara/monitoring/metrics`.

Delivery metrics contract:

```text
tijara_delivery_open_exceptions{provider,severity}
tijara_delivery_retry_pending{provider}
tijara_delivery_retry_oldest_seconds{provider}
tijara_delivery_sla_breach_rate_percent{provider}
tijara_delivery_webhook_failures_total{provider}
tijara_delivery_cod_variance_amount{provider}
tijara_ecommerce_orders_total{company,channel}
tijara_payment_events_total{company,provider,payment_event_type}
tijara_fbr_queue_total{company,state,adapter_mode}
tijara_hardware_certifications_total{company,device_type,result}
tijara_external_assumption_mode{integration}
```

`deploy/monitoring/tijara-delivery-metrics.example.prom` contains dummy sample
values for staging runbooks and exporter implementation tests.
