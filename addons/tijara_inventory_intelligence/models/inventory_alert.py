from datetime import timedelta

from odoo import api, fields, models


class TijaraInventoryAlert(models.Model):
    _name = "tijara.inventory.alert"
    _description = "Tijara Inventory Alert"
    _order = "severity desc, alert_date desc, id desc"

    name = fields.Char(required=True)
    alert_type = fields.Selection(
        [
            ("low_stock", "Low Stock"),
            ("critical_stock", "Critical Stock"),
            ("expiry", "Expiry"),
            ("overstock", "Overstock"),
            ("misplaced", "Misplaced"),
            ("dead_stock", "Dead Stock"),
        ],
        required=True,
        index=True,
    )
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        required=True,
        default="warning",
        index=True,
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("acknowledged", "Acknowledged"),
            ("resolved", "Resolved"),
        ],
        required=True,
        default="new",
        index=True,
    )
    product_id = fields.Many2one("product.product", string="Product", index=True)
    product_tmpl_id = fields.Many2one(
        "product.template",
        related="product_id.product_tmpl_id",
        store=True,
        string="Product Template",
    )
    lot_id = fields.Many2one("stock.lot", string="Lot / Batch")
    location_id = fields.Many2one("stock.location", string="Location")
    position_id = fields.Many2one("tijara.storage.position", string="Storage Position")
    quantity = fields.Float()
    threshold = fields.Float()
    expiry_date = fields.Datetime()
    alert_date = fields.Datetime(default=fields.Datetime.now, index=True)
    last_seen_date = fields.Datetime(default=fields.Datetime.now)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    notes = fields.Text()

    def action_acknowledge(self):
        self.write({"state": "acknowledged"})

    def action_resolve(self):
        self.write({"state": "resolved"})

    def action_reopen(self):
        self.write({"state": "new"})

    @api.model
    def action_scan_inventory_alerts(self):
        self._scan_low_stock_alerts()
        self._scan_expiry_alerts()
        return True

    @api.model
    def _scan_low_stock_alerts(self):
        products = self.env["product.product"].search(
            [
                "|",
                ("product_tmpl_id.tijara_min_stock_alert", ">", 0),
                ("product_tmpl_id.tijara_inventory_critical_qty", ">", 0),
            ]
        )
        for product in products:
            template = product.product_tmpl_id
            warning_threshold = template.tijara_min_stock_alert
            critical_threshold = template.tijara_inventory_critical_qty
            quantity = product.qty_available

            if critical_threshold and quantity <= critical_threshold:
                self._upsert_alert(
                    alert_type="critical_stock",
                    product=product,
                    quantity=quantity,
                    threshold=critical_threshold,
                    severity="critical",
                    name=f"Critical stock: {product.display_name}",
                    notes="On-hand stock is at or below the critical stock quantity.",
                )
            elif warning_threshold and quantity <= warning_threshold:
                self._upsert_alert(
                    alert_type="low_stock",
                    product=product,
                    quantity=quantity,
                    threshold=warning_threshold,
                    severity="warning",
                    name=f"Low stock: {product.display_name}",
                    notes="On-hand stock is at or below the minimum stock alert quantity.",
                )

    @api.model
    def _scan_expiry_alerts(self):
        if "expiration_date" not in self.env["stock.lot"]._fields:
            return

        max_days = 30
        configured_days = self.env["product.template"].search_read(
            [("tijara_expiry_alert_days", ">", 0)],
            ["tijara_expiry_alert_days"],
            limit=200,
        )
        if configured_days:
            max_days = max(
                max_days,
                max(item["tijara_expiry_alert_days"] for item in configured_days),
            )

        now = fields.Datetime.now()
        lots = self.env["stock.lot"].search(
            [
                ("expiration_date", "!=", False),
                ("expiration_date", "<=", now + timedelta(days=max_days)),
            ]
        )
        for lot in lots:
            product = lot.product_id
            if not product:
                continue
            template = product.product_tmpl_id
            alert_days = template.tijara_expiry_alert_days or 30
            expiry_date = fields.Datetime.to_datetime(lot.expiration_date)
            if expiry_date and expiry_date <= now + timedelta(days=alert_days):
                days_left = (expiry_date.date() - now.date()).days
                severity = "critical" if days_left <= 7 else "warning"
                quantity = getattr(lot, "product_qty", 0.0)
                self._upsert_alert(
                    alert_type="expiry",
                    product=product,
                    lot=lot,
                    quantity=quantity,
                    threshold=alert_days,
                    expiry_date=expiry_date,
                    severity=severity,
                    name=f"Expiry alert: {product.display_name}",
                    notes=f"Lot {lot.name} expires in {days_left} day(s).",
                )

    @api.model
    def _upsert_alert(
        self,
        alert_type,
        product,
        quantity,
        threshold,
        severity,
        name,
        notes,
        lot=None,
        location=None,
        position=None,
        expiry_date=False,
    ):
        domain = [
            ("alert_type", "=", alert_type),
            ("product_id", "=", product.id),
            ("state", "in", ["new", "acknowledged"]),
        ]
        if lot:
            domain.append(("lot_id", "=", lot.id))
        if location:
            domain.append(("location_id", "=", location.id))
        if position:
            domain.append(("position_id", "=", position.id))

        values = {
            "name": name,
            "severity": severity,
            "product_id": product.id,
            "lot_id": lot.id if lot else False,
            "location_id": location.id if location else False,
            "position_id": position.id if position else False,
            "quantity": quantity,
            "threshold": threshold,
            "expiry_date": expiry_date,
            "last_seen_date": fields.Datetime.now(),
            "company_id": product.company_id.id or self.env.company.id,
            "notes": notes,
        }
        alert = self.search(domain, limit=1)
        if alert:
            alert.write(values)
        else:
            values.update({"alert_type": alert_type, "state": "new"})
            self.create(values)
