from datetime import timedelta

from odoo import fields, models


class TijaraMonitoringMetrics(models.AbstractModel):
    _name = "tijara.monitoring.metrics"
    _description = "Tijara Prometheus Business Metrics Exporter"

    def _escape_label(self, value):
        value = str(value if value is not None else "")
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    def _label_value(self, record, field_name):
        value = getattr(record, field_name, False)
        if hasattr(value, "_name"):
            return (
                getattr(value, "code", False)
                or getattr(value, "name", False)
                or getattr(value, "display_name", False)
                or str(value.id)
            )
        return value or "unknown"

    def _label_key(self, field_name):
        aliases = {
            "company_id": "company",
            "provider_id": "provider",
            "tijara_delivery_provider_id": "provider",
            "tijara_ecommerce_channel_id": "channel",
            "tijara_fulfillment_method": "fulfillment",
            "tijara_payment_method": "payment_method",
            "tijara_payment_status": "payment_status",
            "tijara_delivery_status": "delivery_status",
            "tijara_delivery_adapter_state": "adapter_state",
        }
        return aliases.get(field_name, field_name)

    def _metric_line(self, name, value, labels=None):
        labels = labels or {}
        label_text = ""
        if labels:
            label_text = "{%s}" % ",".join(
                '%s="%s"' % (key, self._escape_label(labels[key]))
                for key in sorted(labels)
            )
        return "%s%s %.6f" % (name, label_text, float(value or 0.0))

    def _append_header(self, lines, name, help_text, metric_type="gauge"):
        lines.append("# HELP %s %s" % (name, help_text))
        lines.append("# TYPE %s %s" % (name, metric_type))

    def _group_count_lines(self, model_name, metric_name, domain, label_fields):
        if model_name not in self.env.registry:
            return []
        counts = {}
        for record in self.env[model_name].sudo().search(domain):
            labels = tuple(
                (self._label_key(field), self._label_value(record, field))
                for field in label_fields
            )
            counts[labels] = counts.get(labels, 0) + 1
        return [
            self._metric_line(metric_name, count, dict(labels))
            for labels, count in sorted(counts.items())
        ]

    def _group_sum_lines(self, model_name, metric_name, domain, label_fields, amount_field):
        if model_name not in self.env.registry:
            return []
        sums = {}
        for record in self.env[model_name].sudo().search(domain):
            labels = tuple(
                (self._label_key(field), self._label_value(record, field))
                for field in label_fields
            )
            sums[labels] = sums.get(labels, 0.0) + (getattr(record, amount_field, 0.0) or 0.0)
        return [
            self._metric_line(metric_name, amount, dict(labels))
            for labels, amount in sorted(sums.items())
        ]

    def _provider_label(self, provider):
        return provider.code or provider.name or str(provider.id)

    def _delivery_retry_metrics(self, lines):
        metric_name = "tijara_delivery_retry_pending"
        self._append_header(lines, metric_name, "Open delivery retry queue items by provider.")
        if "tijara.ecommerce.delivery.provider" not in self.env.registry:
            return
        retry_model = self.env["tijara.ecommerce.delivery.retry"].sudo()
        for provider in self.env["tijara.ecommerce.delivery.provider"].sudo().search([]):
            count = retry_model.search_count(
                [
                    ("provider_id", "=", provider.id),
                    ("state", "in", ["pending", "running", "failed"]),
                ]
            )
            lines.append(self._metric_line(metric_name, count, {"provider": self._provider_label(provider)}))

        metric_name = "tijara_delivery_retry_oldest_seconds"
        self._append_header(lines, metric_name, "Oldest open delivery retry age in seconds by provider.")
        now = fields.Datetime.now()
        for provider in self.env["tijara.ecommerce.delivery.provider"].sudo().search([]):
            retries = retry_model.search(
                [
                    ("provider_id", "=", provider.id),
                    ("state", "in", ["pending", "running", "failed"]),
                ]
            )
            oldest = 0.0
            for retry in retries:
                created = retry.create_date or now
                oldest = max(oldest, (now - created).total_seconds())
            lines.append(self._metric_line(metric_name, oldest, {"provider": self._provider_label(provider)}))

    def _delivery_sla_metrics(self, lines):
        if "tijara.ecommerce.delivery.provider" not in self.env.registry:
            return
        exception_model = self.env["tijara.ecommerce.delivery.exception"].sudo()
        order_model = self.env["sale.order"].sudo()
        providers = self.env["tijara.ecommerce.delivery.provider"].sudo().search([])
        now = fields.Datetime.now()
        cutoff = now - timedelta(hours=24)

        metric_name = "tijara_delivery_sla_breach_rate_percent"
        self._append_header(lines, metric_name, "Last 24 hour delivery SLA breach rate by provider.")
        for provider in providers:
            delivery_count = order_model.search_count(
                [
                    ("tijara_delivery_provider_id", "=", provider.id),
                    ("tijara_ecommerce_channel_id", "!=", False),
                    ("date_order", ">=", cutoff),
                ]
            )
            breach_count = exception_model.search_count(
                [
                    ("provider_id", "=", provider.id),
                    ("category", "=", "sla_breach"),
                    ("detected_at", ">=", cutoff),
                ]
            )
            rate = (breach_count / delivery_count * 100.0) if delivery_count else 0.0
            lines.append(self._metric_line(metric_name, rate, {"provider": self._provider_label(provider)}))

        metric_name = "tijara_delivery_webhook_failures_total"
        self._append_header(lines, metric_name, "Delivery webhook/manual sync failures by provider.", "counter")
        for provider in providers:
            count = exception_model.search_count(
                [
                    ("provider_id", "=", provider.id),
                    ("category", "=", "webhook_error"),
                ]
            )
            lines.append(self._metric_line(metric_name, count, {"provider": self._provider_label(provider)}))

        metric_name = "tijara_delivery_cod_variance_amount"
        self._append_header(lines, metric_name, "COD reconciliation variance in company currency by provider.")
        reconciliation_model = self.env["tijara.ecommerce.delivery.reconciliation"].sudo()
        for provider in providers:
            variance = 0.0
            for reconciliation in reconciliation_model.search([("provider_id", "=", provider.id)]):
                variance += (
                    (reconciliation.cod_amount_total or 0.0)
                    - (reconciliation.provider_fee_total or 0.0)
                    - (reconciliation.net_receivable or 0.0)
                )
            lines.append(self._metric_line(metric_name, variance, {"provider": self._provider_label(provider)}))

    def _external_assumption_metrics(self, lines):
        metric_name = "tijara_external_assumption_mode"
        self._append_header(
            lines,
            metric_name,
            "Assumption-mode marker for integrations that still need certified live evidence.",
        )
        config = self.env["ir.config_parameter"].sudo()
        assumptions = {
            "courier": config.get_param("tijara.delivery.certification_status", "assumed") != "certified",
            "fbr": config.get_param("tijara.fbr.certification_status", "assumed") != "certified",
            "hardware": config.get_param("tijara.hardware.certification_status", "assumed") != "certified",
            "psp": config.get_param("tijara.psp.certification_status", "assumed") != "certified",
        }
        for integration, enabled in assumptions.items():
            lines.append(self._metric_line(metric_name, 1 if enabled else 0, {"integration": integration}))

    def tijara_prometheus_payload(self):
        lines = []
        self._append_header(
            lines,
            "tijara_ecommerce_orders_total",
            "Ecommerce sale orders by channel, fulfillment, payment, payment status, and state.",
        )
        lines.extend(
            self._group_count_lines(
                "sale.order",
                "tijara_ecommerce_orders_total",
                [("tijara_ecommerce_channel_id", "!=", False)],
                [
                    "company_id",
                    "tijara_ecommerce_channel_id",
                    "tijara_fulfillment_method",
                    "tijara_payment_method",
                    "tijara_payment_status",
                    "state",
                ],
            )
        )

        self._append_header(
            lines,
            "tijara_ecommerce_order_amount_pkr",
            "Ecommerce order amount by channel and payment status.",
        )
        lines.extend(
            self._group_sum_lines(
                "sale.order",
                "tijara_ecommerce_order_amount_pkr",
                [("tijara_ecommerce_channel_id", "!=", False)],
                ["company_id", "tijara_ecommerce_channel_id", "tijara_payment_status"],
                "amount_total",
            )
        )

        self._append_header(
            lines,
            "tijara_ecommerce_delivery_orders_total",
            "Ecommerce delivery/courier orders by provider, status, and adapter state.",
        )
        lines.extend(
            self._group_count_lines(
                "sale.order",
                "tijara_ecommerce_delivery_orders_total",
                [("tijara_delivery_provider_id", "!=", False)],
                [
                    "company_id",
                    "tijara_delivery_provider_id",
                    "tijara_delivery_status",
                    "tijara_delivery_adapter_state",
                ],
            )
        )

        self._append_header(
            lines,
            "tijara_delivery_open_exceptions",
            "Open or acknowledged delivery exceptions by provider, severity, category, and state.",
        )
        lines.extend(
            self._group_count_lines(
                "tijara.ecommerce.delivery.exception",
                "tijara_delivery_open_exceptions",
                [("state", "in", ["open", "acknowledged"])],
                ["company_id", "provider_id", "severity", "category", "state"],
            )
        )
        self._delivery_retry_metrics(lines)
        self._delivery_sla_metrics(lines)

        self._append_header(
            lines,
            "tijara_payment_events_total",
            "SaaS/payment webhook lifecycle events by provider and reconciliation state.",
        )
        lines.extend(
            self._group_count_lines(
                "tijara.saas.payment.webhook.event",
                "tijara_payment_events_total",
                [],
                [
                    "company_id",
                    "provider",
                    "payment_event_type",
                    "status",
                    "signature_status",
                    "reconciliation_status",
                ],
            )
        )

        self._append_header(
            lines,
            "tijara_payment_settlement_variance_pkr",
            "Payment settlement net delta by provider and reconciliation status.",
        )
        lines.extend(
            self._group_sum_lines(
                "tijara.saas.payment.settlement.batch",
                "tijara_payment_settlement_variance_pkr",
                [],
                ["company_id", "provider", "reconciliation_status", "finance_approval_status"],
                "net_delta",
            )
        )

        self._append_header(
            lines,
            "tijara_fbr_queue_total",
            "FBR invoice queue items by state, adapter mode, compliance status, and environment.",
        )
        lines.extend(
            self._group_count_lines(
                "tijara.fbr.invoice.queue",
                "tijara_fbr_queue_total",
                [],
                ["company_id", "state", "adapter_mode", "compliance_status", "certification_environment"],
            )
        )

        self._append_header(
            lines,
            "tijara_hardware_certifications_total",
            "Hardware certification records by device type, certification type, and result.",
        )
        lines.extend(
            self._group_count_lines(
                "tijara.hardware.certification",
                "tijara_hardware_certifications_total",
                [],
                ["company_id", "device_type", "certification_type", "result"],
            )
        )

        self._append_header(
            lines,
            "tijara_hardware_devices_total",
            "Hardware devices by type, connection, and integration status.",
        )
        lines.extend(
            self._group_count_lines(
                "tijara.hardware.device",
                "tijara_hardware_devices_total",
                [],
                ["company_id", "device_type", "connection_type", "integration_status"],
            )
        )
        self._external_assumption_metrics(lines)
        lines.append("")
        return "\n".join(lines)
