from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config):
        field_names = super()._load_pos_data_fields(config)
        tijara_fields = [
            "tijara_b2c_price",
            "tijara_b2b_price",
            "tijara_b2b_min_qty",
        ]
        return field_names + [field for field in tijara_fields if field not in field_names]
