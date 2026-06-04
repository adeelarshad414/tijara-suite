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
