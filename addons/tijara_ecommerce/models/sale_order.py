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
    tijara_delivery_address = fields.Text(string="Delivery Address", copy=False)
    tijara_queue_ticket_id = fields.Many2one("tijara.queue.ticket", string="Queue Ticket", copy=False)
    tijara_amount_service_charge = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_amount_delivery_charge = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_amount_payment_tax = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_estimated_gst = fields.Monetary(currency_field="currency_id", copy=False)
    tijara_loyalty_points_awarded = fields.Float(copy=False)
    tijara_ecommerce_payload = fields.Text(string="Online Payload Snapshot", copy=False)

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
