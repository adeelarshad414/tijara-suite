from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TijaraKioskOrder(models.Model):
    _name = "tijara.kiosk.order"
    _description = "Tijara Kiosk Order"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    profile_id = fields.Many2one("tijara.kiosk.profile", required=True)
    screen_id = fields.Many2one(
        "tijara.display.screen",
        domain=[("display_type", "=", "kiosk")],
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    customer_name = fields.Char()
    customer_mobile = fields.Char()
    customer_email = fields.Char()
    partner_id = fields.Many2one("res.partner")
    order_type = fields.Selection(
        [
            ("dine_in", "Dine In"),
            ("takeaway", "Takeaway"),
            ("pickup", "Pickup"),
        ],
        default="takeaway",
        required=True,
    )
    audience = fields.Selection(
        [("b2c", "B2C"), ("b2b", "B2B")],
        default="b2c",
        required=True,
    )
    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
        ],
        default="cash",
        required=True,
    )
    payment_provider = fields.Selection(
        [
            ("manual", "Manual / Counter"),
            ("jazzcash", "JazzCash"),
            ("easypaisa", "Easypaisa"),
            ("stripe", "Stripe"),
            ("other", "Other"),
        ],
        default="manual",
    )
    payment_status = fields.Selection(
        [
            ("pay_at_counter", "Pay at Counter"),
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("paid", "Paid"),
            ("failed", "Failed"),
        ],
        default="pay_at_counter",
        required=True,
        copy=False,
    )
    payment_reference = fields.Char(copy=False)
    payment_terminal_id = fields.Char(string="Terminal ID", copy=False)
    pos_config_id = fields.Many2one("pos.config", string="POS Register", copy=False)
    pos_session_id = fields.Many2one("pos.session", string="POS Session", copy=False)
    pos_order_id = fields.Many2one("pos.order", string="POS Order", copy=False)
    pos_payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="POS Payment Method",
        copy=False,
    )
    pos_payment_id = fields.Many2one("pos.payment", string="POS Payment", copy=False)
    pos_synced_at = fields.Datetime(copy=False)
    pos_sync_error = fields.Text(copy=False)
    line_ids = fields.One2many(
        "tijara.kiosk.order.line",
        "order_id",
        string="Lines",
    )
    amount_total = fields.Monetary(
        compute="_compute_amount_total",
        currency_field="currency_id",
        store=True,
    )
    pickup_code = fields.Char(copy=False)
    queue_ticket_id = fields.Many2one("tijara.queue.ticket", copy=False)
    submitted_at = fields.Datetime()
    completed_at = fields.Datetime()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("preparing", "Preparing"),
            ("ready", "Ready"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for order in records:
            if order.name == "New":
                order.name = self.env["ir.sequence"].next_by_code("tijara.kiosk.order") or "New"
        return records

    @api.depends("line_ids.price_subtotal")
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped("price_subtotal"))

    def _ensure_pickup_code(self):
        for order in self:
            if not order.pickup_code:
                order.pickup_code = (order.name or "KIOSK").replace("/", "")[-6:]

    def _ensure_pos_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        if not (self.customer_name or self.customer_mobile or self.customer_email):
            return self.env["res.partner"]
        partner_fields = self.env["res.partner"]._fields
        domain = []
        if self.customer_mobile:
            if "mobile" in partner_fields:
                domain = [
                    "|",
                    ("mobile", "=", self.customer_mobile),
                    ("phone", "=", self.customer_mobile),
                ]
            else:
                domain = [("phone", "=", self.customer_mobile)]
        elif self.customer_email:
            domain = [("email", "=", self.customer_email)]
        partner = self.env["res.partner"].sudo().search(domain, limit=1) if domain else False
        if not partner:
            values = {
                "name": self.customer_name or self.customer_mobile or self.customer_email,
                "phone": self.customer_mobile or False,
                "email": self.customer_email or False,
                "company_id": False,
            }
            if "mobile" in partner_fields:
                values["mobile"] = self.customer_mobile or False
            partner = self.env["res.partner"].sudo().create(
                values
            )
        self.partner_id = partner.id
        return partner

    def _kiosk_pos_session(self):
        self.ensure_one()
        config = self.profile_id.pos_config_id
        if not config:
            raise UserError(_("Configure a POS register on the kiosk profile before POS sync."))
        session = self.env["pos.session"].sudo().search(
            [
                ("config_id", "=", config.id),
                ("state", "not in", ["closed", "closing_control"]),
            ],
            order="id desc",
            limit=1,
        )
        if not session:
            session = self.env["pos.session"].sudo().create({"config_id": config.id})
        return session

    def _kiosk_pos_payment_method(self, config):
        self.ensure_one()
        mapped_method = {
            "cash": self.profile_id.cash_payment_method_id,
            "card": self.profile_id.card_payment_method_id,
            "bank_transfer": self.profile_id.bank_payment_method_id,
        }.get(self.payment_method)
        if mapped_method:
            return mapped_method
        methods = config.payment_method_ids
        if self.payment_method == "cash":
            return methods.filtered(lambda method: method.is_cash_count or method.type == "cash")[:1]
        return methods.filtered(lambda method: method.type == "bank" or not method.is_cash_count)[:1]

    def _kiosk_should_record_payment(self):
        self.ensure_one()
        mode = self.profile_id.payment_capture_mode
        if mode == "pay_at_counter":
            return False
        if mode == "provider_webhook":
            return self.payment_status == "paid"
        if mode == "terminal_reference":
            return bool(self.payment_reference) and self.payment_status in ("authorized", "paid")
        return True

    def _prepare_pos_order_lines(self, partner):
        self.ensure_one()
        currency = self.currency_id
        amount_tax = 0.0
        amount_total = 0.0
        commands = []
        for index, line in enumerate(self.line_ids, start=1):
            product = line.product_id
            if not product:
                raise UserError(_("Every kiosk line must have a product before POS sync."))
            taxes = product.taxes_id.filtered(
                lambda tax: not tax.company_id or tax.company_id == self.company_id
            )
            tax_values = taxes.compute_all(
                line.price_unit,
                currency,
                line.quantity,
                product=product,
                partner=partner or False,
            )
            subtotal = tax_values["total_excluded"]
            subtotal_incl = tax_values["total_included"]
            amount_tax += subtotal_incl - subtotal
            amount_total += subtotal_incl
            commands.append(
                (
                    0,
                    0,
                    {
                        "name": "%s/%s" % (self.name, index),
                        "product_id": product.id,
                        "full_product_name": line.name,
                        "qty": line.quantity,
                        "price_unit": line.price_unit,
                        "discount": 0.0,
                        "tax_ids": [(6, 0, taxes.ids)],
                        "price_subtotal": currency.round(subtotal) if currency else subtotal,
                        "price_subtotal_incl": currency.round(subtotal_incl)
                        if currency
                        else subtotal_incl,
                    },
                )
            )
        if currency:
            amount_tax = currency.round(amount_tax)
            amount_total = currency.round(amount_total)
        return commands, amount_tax, amount_total

    def _create_linked_pos_order(self):
        self.ensure_one()
        if self.pos_order_id:
            return self.pos_order_id
        session = self._kiosk_pos_session()
        config = session.config_id
        partner = self._ensure_pos_partner()
        lines, amount_tax, amount_total = self._prepare_pos_order_lines(partner)
        pos_reference, tracking_number = config._get_next_order_refs("K")
        fiscal_position = (
            config.fiscal_position_id if "fiscal_position_id" in config._fields else False
        )
        pos_order = self.env["pos.order"].sudo().with_company(self.company_id).create(
            {
                "session_id": session.id,
                "company_id": self.company_id.id,
                "user_id": session.user_id.id or self.env.uid,
                "partner_id": partner.id if partner else False,
                "pricelist_id": config.pricelist_id.id if config.pricelist_id else False,
                "fiscal_position_id": fiscal_position.id if fiscal_position else False,
                "pos_reference": pos_reference,
                "tracking_number": tracking_number,
                "amount_tax": amount_tax,
                "amount_total": amount_total,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "lines": lines,
                "tijara_order_type": self.order_type,
                "tijara_audience": self.audience,
                "tijara_pickup_code": self.pickup_code or False,
                "tijara_queue_ticket_id": self.queue_ticket_id.id or False,
            }
        )
        payment_method = self._kiosk_pos_payment_method(config)
        payment = self.env["pos.payment"]
        record_payment = self._kiosk_should_record_payment()
        if record_payment:
            if not payment_method:
                raise UserError(_("No POS payment method is mapped for this kiosk payment."))
            pos_order.add_payment(
                {
                    "pos_order_id": pos_order.id,
                    "amount": amount_total,
                    "payment_method_id": payment_method.id,
                    "payment_date": fields.Datetime.now(),
                    "payment_ref_no": self.payment_reference or False,
                    "transaction_id": self.payment_reference or False,
                    "payment_status": self.payment_status,
                }
            )
            payment = pos_order.payment_ids.sorted("id")[-1:]
            pos_order.action_pos_order_paid()
            try:
                pos_order._create_order_picking()
            except Exception as error:
                self.pos_sync_error = _("POS order is paid; stock picking is pending: %s") % error
        self.write(
            {
                "pos_config_id": config.id,
                "pos_session_id": session.id,
                "pos_order_id": pos_order.id,
                "pos_payment_method_id": payment_method.id if payment_method else False,
                "pos_payment_id": payment.id if payment else False,
                "pos_synced_at": fields.Datetime.now(),
                "pos_sync_error": self.pos_sync_error or False,
                "payment_status": "paid"
                if record_payment and pos_order.state == "paid"
                else self.payment_status,
            }
        )
        return pos_order

    def action_sync_pos_order(self):
        for order in self:
            with self.env.cr.savepoint():
                order._create_linked_pos_order()

    def action_submit(self):
        for order in self:
            if not order.line_ids:
                raise UserError(_("A kiosk order needs at least one line."))
            if order.state != "draft":
                continue
            order._ensure_pickup_code()
            queue_ticket = False
            if (
                order.profile_id.auto_create_queue_ticket
                and order.company_id.tijara_has_saas_feature("queue_system")
            ):
                queue_ticket = self.env["tijara.queue.ticket"].sudo().create(
                    {
                        "source": "kiosk",
                        "order_type": order.order_type,
                        "audience": order.audience,
                        "pickup_code": order.pickup_code,
                        "customer_id": order.partner_id.id or False,
                        "company_id": order.company_id.id,
                        "notes": order.notes,
                    }
                )
                queue_ticket.action_assign_number()
            order.write(
                {
                    "state": "submitted",
                    "submitted_at": fields.Datetime.now(),
                    "queue_ticket_id": queue_ticket.id if queue_ticket else False,
                }
            )
            if order.profile_id.auto_create_pos_order:
                try:
                    with self.env.cr.savepoint():
                        order._create_linked_pos_order()
                except Exception as error:
                    order.write({"pos_sync_error": str(error)})

    def action_prepare(self):
        self.write({"state": "preparing"})
        self.mapped("queue_ticket_id").action_prepare()

    def action_ready(self):
        self.write({"state": "ready"})
        self.mapped("queue_ticket_id").action_ready()

    def action_complete(self):
        self.write({"state": "completed", "completed_at": fields.Datetime.now()})
        self.mapped("queue_ticket_id").action_complete()

    def action_cancel(self):
        self.write({"state": "cancelled"})
        self.mapped("queue_ticket_id").action_cancel()


class TijaraKioskOrderLine(models.Model):
    _name = "tijara.kiosk.order.line"
    _description = "Tijara Kiosk Order Line"
    _order = "order_id, sequence, id"

    order_id = fields.Many2one(
        "tijara.kiosk.order",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    display_content_id = fields.Many2one("tijara.display.content")
    product_id = fields.Many2one("product.product")
    name = fields.Char(required=True)
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(
        currency_field="currency_id",
        required=True,
    )
    price_subtotal = fields.Monetary(
        compute="_compute_price_subtotal",
        currency_field="currency_id",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="order_id.currency_id",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="order_id.company_id",
        store=True,
    )

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
