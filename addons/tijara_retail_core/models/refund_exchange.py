from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class TijaraRefundReason(models.Model):
    _name = "tijara.refund.reason"
    _description = "Tijara Refund Reason"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    requires_manager_approval = fields.Boolean()


class TijaraExchangeRequest(models.Model):
    _name = "tijara.exchange.request"
    _description = "Tijara Refund and Exchange Request"
    _order = "request_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    request_date = fields.Datetime(default=fields.Datetime.now, required=True)
    customer_id = fields.Many2one("res.partner", string="Customer")
    original_order_ref = fields.Char(string="Original Receipt/Order")
    scanned_invoice_barcode = fields.Char(string="Invoice Barcode / QR")
    scanner_device_id = fields.Many2one(
        "tijara.hardware.device",
        domain="[('device_type', 'in', ('barcode_scanner', 'qr_scanner'))]",
    )
    matched_pos_order_id = fields.Many2one("pos.order", string="Matched POS Order")
    matched_invoice_id = fields.Many2one("account.move", string="Matched Invoice")
    scan_status = fields.Selection(
        [
            ("not_scanned", "Not Scanned"),
            ("found", "Found"),
            ("not_found", "Not Found"),
            ("ambiguous", "Ambiguous"),
        ],
        default="not_scanned",
        required=True,
    )
    scan_result_message = fields.Text()
    reason_id = fields.Many2one("tijara.refund.reason", required=True)
    line_ids = fields.One2many(
        "tijara.exchange.request.line",
        "request_id",
        string="Lines",
    )
    amount_total = fields.Float(compute="_compute_amount_total", store=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    requested_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True)
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("processed", "Processed"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    @api.depends("line_ids.return_subtotal")
    def _compute_amount_total(self):
        for request in self:
            request.amount_total = sum(request.line_ids.mapped("return_subtotal"))

    def action_submit(self):
        for request in self:
            if request.name == "New":
                request.name = self.env["ir.sequence"].next_by_code(
                    "tijara.exchange.request"
                ) or "New"
            request.state = (
                "pending_approval"
                if request.reason_id.requires_manager_approval
                else "approved"
            )

    def action_approve(self):
        for request in self:
            request.approved_by_id = self.env.user
            request.state = "approved"

    def action_process(self):
        self.write({"state": "processed"})

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_scan_invoice_barcode(self):
        for request in self:
            code = request._normalize_invoice_scan_code(request.scanned_invoice_barcode)
            if not code:
                raise UserError(_("Scan or enter an invoice barcode first."))

            order = request._find_pos_order_from_scan(code)
            invoice = request._find_invoice_from_scan(code) if not order else order.account_move

            if order:
                request._apply_pos_order_scan(order)
            elif invoice:
                request._apply_invoice_scan(invoice)
            else:
                request.write(
                    {
                        "scan_status": "not_found",
                        "scan_result_message": _(
                            "No POS order or customer invoice was found for %s."
                        )
                        % code,
                    }
                )

    def _normalize_invoice_scan_code(self, code):
        code = (code or "").strip()
        for prefix in ("TJINV:", "POS:", "INV:", "FBR:"):
            if code.upper().startswith(prefix):
                return code[len(prefix) :].strip()
        return code

    def _find_pos_order_from_scan(self, code):
        order_model = self.env["pos.order"].sudo()
        fields_to_search = [
            "tijara_invoice_barcode",
            "name",
            "pos_reference",
            "tijara_fbr_invoice_number",
        ]
        variants = [code, f"TJINV:{code}"]
        for field_name in fields_to_search:
            if field_name not in order_model._fields:
                continue
            for variant in variants:
                order = order_model.search(
                    [
                        (field_name, "=", variant),
                        ("company_id", "=", self.company_id.id),
                    ],
                    limit=1,
                )
                if order:
                    return order
        return order_model

    def _find_invoice_from_scan(self, code):
        move_model = self.env["account.move"].sudo()
        variants = [code, f"TJINV:{code}"]
        for field_name in ("tijara_invoice_barcode", "name", "payment_reference", "ref"):
            if field_name not in move_model._fields:
                continue
            for variant in variants:
                invoice = move_model.search(
                    [
                        (field_name, "=", variant),
                        ("company_id", "=", self.company_id.id),
                        ("move_type", "in", ["out_invoice", "out_refund"]),
                    ],
                    limit=1,
                )
                if invoice:
                    return invoice
        return move_model

    def _apply_pos_order_scan(self, order):
        self.ensure_one()
        discount_product = order.config_id.discount_product_id
        commands = [Command.clear()]
        for line in order.lines:
            if not line.product_id or (discount_product and line.product_id == discount_product):
                continue
            qty = abs(line.qty or 0.0)
            if not qty:
                continue
            price = abs(line.price_subtotal_incl / line.qty) if line.qty else line.price_unit
            commands.append(
                Command.create(
                    {
                        "product_id": line.product_id.id,
                        "return_qty": qty,
                        "return_price": abs(price),
                    }
                )
            )
        self.write(
            {
                "customer_id": order.partner_id.id or False,
                "original_order_ref": order.name,
                "matched_pos_order_id": order.id,
                "matched_invoice_id": order.account_move.id or False,
                "scan_status": "found",
                "scan_result_message": _("Matched POS order %s.") % order.name,
                "line_ids": commands,
            }
        )

    def _apply_invoice_scan(self, invoice):
        self.ensure_one()
        commands = [Command.clear()]
        for line in invoice.invoice_line_ids.filtered("product_id"):
            commands.append(
                Command.create(
                    {
                        "product_id": line.product_id.id,
                        "return_qty": abs(line.quantity or 0.0),
                        "return_price": abs(line.price_unit or 0.0),
                    }
                )
            )
        self.write(
            {
                "customer_id": invoice.partner_id.id or False,
                "original_order_ref": invoice.name,
                "matched_invoice_id": invoice.id,
                "matched_pos_order_id": False,
                "scan_status": "found",
                "scan_result_message": _("Matched customer invoice %s.") % invoice.name,
                "line_ids": commands,
            }
        )


class TijaraExchangeRequestLine(models.Model):
    _name = "tijara.exchange.request.line"
    _description = "Tijara Refund and Exchange Request Line"

    request_id = fields.Many2one(
        "tijara.exchange.request",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one("product.product", required=True)
    return_qty = fields.Float(default=1.0, required=True)
    return_price = fields.Float(required=True)
    return_subtotal = fields.Float(compute="_compute_return_subtotal", store=True)
    replacement_product_id = fields.Many2one("product.product")
    replacement_qty = fields.Float(default=0.0)
    note = fields.Char()

    @api.depends("return_qty", "return_price")
    def _compute_return_subtotal(self):
        for line in self:
            line.return_subtotal = line.return_qty * line.return_price
