from odoo import fields, models


class TijaraPromotion(models.Model):
    _name = "tijara.promotion"
    _description = "Tijara Promotion and Deal"
    _order = "start_at desc, sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    promotion_type = fields.Selection(
        [
            ("discount", "Discount"),
            ("bundle", "Bundle"),
            ("combo", "Combo"),
            ("buy_x_get_y", "Buy X Get Y"),
            ("happy_hour", "Happy Hour"),
            ("announcement", "Announcement"),
        ],
        default="discount",
        required=True,
    )
    applies_to = fields.Selection(
        [
            ("b2c", "B2C"),
            ("b2b", "B2B"),
            ("both", "B2C + B2B"),
        ],
        default="b2c",
        required=True,
    )
    discount_percent = fields.Float()
    fixed_price = fields.Float()
    start_at = fields.Datetime()
    end_at = fields.Datetime()
    product_ids = fields.Many2many(
        "product.product",
        "tijara_promotion_product_rel",
        "promotion_id",
        "product_id",
        string="Products",
    )
    title_english = fields.Char()
    title_urdu = fields.Char()
    display_description = fields.Text()
    show_on_kiosk = fields.Boolean(default=True)
    show_on_menu_board = fields.Boolean(default=True)
    show_on_deals_board = fields.Boolean(default=True)
    show_on_customer_display = fields.Boolean(default=False)

