from odoo import fields, models


class TijaraQueueTicket(models.Model):
    _inherit = "tijara.queue.ticket"

    source = fields.Selection(
        selection_add=[("ecommerce", "Ecommerce")],
        ondelete={"ecommerce": "set default"},
    )
    sale_order_id = fields.Many2one("sale.order", string="Ecommerce Sale Order")
