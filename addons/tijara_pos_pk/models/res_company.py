from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _load_pos_data_fields(self, config):
        field_names = super()._load_pos_data_fields(config)
        tijara_fields = [
            "tijara_ntn",
            "tijara_strn",
            "tijara_branch_code",
            "tijara_fbr_pos_id",
        ]
        return field_names + [field for field in tijara_fields if field not in field_names]
