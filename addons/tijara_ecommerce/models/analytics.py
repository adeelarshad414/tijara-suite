from odoo import fields, models


class TijaraAnalyticsWidget(models.Model):
    _inherit = "tijara.analytics.widget"

    business_area = fields.Selection(
        selection_add=[("ecommerce", "Ecommerce")],
        ondelete={"ecommerce": "cascade"},
    )


class TijaraAnalyticsReport(models.Model):
    _inherit = "tijara.analytics.report"

    business_area = fields.Selection(
        selection_add=[("ecommerce", "Ecommerce")],
        ondelete={"ecommerce": "cascade"},
    )


class TijaraAnalyticsSnapshot(models.Model):
    _inherit = "tijara.analytics.snapshot"

    business_area = fields.Selection(
        selection_add=[("ecommerce", "Ecommerce")],
        ondelete={"ecommerce": "cascade"},
    )
    metric_type = fields.Selection(
        selection_add=[
            ("ecommerce_order_pipeline", "Ecommerce Order Pipeline"),
            ("delivery_sla_breach_rate", "Delivery SLA Breach Rate"),
            ("delivery_retry_aging", "Delivery Retry Aging"),
            ("courier_success_rate", "Courier Success Rate"),
            ("cod_receivable_aging", "COD Receivable Aging"),
            ("delivery_reconciliation_variance", "Delivery Reconciliation Variance"),
        ],
        ondelete={
            "ecommerce_order_pipeline": "cascade",
            "delivery_sla_breach_rate": "cascade",
            "delivery_retry_aging": "cascade",
            "courier_success_rate": "cascade",
            "cod_receivable_aging": "cascade",
            "delivery_reconciliation_variance": "cascade",
        },
    )

    def _collect_company_daily_snapshots(self, company, snapshot_date, start_value, stop_value):
        result = super()._collect_company_daily_snapshots(company, snapshot_date, start_value, stop_value)
        self._collect_ecommerce_delivery_snapshots(company, snapshot_date, start_value, stop_value)
        return result

    def _collect_ecommerce_delivery_snapshots(self, company, snapshot_date, start_value, stop_value):
        if "sale.order" not in self.env.registry:
            return
        order_model = self.env["sale.order"].sudo()
        orders = order_model.search(
            [
                ("company_id", "=", company.id),
                ("tijara_ecommerce_channel_id", "!=", False),
                ("date_order", ">=", start_value),
                ("date_order", "<", stop_value),
            ]
        )
        delivery_orders = orders.filtered(lambda order: order.tijara_fulfillment_method in ("delivery", "courier"))
        order_count = len(orders)
        revenue = sum(orders.mapped("amount_total"))
        payment_status_counts = {}
        fulfillment_counts = {}
        for order in orders:
            payment_status = order.tijara_payment_status or "unknown"
            fulfillment = order.tijara_fulfillment_method or "unknown"
            payment_status_counts[payment_status] = payment_status_counts.get(payment_status, 0) + 1
            fulfillment_counts[fulfillment] = fulfillment_counts.get(fulfillment, 0) + 1
        self._upsert_snapshot(
            company,
            snapshot_date,
            "Ecommerce Order Pipeline",
            "ecommerce",
            "ecommerce_order_pipeline",
            amount=revenue,
            count=order_count,
            notes="%s %s"
            % (
                self._breakdown_note("payment_status", payment_status_counts),
                self._breakdown_note("fulfillment", fulfillment_counts),
            ),
        )

        if "tijara.ecommerce.delivery.exception" in self.env.registry:
            exception_model = self.env["tijara.ecommerce.delivery.exception"].sudo()
            sla_exceptions = exception_model.search(
                [
                    ("company_id", "=", company.id),
                    ("category", "=", "sla_breach"),
                    ("detected_at", ">=", start_value),
                    ("detected_at", "<", stop_value),
                ]
            )
            delivery_count = len(delivery_orders)
            breach_rate = (len(sla_exceptions) / delivery_count * 100.0) if delivery_count else 0.0
            open_critical = exception_model.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ["open", "acknowledged"]),
                    ("severity", "=", "critical"),
                ]
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Delivery SLA Breach Rate",
                "ecommerce",
                "delivery_sla_breach_rate",
                count=len(sla_exceptions),
                rate=breach_rate,
                notes="Open critical delivery exceptions=%s." % open_critical,
            )

        if "tijara.ecommerce.delivery.retry" in self.env.registry:
            retry_model = self.env["tijara.ecommerce.delivery.retry"].sudo()
            open_retries = retry_model.search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ["pending", "running", "failed"]),
                ]
            )
            now = fields.Datetime.now()
            ages = [
                (now - (retry.create_date or now)).total_seconds() / 60.0
                for retry in open_retries
            ]
            oldest_age = max(ages) if ages else 0.0
            failed_count = len(open_retries.filtered(lambda retry: retry.state == "failed"))
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Delivery Retry Aging",
                "ecommerce",
                "delivery_retry_aging",
                quantity=oldest_age,
                count=len(open_retries),
                rate=failed_count,
                notes="Oldest open retry age in minutes; failed open retries=%s." % failed_count,
            )

        delivered = len(delivery_orders.filtered(lambda order: order.tijara_delivery_status == "delivered"))
        failed = len(delivery_orders.filtered(lambda order: order.tijara_delivery_status == "failed"))
        cancelled = len(delivery_orders.filtered(lambda order: order.tijara_delivery_status == "cancelled"))
        terminal = delivered + failed + cancelled
        success_rate = (delivered / terminal * 100.0) if terminal else 0.0
        self._upsert_snapshot(
            company,
            snapshot_date,
            "Courier Success Rate",
            "ecommerce",
            "courier_success_rate",
            count=terminal,
            rate=success_rate,
            notes="Delivered=%s, failed=%s, cancelled=%s." % (delivered, failed, cancelled),
        )

        cod_orders = self.env["sale.order"].sudo().search(
            [
                ("company_id", "=", company.id),
                ("tijara_ecommerce_channel_id", "!=", False),
                ("tijara_payment_method", "=", "cod"),
                ("tijara_payment_status", "in", ["cod", "pending", "authorized"]),
            ]
        )
        cod_amount = sum(cod_orders.mapped("amount_total"))
        oldest_cod_age = 0.0
        now = fields.Datetime.now()
        if cod_orders:
            oldest_cod_age = max(
                (now - (order.date_order or now)).total_seconds() / 86400.0 for order in cod_orders
            )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "COD Receivable Aging",
            "ecommerce",
            "cod_receivable_aging",
            amount=cod_amount,
            quantity=oldest_cod_age,
            count=len(cod_orders),
            notes="Open COD ecommerce receivable; oldest age in days.",
        )

        if "tijara.ecommerce.delivery.reconciliation.line" in self.env.registry:
            lines = self.env["tijara.ecommerce.delivery.reconciliation.line"].sudo().search(
                [
                    ("company_id", "=", company.id),
                    ("reconciliation_id.date_from", "<=", snapshot_date),
                    ("reconciliation_id.date_to", ">=", snapshot_date),
                ]
            )
            variance = sum(line.cod_amount - line.provider_fee - line.net_receivable for line in lines)
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Delivery Reconciliation Variance",
                "ecommerce",
                "delivery_reconciliation_variance",
                amount=variance,
                count=len(lines),
                notes="Expected zero when COD minus provider fee equals net receivable.",
            )
