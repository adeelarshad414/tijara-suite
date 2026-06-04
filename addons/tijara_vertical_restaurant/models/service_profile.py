from odoo import fields, models


class TijaraRestaurantServiceProfile(models.Model):
    _name = "tijara.restaurant.service.profile"
    _description = "Tijara Restaurant Service Profile"
    _order = "company_id, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    allow_dine_in = fields.Boolean(default=True)
    allow_takeaway = fields.Boolean(default=True)
    allow_pickup = fields.Boolean(default=True)
    default_order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
        ],
        default="dine_in",
        required=True,
    )
    require_table_for_dine_in = fields.Boolean(default=True)
    require_mobile_for_pickup = fields.Boolean(default=True)
    print_kitchen_ticket_for_takeaway = fields.Boolean(default=True)
    print_kitchen_ticket_for_pickup = fields.Boolean(default=True)
    notes = fields.Text()
