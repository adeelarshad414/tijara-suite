from odoo import _, api, fields, models


class TijaraEcommerceCustomerAddress(models.Model):
    _name = "tijara.ecommerce.customer.address"
    _description = "Tijara Ecommerce Customer Saved Address"
    _order = "partner_id, default_delivery desc, name"

    name = fields.Char(required=True)
    partner_id = fields.Many2one("res.partner", required=True, index=True, ondelete="cascade")
    channel_id = fields.Many2one("tijara.ecommerce.channel", index=True, ondelete="set null")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    default_delivery = fields.Boolean()
    contact_name = fields.Char()
    mobile = fields.Char(required=True)
    email = fields.Char()
    street = fields.Char(required=True)
    street2 = fields.Char()
    city = fields.Char(default="Karachi")
    area = fields.Char()
    postal_code = fields.Char()
    delivery_notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_single_default()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "default_delivery" in vals and vals.get("default_delivery"):
            self._ensure_single_default()
        return result

    def _ensure_single_default(self):
        for address in self.filtered("default_delivery"):
            domain = [
                ("id", "!=", address.id),
                ("partner_id", "=", address.partner_id.id),
                ("default_delivery", "=", True),
            ]
            if address.channel_id:
                domain.append(("channel_id", "=", address.channel_id.id))
            self.search(domain).write({"default_delivery": False})

    def to_portal_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "channel_id": self.channel_id.id if self.channel_id else False,
            "default_delivery": bool(self.default_delivery),
            "contact_name": self.contact_name or self.partner_id.name or "",
            "mobile": self.mobile or "",
            "email": self.email or self.partner_id.email or "",
            "street": self.street or "",
            "street2": self.street2 or "",
            "city": self.city or "",
            "area": self.area or "",
            "postal_code": self.postal_code or "",
            "delivery_notes": self.delivery_notes or "",
            "display": ", ".join(
                part
                for part in [self.street, self.street2, self.area, self.city, self.postal_code]
                if part
            ),
        }

    @api.model
    def create_from_portal_payload(self, channel, partner, payload):
        values = {
            "name": (payload.get("name") or payload.get("label") or _("Delivery Address")).strip(),
            "partner_id": partner.id,
            "channel_id": channel.id,
            "company_id": channel.company_id.id,
            "default_delivery": bool(payload.get("default_delivery")),
            "contact_name": (payload.get("contact_name") or partner.name or "").strip(),
            "mobile": (payload.get("mobile") or getattr(partner, "mobile", "") or partner.phone or "").strip(),
            "email": (payload.get("email") or partner.email or "").strip(),
            "street": (payload.get("street") or payload.get("address") or "").strip(),
            "street2": (payload.get("street2") or "").strip(),
            "city": (payload.get("city") or "Karachi").strip(),
            "area": (payload.get("area") or "").strip(),
            "postal_code": (payload.get("postal_code") or "").strip(),
            "delivery_notes": payload.get("delivery_notes") or "",
        }
        if not values["mobile"]:
            raise ValueError(_("Mobile is required for saved delivery address."))
        if not values["street"]:
            raise ValueError(_("Street/address is required for saved delivery address."))
        address_id = int(payload.get("id") or 0)
        if address_id:
            address = self.search(
                [
                    ("id", "=", address_id),
                    ("partner_id", "=", partner.id),
                    ("channel_id", "=", channel.id),
                ],
                limit=1,
            )
            if address:
                address.write(values)
                return address
        return self.create(values)
