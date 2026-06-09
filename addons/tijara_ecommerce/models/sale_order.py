import uuid

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    tijara_ecommerce_channel_id = fields.Many2one("tijara.ecommerce.channel", string="Tijara Ecommerce Channel")
    tijara_ecommerce_reference = fields.Char(string="Online Reference", copy=False)
    tijara_ecommerce_audience = fields.Selection(
        [("b2c", "B2C"), ("b2b", "B2B")],
        string="Online Audience",
        copy=False,
    )
    tijara_fulfillment_method = fields.Selection(
        [
            ("delivery", "Delivery"),
            ("pickup", "Pickup"),
            ("store_pickup", "Store Pickup"),
            ("courier", "Courier"),
            ("takeaway", "Takeaway"),
            ("dine_in", "Dine In"),
        ],
        string="Fulfillment",
        copy=False,
    )
    tijara_payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
            ("jazzcash", "JazzCash"),
            ("easypaisa", "Easypaisa"),
            ("stripe", "Stripe"),
            ("cod", "Cash on Delivery"),
        ],
        string="Tijara Payment Method",
        copy=False,
    )
    tijara_payment_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("cod", "Cash on Delivery"),
            ("pay_at_pickup", "Pay at Pickup"),
        ],
        default="pending",
        string="Tijara Payment Status",
        copy=False,
    )
    tijara_pickup_code = fields.Char(string="Pickup Code", copy=False)
    tijara_delivery_mobile = fields.Char(string="Delivery Mobile", copy=False)
    tijara_delivery_address = fields.Text(string="Tijara Delivery Address", copy=False)
    tijara_delivery_provider_id = fields.Many2one(
        "tijara.ecommerce.delivery.provider",
        string="Delivery Provider",
        copy=False,
    )
    tijara_delivery_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending Assignment"),
            ("assigned", "Assigned"),
            ("picked", "Picked"),
            ("out_for_delivery", "Out For Delivery"),
            ("delivered", "Delivered"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="not_required",
        string="Tijara Delivery Status",
        copy=False,
    )
    tijara_delivery_tracking_number = fields.Char(string="Delivery Tracking Number", copy=False)
    tijara_delivery_tracking_url = fields.Char(string="Provider Tracking URL", copy=False)
    tijara_delivery_provider_payload = fields.Text(string="Provider Payload Snapshot", copy=False)
    tijara_delivery_eta = fields.Datetime(string="Delivery ETA", copy=False)
    tijara_last_tracking_at = fields.Datetime(string="Last Tracking Update", copy=False)
    tijara_tracking_token = fields.Char(string="Customer Tracking Token", copy=False, readonly=True)
    tijara_tracking_url = fields.Char(string="Customer Tracking URL", copy=False, readonly=True)
    tijara_queue_ticket_id = fields.Many2one("tijara.queue.ticket", string="Queue Ticket", copy=False)
    tijara_amount_service_charge = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_amount_delivery_charge = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_amount_payment_tax = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_estimated_gst = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_loyalty_points_awarded = fields.Float(copy=False)
    tijara_ecommerce_payload = fields.Text(string="Online Payload Snapshot", copy=False)

    def _tijara_tracking_public_url(self):
        self.ensure_one()
        if not self.tijara_ecommerce_channel_id or not self.tijara_tracking_token:
            return ""
        return "/tijara/ecommerce/%s/track/%s" % (
            self.tijara_ecommerce_channel_id.url_slug,
            self.tijara_tracking_token,
        )

    def action_tijara_generate_tracking_token(self):
        for order in self:
            if not order.tijara_ecommerce_channel_id:
                continue
            if not order.tijara_tracking_token:
                order.tijara_tracking_token = uuid.uuid4().hex
            order.tijara_tracking_url = order._tijara_tracking_public_url()
        return True

    def action_tijara_prepare_delivery(self):
        for order in self:
            if not order.tijara_ecommerce_channel_id:
                continue
            order.action_tijara_generate_tracking_token()
            provider = order.tijara_delivery_provider_id or order.tijara_ecommerce_channel_id.default_delivery_provider_id
            if not provider and order.tijara_ecommerce_channel_id.delivery_provider_ids:
                provider = order.tijara_ecommerce_channel_id.delivery_provider_ids.filtered("auto_assign")[:1]
            if provider and order.tijara_fulfillment_method in {"delivery", "courier"}:
                provider.tijara_prepare_shipment(order)
            elif order.tijara_fulfillment_method in {"delivery", "courier"}:
                order.tijara_delivery_status = "pending"
            else:
                order.tijara_delivery_status = "not_required"
        return True

    def action_tijara_mark_delivery_picked(self):
        self.write({"tijara_delivery_status": "picked", "tijara_last_tracking_at": fields.Datetime.now()})
        return True

    def action_tijara_mark_out_for_delivery(self):
        self.write({"tijara_delivery_status": "out_for_delivery", "tijara_last_tracking_at": fields.Datetime.now()})
        return True

    def action_tijara_mark_delivered(self):
        self.write({"tijara_delivery_status": "delivered", "tijara_last_tracking_at": fields.Datetime.now()})
        return True

    def _tijara_ecommerce_tracking_payload(self):
        self.ensure_one()
        queue = self.tijara_queue_ticket_id
        provider = self.tijara_delivery_provider_id
        order_lines = [
            {
                "product": line.product_id.display_name,
                "quantity": line.product_uom_qty,
                "subtotal": line.price_subtotal,
            }
            for line in self.order_line
            if line.product_id and line.product_uom_qty
        ]
        return {
            "status": "ok",
            "order": {
                "id": self.id,
                "name": self.name,
                "reference": self.client_order_ref or self.tijara_ecommerce_reference or "",
                "amount_total": self.amount_total,
                "currency": self.currency_id.name,
                "state": self.state,
                "fulfillment_method": self.tijara_fulfillment_method,
                "payment_method": self.tijara_payment_method,
                "payment_status": self.tijara_payment_status,
                "pickup_code": self.tijara_pickup_code or "",
                "customer_tracking_url": self.tijara_tracking_url or self._tijara_tracking_public_url(),
            },
            "queue": {
                "number": queue.queue_number or "",
                "state": queue.state or "",
                "order_type": queue.order_type or "",
            },
            "delivery": {
                "required": self.tijara_fulfillment_method in {"delivery", "courier"},
                "status": self.tijara_delivery_status,
                "provider": provider.name or "",
                "provider_type": provider.provider_type or "",
                "dry_run": bool(provider.dry_run) if provider else False,
                "tracking_number": self.tijara_delivery_tracking_number or "",
                "tracking_url": self.tijara_delivery_tracking_url or "",
                "eta": fields.Datetime.to_string(self.tijara_delivery_eta) if self.tijara_delivery_eta else "",
                "last_update": fields.Datetime.to_string(self.tijara_last_tracking_at) if self.tijara_last_tracking_at else "",
            },
            "lines": order_lines[:30],
            "next_step": self._tijara_tracking_next_step(),
        }

    def _tijara_tracking_next_step(self):
        self.ensure_one()
        if self.tijara_payment_status in {"pending", "authorized"}:
            return _("Payment is pending review.")
        if self.tijara_delivery_status in {"assigned", "picked", "out_for_delivery"}:
            return _("Delivery is in progress.")
        if self.tijara_delivery_status == "delivered":
            return _("Order delivered.")
        if self.tijara_queue_ticket_id and self.tijara_queue_ticket_id.state in {"waiting", "preparing", "ready"}:
            return _("Order is in the queue.")
        if self.state in {"sale", "done"}:
            return _("Order confirmed.")
        return _("Order received.")

    def action_tijara_mark_ecommerce_paid(self):
        for order in self:
            order.tijara_payment_status = "paid"
            partner = order.partner_id
            company = order.company_id
            if (
                order.tijara_ecommerce_channel_id
                and company.tijara_loyalty_enabled
                and partner
                and partner.tijara_loyalty_opt_in
                and not order.tijara_loyalty_points_awarded
            ):
                points = order.amount_total * company.tijara_loyalty_points_per_currency
                partner.sudo().write({"tijara_loyalty_points": partner.tijara_loyalty_points + points})
                order.tijara_loyalty_points_awarded = points
        return True

    def action_tijara_create_ecommerce_queue_ticket(self):
        for order in self:
            if not order.tijara_ecommerce_channel_id:
                continue
            if order.tijara_queue_ticket_id:
                continue
            if not order.company_id.tijara_has_saas_feature("queue_system"):
                continue
            queue_order_type = order.tijara_ecommerce_channel_id._fulfillment_to_queue_order_type(
                order.tijara_fulfillment_method
            )
            if not queue_order_type:
                continue
            ticket = self.env["tijara.queue.ticket"].sudo().create(
                {
                    "source": "ecommerce",
                    "sale_order_id": order.id,
                    "order_type": queue_order_type,
                    "audience": order.tijara_ecommerce_audience or "b2c",
                    "pickup_code": order.tijara_pickup_code or False,
                    "customer_id": order.partner_id.id if order.partner_id else False,
                    "company_id": order.company_id.id,
                    "notes": _("Online order %s") % order.name,
                }
            )
            ticket.action_assign_number()
            order.tijara_queue_ticket_id = ticket.id
        return True
