from odoo import fields, models


class TijaraQueueTicket(models.Model):
    _name = "tijara.queue.ticket"
    _description = "Tijara Queue Ticket"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    queue_number = fields.Char(copy=False)
    source = fields.Selection(
        [("pos", "POS"), ("kiosk", "Kiosk"), ("manual", "Manual")],
        default="pos",
        required=True,
    )
    order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
            ("delivery", "Delivery"),
        ],
        default="takeaway",
        required=True,
    )
    audience = fields.Selection(
        [("b2c", "B2C"), ("b2b", "B2B")],
        default="b2c",
        required=True,
    )
    pos_order_id = fields.Many2one("pos.order", string="POS Order")
    customer_id = fields.Many2one("res.partner")
    pickup_code = fields.Char()
    promised_at = fields.Datetime()
    called_at = fields.Datetime()
    completed_at = fields.Datetime()
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("waiting", "Waiting"),
            ("preparing", "Preparing"),
            ("ready", "Ready"),
            ("called", "Called"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="waiting",
        required=True,
    )
    notes = fields.Text()

    def action_prepare(self):
        self.write({"state": "preparing"})

    def action_ready(self):
        self.write({"state": "ready"})

    def action_call(self):
        self.write({"state": "called", "called_at": fields.Datetime.now()})

    def action_complete(self):
        self.write({"state": "completed", "completed_at": fields.Datetime.now()})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_assign_number(self):
        for ticket in self:
            if ticket.name == "New":
                ticket.name = self.env["ir.sequence"].next_by_code(
                    "tijara.queue.ticket"
                ) or "New"
            if not ticket.queue_number:
                ticket.queue_number = ticket.name
