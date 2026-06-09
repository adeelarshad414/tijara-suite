from odoo import fields, models


class TijaraKioskProfile(models.Model):
    _name = "tijara.kiosk.profile"
    _description = "Tijara Kiosk Profile"
    _order = "company_id, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    screen_id = fields.Many2one(
        "tijara.display.screen",
        domain=[("display_type", "=", "kiosk")],
    )
    default_order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
        ],
        default="takeaway",
        required=True,
    )
    allow_dine_in = fields.Boolean(default=True)
    allow_takeaway = fields.Boolean(default=True)
    allow_pickup = fields.Boolean(default=True)
    allow_delivery = fields.Boolean(default=True)
    allow_b2c = fields.Boolean(string="Allow B2C", default=True)
    allow_b2b = fields.Boolean(string="Allow B2B")
    require_customer_for_b2b = fields.Boolean(default=True)
    require_mobile_for_pickup = fields.Boolean(default=True)
    allow_cash = fields.Boolean(default=True)
    allow_card = fields.Boolean(default=True)
    allow_bank_transfer = fields.Boolean(default=False)
    auto_create_pos_order = fields.Boolean(
        string="Create POS Order",
        default=False,
        help="Create a linked Odoo POS order when the kiosk checkout is submitted.",
    )
    pos_config_id = fields.Many2one(
        "pos.config",
        string="POS Register",
        domain="[('company_id', '=', company_id)]",
        help="Open register/session used for kiosk-created POS orders.",
    )
    payment_capture_mode = fields.Selection(
        [
            ("pay_at_counter", "Pay at Counter"),
            ("record_paid", "Record Paid"),
            ("terminal_reference", "Terminal Reference"),
            ("provider_webhook", "Provider Webhook"),
        ],
        default="pay_at_counter",
        required=True,
        help="Controls how kiosk checkout records payment into the linked POS order.",
    )
    cash_payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="Cash Payment Method",
        domain="[('company_id', '=', company_id)]",
    )
    card_payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="Card/Terminal Payment Method",
        domain="[('company_id', '=', company_id)]",
    )
    bank_payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="Bank Transfer Payment Method",
        domain="[('company_id', '=', company_id)]",
    )
    auto_create_queue_ticket = fields.Boolean(
        string="Create Queue Ticket",
        default=True,
        help="Creates a queue ticket at kiosk checkout when the tenant has the queue feature.",
    )
    notes = fields.Text()
