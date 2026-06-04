from odoo import fields, models


class TijaraDisplayScreen(models.Model):
    _name = "tijara.display.screen"
    _description = "Tijara Display Screen"
    _order = "display_type, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    display_type = fields.Selection(
        [
            ("kiosk", "Self-Service Kiosk"),
            ("customer_display", "POS Customer Display"),
            ("menu_board", "Menu Board"),
            ("deals_board", "Deals Board"),
            ("queue_display", "Queue Display"),
            ("back_office", "Back Office Display"),
        ],
        required=True,
    )
    language_mode = fields.Selection(
        [("en", "English"), ("ur", "Urdu"), ("both", "English + Urdu")],
        default="en",
        required=True,
    )
    orientation = fields.Selection(
        [("landscape", "Landscape"), ("portrait", "Portrait")],
        default="landscape",
        required=True,
    )
    price_mode = fields.Selection(
        [("b2c", "B2C"), ("b2b", "B2B"), ("both", "B2C + B2B")],
        default="b2c",
        required=True,
    )
    url_slug = fields.Char(string="Screen URL Slug")
    refresh_seconds = fields.Integer(default=15)
    hardware_device_id = fields.Many2one(
        "tijara.hardware.device",
        string="Linked Hardware Device",
    )
    content_ids = fields.Many2many(
        "tijara.display.content",
        "tijara_display_screen_content_rel",
        "screen_id",
        "content_id",
        string="Content",
    )
    notes = fields.Text()

