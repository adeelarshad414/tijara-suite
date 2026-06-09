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
- Loki local filesystem retention baseline.

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
