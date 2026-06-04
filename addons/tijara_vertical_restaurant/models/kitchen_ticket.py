from odoo import fields, models


class TijaraKitchenTicket(models.Model):
    _name = "tijara.kitchen.ticket"
    _description = "Tijara Kitchen Ticket"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True)
    table_id = fields.Many2one("tijara.restaurant.table")
    pos_order_id = fields.Many2one("pos.order")
    order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
        ],
        default="dine_in",
        required=True,
    )
    pickup_code = fields.Char()
    promised_at = fields.Datetime()
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent to Kitchen"),
            ("preparing", "Preparing"),
            ("ready", "Ready"),
            ("served", "Served"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    def action_send(self):
        self.write({"state": "sent"})

    def action_prepare(self):
        self.write({"state": "preparing"})

    def action_ready(self):
        self.write({"state": "ready"})

    def action_served(self):
        self.write({"state": "served"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
