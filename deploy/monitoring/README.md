# Tijara Monitoring

This profile uses open-source Prometheus, Blackbox Exporter, Alertmanager,
Grafana, and Loki for first-line availability checks, alert routing foundation,
dashboards, and log aggregation foundation.

Start it with:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets --profile monitoring up -d prometheus blackbox alertmanager loki grafana
```

Current checks:

- Odoo login endpoint availability.
- Hardware bridge health endpoint availability.
- Endpoint latency warning above 3 seconds.
- Delivery operations alert rule pack for critical exceptions, retry backlog,
  retry aging, SLA breach rate, courier webhook failures, and COD
  reconciliation variance. These rules use assumed OpenMetrics names until a
  real Odoo/business metrics exporter or log-derived metrics pipeline is
  connected.
- Alertmanager local receiver baseline.
- Grafana Prometheus and Loki datasources.
- Loki local filesystem retention baseline.

Production teams should add:

- Odoo business metrics exporter or log-derived metrics.
- PostgreSQL exporter.
- Alertmanager routing to email, Slack, SMS, or on-call tooling.
- Promtail, Vector, Fluent Bit, or OpenTelemetry collectors for Odoo,
  PostgreSQL, Nginx/ingress, FBR adapter, and hardware bridge logs.
- Tenant-level SLO dashboards.

Delivery metrics contract:

```text
tijara_delivery_open_exceptions{provider,severity}
tijara_delivery_retry_pending{provider}
tijara_delivery_retry_oldest_seconds{provider}
tijara_delivery_sla_breach_rate_percent{provider}
tijara_delivery_webhook_failures_total{provider}
tijara_delivery_cod_variance_amount{provider}
```

`deploy/monitoring/tijara-delivery-metrics.example.prom` contains dummy sample
values for staging runbooks and exporter implementation tests.
