from odoo import fields, models


class TijaraBakeryBatch(models.Model):
    _name = "tijara.bakery.batch"
    _description = "Tijara Bakery Production Batch"
    _order = "production_date desc, id desc"

    name = fields.Char(default="New", required=True)
    product_id = fields.Many2one("product.product", required=True)
    production_date = fields.Datetime(default=fields.Datetime.now, required=True)
    planned_qty = fields.Float(required=True, default=1.0)
    produced_qty = fields.Float(default=0.0)
    expiry_datetime = fields.Datetime()
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_production", "In Production"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    def action_start(self):
        self.write({"state": "in_production"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

