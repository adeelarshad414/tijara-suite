from datetime import datetime, time, timedelta

from odoo import api, fields, models


class TijaraAnalyticsSnapshot(models.Model):
    _name = "tijara.analytics.snapshot"
    _description = "Tijara Analytics KPI Snapshot"
    _order = "snapshot_date desc, business_area, metric_type"

    name = fields.Char(required=True)
    snapshot_date = fields.Date(default=fields.Date.context_today, required=True)
    period_type = fields.Selection(
        [
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
        ],
        default="day",
        required=True,
    )
    business_area = fields.Selection(
        [
            ("sales", "Sales"),
            ("pos", "POS"),
            ("purchase", "Purchase"),
            ("inventory", "Inventory"),
            ("customers", "Customers"),
            ("promotions", "Promotions"),
            ("finance", "Finance"),
            ("operations", "Operations"),
            ("backoffice", "Back Office"),
            ("payroll", "Payroll"),
            ("loyalty", "Loyalty"),
            ("food_service", "Food Service"),
            ("verticals", "Vertical Retail"),
            ("tax_policy", "Tax and Charges"),
        ],
        required=True,
        index=True,
    )
    metric_type = fields.Selection(
        [
            ("revenue", "Revenue"),
            ("gross_margin", "Gross Margin"),
            ("orders", "Orders"),
            ("basket_size", "Basket Size"),
            ("refunds", "Refunds"),
            ("stock_value", "Stock Value"),
            ("stock_turnover", "Stock Turnover"),
            ("low_stock", "Low Stock"),
            ("expiry", "Expiry"),
            ("purchase_value", "Purchase Value"),
            ("supplier_lead_time", "Supplier Lead Time"),
            ("new_customers", "New Customers"),
            ("promotion_uplift", "Promotion Uplift"),
            ("queue_wait_time", "Queue Wait Time"),
            ("queue_wait_kitchen_sla", "Queue Wait and Kitchen SLA"),
            ("cash_variance", "Cash Variance"),
            ("expense_state_totals", "Expense State Totals"),
            ("salary_net_payable", "Salary Net Payable"),
            ("restaurant_order_type_mix", "Restaurant Order Type Mix"),
            ("food_service_charge_tax_audit", "Food Service Charge and Tax Audit"),
            ("vertical_catalog_coverage", "Vertical Catalog Coverage"),
            ("vertical_b2b_b2c_margin", "B2B and B2C Margin"),
            ("loyalty_points_liability", "Loyalty Points Liability"),
            ("customer_repeat_visit_history", "Customer Repeat Visit History"),
        ],
        required=True,
        index=True,
    )
    amount = fields.Monetary(currency_field="currency_id")
    quantity = fields.Float()
    count = fields.Integer()
    rate = fields.Float(string="Rate / Percentage")
    target_amount = fields.Monetary(currency_field="currency_id")
    target_quantity = fields.Float()
    target_count = fields.Integer()
    variance_amount = fields.Monetary(currency_field="currency_id")
    variance_rate = fields.Float()
    warehouse_id = fields.Many2one("stock.warehouse")
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    notes = fields.Text()

    @api.model
    def action_collect_daily_snapshots(self):
        return self._collect_daily_snapshots()

    @api.model
    def _collect_daily_snapshots(self, snapshot_date=False):
        snapshot_date = snapshot_date or fields.Date.context_today(self)
        start = datetime.combine(fields.Date.to_date(snapshot_date), time.min)
        stop = start + timedelta(days=1)
        start_value = fields.Datetime.to_string(start)
        stop_value = fields.Datetime.to_string(stop)

        companies = self.env["res.company"].search([])
        for company in companies:
            self._collect_company_daily_snapshots(company, snapshot_date, start_value, stop_value)
        return True

    @api.model
    def _collect_company_daily_snapshots(self, company, snapshot_date, start_value, stop_value):
        PosOrder = self.env["pos.order"].sudo()
        order_domain = [
            ("company_id", "=", company.id),
            ("date_order", ">=", start_value),
            ("date_order", "<", stop_value),
            ("state", "in", ("paid", "done", "invoiced")),
        ]
        orders = PosOrder.search(order_domain)
        revenue = sum(orders.mapped("amount_total"))
        order_count = len(orders)
        refund_orders = orders.filtered(lambda order: order.amount_total < 0)
        basket_size = revenue / order_count if order_count else 0.0

        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Revenue",
            "pos",
            "revenue",
            amount=revenue,
            count=order_count,
            notes="Collected from paid/done/invoiced POS orders.",
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Orders",
            "pos",
            "orders",
            count=order_count,
            notes="Collected from paid/done/invoiced POS orders.",
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Basket Size",
            "pos",
            "basket_size",
            amount=basket_size,
            notes="Average POS order value.",
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "POS Refunds",
            "pos",
            "refunds",
            amount=sum(refund_orders.mapped("amount_total")),
            count=len(refund_orders),
            notes="Negative-total POS orders.",
        )

        if "tijara.inventory.alert" in self.env.registry:
            Alert = self.env["tijara.inventory.alert"].sudo()
            low_count = Alert.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("new", "acknowledged")),
                    ("alert_type", "in", ("low_stock", "critical_stock")),
                ]
            )
            expiry_count = Alert.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("new", "acknowledged")),
                    ("alert_type", "=", "expiry"),
                ]
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Open Low Stock Alerts",
                "inventory",
                "low_stock",
                count=low_count,
                notes="Open low and critical stock alerts.",
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Open Expiry Alerts",
                "inventory",
                "expiry",
                count=expiry_count,
                notes="Open expiry alerts.",
            )

        if "tijara.queue.ticket" in self.env.registry:
            tickets = self.env["tijara.queue.ticket"].sudo().search(
                [
                    ("company_id", "=", company.id),
                    ("called_at", ">=", start_value),
                    ("called_at", "<", stop_value),
                ]
            )
            wait_minutes = []
            for ticket in tickets:
                if ticket.create_date and ticket.called_at:
                    wait_minutes.append(
                        (ticket.called_at - ticket.create_date).total_seconds() / 60.0
                    )
            average_wait = sum(wait_minutes) / len(wait_minutes) if wait_minutes else 0.0
            kitchen_count = 0
            if "tijara.kitchen.ticket" in self.env.registry:
                kitchen_count = self.env["tijara.kitchen.ticket"].sudo().search_count(
                    [
                        ("company_id", "=", company.id),
                        ("create_date", ">=", start_value),
                        ("create_date", "<", stop_value),
                        ("state", "in", ("sent", "preparing", "ready")),
                    ]
                )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Average Queue Wait",
                "operations",
                "queue_wait_time",
                quantity=average_wait,
                count=len(wait_minutes),
                notes="Average minutes from ticket creation to call.",
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Queue Wait and Kitchen SLA",
                "operations",
                "queue_wait_kitchen_sla",
                quantity=average_wait,
                count=len(wait_minutes) + kitchen_count,
                notes=(
                    "Average called-ticket wait minutes; active kitchen SLA tickets=%s."
                    % kitchen_count
                ),
            )

        if "tijara.promotion" in self.env.registry:
            promo_count = self.env["tijara.promotion"].sudo().search_count(
                [
                    ("company_id", "=", company.id),
                    ("active", "=", True),
                    "|",
                    ("start_at", "=", False),
                    ("start_at", "<=", stop_value),
                    "|",
                    ("end_at", "=", False),
                    ("end_at", ">=", start_value),
                ]
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Active Promotions",
                "promotions",
                "promotion_uplift",
                count=promo_count,
                notes="Active promotions/deals available during the period.",
            )

        self._collect_backoffice_finance_snapshots(
            company, snapshot_date, start_value, stop_value
        )
        self._collect_loyalty_customer_snapshots(company, snapshot_date, start_value, stop_value)
        self._collect_vertical_catalog_snapshots(company, snapshot_date)
        self._collect_food_service_snapshots(company, snapshot_date, start_value, stop_value)

    @api.model
    def _model_has_field(self, model_name, field_name):
        return model_name in self.env.registry and field_name in self.env[model_name]._fields

    @api.model
    def _format_number(self, value):
        if isinstance(value, float):
            return "%.2f" % value
        return str(value)

    @api.model
    def _breakdown_note(self, label, values):
        parts = [
            "%s=%s" % (key, self._format_number(values[key]))
            for key in sorted(values)
            if values[key]
        ]
        return "%s: %s." % (label, ", ".join(parts) if parts else "none")

    @api.model
    def _collect_backoffice_finance_snapshots(
        self, company, snapshot_date, start_value, stop_value
    ):
        if "tijara.expense.request" in self.env.registry:
            expenses = self.env["tijara.expense.request"].sudo().search(
                [
                    ("company_id", "=", company.id),
                    ("expense_date", "=", snapshot_date),
                ]
            )
            amount_by_state = {}
            count_by_state = {}
            for expense in expenses:
                state = expense.state or "unknown"
                amount_by_state[state] = amount_by_state.get(state, 0.0) + (
                    expense.total_amount or expense.amount or 0.0
                )
                count_by_state[state] = count_by_state.get(state, 0) + 1
            active_expenses = expenses.filtered(lambda expense: expense.state != "cancelled")
            notes = "%s %s" % (
                self._breakdown_note("amount_by_state", amount_by_state),
                self._breakdown_note("count_by_state", count_by_state),
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Expense Approval Pipeline",
                "backoffice",
                "expense_state_totals",
                amount=sum(active_expenses.mapped("total_amount")),
                count=len(active_expenses),
                notes=notes,
            )

        if "tijara.salary.batch" in self.env.registry:
            batches = self.env["tijara.salary.batch"].sudo().search(
                [
                    ("company_id", "=", company.id),
                    ("period_start", "<=", snapshot_date),
                    ("period_end", ">=", snapshot_date),
                    ("state", "!=", "cancelled"),
                ]
            )
            net_by_state = {}
            gross_total = 0.0
            deduction_total = 0.0
            bonus_total = 0.0
            line_count = 0
            for batch in batches:
                state = batch.state or "unknown"
                net_by_state[state] = net_by_state.get(state, 0.0) + (batch.net_total or 0.0)
                gross_total += batch.gross_total or 0.0
                deduction_total += batch.deduction_total or 0.0
                bonus_total += batch.bonus_total or 0.0
                line_count += len(batch.line_ids)
            net_payable = sum(
                batch.net_total or 0.0 for batch in batches if batch.state in ("draft", "approved")
            )
            notes = "%s gross=%s, deductions=%s, bonuses=%s." % (
                self._breakdown_note("net_by_state", net_by_state),
                self._format_number(gross_total),
                self._format_number(deduction_total),
                self._format_number(bonus_total),
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Salary Net Payable",
                "payroll",
                "salary_net_payable",
                amount=net_payable,
                quantity=gross_total,
                count=line_count,
                notes=notes,
            )

    @api.model
    def _collect_loyalty_customer_snapshots(
        self, company, snapshot_date, start_value, stop_value
    ):
        Partner = self.env["res.partner"].sudo()
        if self._model_has_field("res.partner", "tijara_loyalty_opt_in"):
            loyalty_domain = [
                ("company_id", "in", [False, company.id]),
                ("tijara_loyalty_opt_in", "=", True),
            ]
            loyalty_partners = Partner.search(loyalty_domain)
            points_by_tier = {}
            count_by_tier = {}
            for partner in loyalty_partners:
                tier = partner.tijara_loyalty_tier or "standard"
                points_by_tier[tier] = points_by_tier.get(tier, 0.0) + (
                    partner.tijara_loyalty_points or 0.0
                )
                count_by_tier[tier] = count_by_tier.get(tier, 0) + 1
            customer_domain = [("company_id", "in", [False, company.id])]
            if "customer_rank" in Partner._fields:
                customer_domain.append(("customer_rank", ">", 0))
            customer_count = Partner.search_count(customer_domain) or len(loyalty_partners)
            total_points = sum(points_by_tier.values())
            rate = (len(loyalty_partners) / customer_count * 100.0) if customer_count else 0.0
            notes = "%s %s Assumption: 1 loyalty point is reported as 1 PKR liability until redemption policy is configured." % (
                self._breakdown_note("points_by_tier", points_by_tier),
                self._breakdown_note("count_by_tier", count_by_tier),
            )
            self._upsert_snapshot(
                company,
                snapshot_date,
                "Loyalty Points Liability",
                "loyalty",
                "loyalty_points_liability",
                amount=total_points,
                quantity=total_points,
                count=len(loyalty_partners),
                rate=rate,
                notes=notes,
            )

        PosOrder = self.env["pos.order"].sudo()
        order_domain = [
            ("company_id", "=", company.id),
            ("date_order", ">=", start_value),
            ("date_order", "<", stop_value),
            ("state", "in", ("paid", "done", "invoiced")),
            ("partner_id", "!=", False),
        ]
        daily_orders = PosOrder.search(order_domain)
        repeat_partner_ids = set()
        repeat_revenue = 0.0
        for partner in daily_orders.mapped("partner_id"):
            partner_orders = PosOrder.search(
                [
                    ("company_id", "=", company.id),
                    ("date_order", "<", stop_value),
                    ("state", "in", ("paid", "done", "invoiced")),
                    ("partner_id", "=", partner.id),
                ]
            )
            if len(partner_orders) >= 2:
                repeat_partner_ids.add(partner.id)
                repeat_revenue += sum(
                    daily_orders.filtered(lambda order: order.partner_id == partner).mapped(
                        "amount_total"
                    )
                )
        distinct_daily_customers = len(set(daily_orders.mapped("partner_id").ids))
        repeat_rate = (
            len(repeat_partner_ids) / distinct_daily_customers * 100.0
            if distinct_daily_customers
            else 0.0
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "Customer Repeat Visit History",
            "customers",
            "customer_repeat_visit_history",
            amount=repeat_revenue,
            count=len(repeat_partner_ids),
            rate=repeat_rate,
            notes=(
                "Repeat customers with at least two paid/done/invoiced POS orders "
                "up to the snapshot date."
            ),
        )

    @api.model
    def _collect_vertical_catalog_snapshots(self, company, snapshot_date):
        if not self._model_has_field("product.template", "tijara_vertical_tag"):
            return
        ProductTemplate = self.env["product.template"].sudo()
        domain = [
            ("sale_ok", "=", True),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company.id),
        ]
        if "active" in ProductTemplate._fields:
            domain.insert(0, ("active", "=", True))
        products = ProductTemplate.search(domain)
        count_by_vertical = {}
        b2c_catalog_value = 0.0
        margin_products = 0
        total_price_spread = 0.0
        total_margin_rate = 0.0
        for product in products:
            vertical = product.tijara_vertical_tag or "uncategorized"
            count_by_vertical[vertical] = count_by_vertical.get(vertical, 0) + 1
            b2c_price = product.tijara_b2c_price or product.list_price or 0.0
            b2b_price = product.tijara_b2b_price or 0.0
            b2c_catalog_value += b2c_price
            if b2c_price and b2b_price:
                spread = b2c_price - b2b_price
                total_price_spread += spread
                total_margin_rate += spread / b2c_price * 100.0
                margin_products += 1
        self._upsert_snapshot(
            company,
            snapshot_date,
            "Vertical Catalog Coverage",
            "verticals",
            "vertical_catalog_coverage",
            amount=b2c_catalog_value,
            quantity=len(count_by_vertical),
            count=len(products),
            notes=self._breakdown_note("sku_count_by_vertical", count_by_vertical),
        )
        average_spread = total_price_spread / margin_products if margin_products else 0.0
        average_margin_rate = total_margin_rate / margin_products if margin_products else 0.0
        self._upsert_snapshot(
            company,
            snapshot_date,
            "B2B and B2C Price Margin",
            "verticals",
            "vertical_b2b_b2c_margin",
            amount=average_spread,
            count=margin_products,
            rate=average_margin_rate,
            notes=(
                "Average B2C minus B2B price spread across saleable products "
                "with both Tijara prices."
            ),
        )

    @api.model
    def _collect_food_service_snapshots(self, company, snapshot_date, start_value, stop_value):
        if "tijara.kiosk.order" not in self.env.registry:
            return
        orders = self.env["tijara.kiosk.order"].sudo().search(
            [
                ("company_id", "=", company.id),
                ("create_date", ">=", start_value),
                ("create_date", "<", stop_value),
                ("state", "!=", "cancelled"),
            ]
        )
        order_type_counts = {}
        for order in orders:
            order_type = order.order_type or "unknown"
            order_type_counts[order_type] = order_type_counts.get(order_type, 0) + 1
        total_amount = sum(orders.mapped("amount_total"))
        service_charge = sum(orders.mapped("amount_service_charge"))
        delivery_charge = sum(orders.mapped("amount_delivery_charge"))
        payment_tax = sum(orders.mapped("amount_payment_tax"))
        gst = sum(orders.mapped("amount_gst"))
        charged_count = len(
            orders.filtered(
                lambda order: order.amount_service_charge
                or order.amount_delivery_charge
                or order.amount_payment_tax
            )
        )
        policy_notes = (
            "%s service_charge=%s, delivery_charge=%s, payment_tax=%s, gst=%s, "
            "business_type=%s, gst_enabled=%s, service_charge_enabled=%s, "
            "delivery_charge_enabled=%s, food_payment_tax_enabled=%s."
            % (
                self._breakdown_note("order_type_count", order_type_counts),
                self._format_number(service_charge),
                self._format_number(delivery_charge),
                self._format_number(payment_tax),
                self._format_number(gst),
                getattr(company, "tijara_business_type", ""),
                bool(getattr(company, "tijara_gst_enabled", False)),
                bool(getattr(company, "tijara_service_charge_enabled", False)),
                bool(getattr(company, "tijara_delivery_charge_enabled", False)),
                bool(getattr(company, "tijara_food_payment_tax_enabled", False)),
            )
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "Dine-in Takeaway Pickup Delivery Mix",
            "food_service",
            "restaurant_order_type_mix",
            amount=total_amount,
            count=len(orders),
            notes=self._breakdown_note("order_type_count", order_type_counts),
        )
        self._upsert_snapshot(
            company,
            snapshot_date,
            "Service Charge and Card/Cash Tax Audit",
            "tax_policy",
            "food_service_charge_tax_audit",
            amount=service_charge + delivery_charge + payment_tax,
            quantity=gst,
            count=charged_count,
            notes=policy_notes,
        )

    @api.model
    def _upsert_snapshot(
        self,
        company,
        snapshot_date,
        name,
        business_area,
        metric_type,
        amount=0.0,
        quantity=0.0,
        count=0,
        rate=0.0,
        notes="",
    ):
        domain = [
            ("company_id", "=", company.id),
            ("snapshot_date", "=", snapshot_date),
            ("period_type", "=", "day"),
            ("business_area", "=", business_area),
            ("metric_type", "=", metric_type),
            ("warehouse_id", "=", False),
        ]
        values = {
            "name": name,
            "company_id": company.id,
            "snapshot_date": snapshot_date,
            "period_type": "day",
            "business_area": business_area,
            "metric_type": metric_type,
            "amount": amount,
            "quantity": quantity,
            "count": count,
            "rate": rate,
            "notes": notes,
        }
        snapshot = self.search(domain, limit=1)
        if snapshot:
            snapshot.write(values)
        else:
            self.create(values)
