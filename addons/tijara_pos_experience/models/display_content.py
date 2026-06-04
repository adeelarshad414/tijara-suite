from odoo import fields, models


class TijaraDisplayContent(models.Model):
    _name = "tijara.display.content"
    _description = "Tijara Display Content"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    content_type = fields.Selection(
        [
            ("menu_item", "Menu Item"),
            ("deal", "Deal"),
            ("promotion", "Promotion"),
            ("announcement", "Announcement"),
            ("product", "Product"),
            ("queue_message", "Queue Message"),
        ],
        required=True,
        default="product",
    )
    title_english = fields.Char()
    title_urdu = fields.Char()
    subtitle_english = fields.Char()
    subtitle_urdu = fields.Char()
    product_id = fields.Many2one("product.product")
    promotion_id = fields.Many2one("tijara.promotion")
    b2c_price = fields.Float(string="Display B2C Price")
    b2b_price = fields.Float(string="Display B2B Price")
    start_at = fields.Datetime()
    end_at = fields.Datetime()
    screen_ids = fields.Many2many(
        "tijara.display.screen",
        "tijara_display_screen_content_rel",
        "content_id",
        "screen_id",
        string="Screens",
    )

