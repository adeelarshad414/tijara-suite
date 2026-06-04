# Tijara Logging

Production deployments should centralize logs from:

- Odoo application workers.
- PostgreSQL.
- Nginx or ingress proxy.
- Hardware bridge services at each branch.
- FBR adapter/proxy service.
- Backup and restore jobs.

Open-source options:

- Grafana Loki with Promtail.
- OpenSearch.
- Vector or Fluent Bit for collection.

Minimum production retention:

- 30 days hot searchable logs.
- 180 days archived audit/security logs.
- Separate retention for payment, FBR, and invoice audit events according to
  local compliance requirements.

