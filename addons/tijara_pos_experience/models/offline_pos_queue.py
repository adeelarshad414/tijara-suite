import hashlib
import json
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TijaraOfflinePosQueue(models.Model):
    _name = "tijara.offline.pos.queue"
    _description = "Tijara Offline POS Queue"
    _order = "queued_at desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    pos_config_id = fields.Many2one("pos.config", string="POS Register")
    source_app = fields.Selection(
        [
            ("pos_frontend", "POS Frontend"),
            ("kiosk", "Kiosk"),
            ("mobile", "Mobile POS"),
            ("manual", "Manual Import"),
        ],
        default="pos_frontend",
        required=True,
    )
    source_device_id = fields.Char(required=True)
    source_order_uid = fields.Char(required=True)
    order_reference = fields.Char(copy=False)
    payment_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("paid", "Paid"),
            ("failed", "Failed"),
        ],
        default="paid",
        required=True,
        copy=False,
    )
    amount_total = fields.Monetary(currency_field="currency_id", copy=False)
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )
    payload_json = fields.Text(required=True)
    payload_hash = fields.Char(required=True, copy=False, index=True)
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("validated", "Validated"),
            ("replayed", "Replayed"),
            ("conflict", "Conflict"),
            ("failed", "Failed"),
            ("duplicate", "Duplicate"),
            ("merged", "Merged"),
            ("cancelled", "Cancelled"),
        ],
        default="queued",
        required=True,
    )
    queued_at = fields.Datetime(default=fields.Datetime.now, required=True)
    offline_captured_at = fields.Datetime(copy=False)
    validated_at = fields.Datetime(copy=False)
    replay_attempts = fields.Integer(default=0, copy=False)
    last_replay_at = fields.Datetime(copy=False)
    replayed_at = fields.Datetime(copy=False)
    replayed_pos_order_id = fields.Many2one("pos.order", string="Replayed POS Order", copy=False)
    error_message = fields.Text(copy=False)
    payload_line_count = fields.Integer(compute="_compute_payload_audit", store=True)
    payload_payment_count = fields.Integer(compute="_compute_payload_audit", store=True)
    payload_total_delta = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_payload_audit",
        store=True,
    )
    replay_latency_minutes = fields.Float(compute="_compute_replay_latency", store=True)
    duplicate_of_queue_id = fields.Many2one(
        "tijara.offline.pos.queue",
        string="Duplicate Of",
        copy=False,
    )
    merged_into_queue_id = fields.Many2one(
        "tijara.offline.pos.queue",
        string="Merged Into",
        copy=False,
    )
    review_action = fields.Selection(
        [
            ("retry", "Retry"),
            ("cancel", "Cancel"),
            ("duplicate", "Mark Duplicate"),
            ("merge", "Merge"),
            ("manual_replay", "Manual Replay"),
            ("fail", "Fail"),
        ],
        copy=False,
    )
    review_note = fields.Text(copy=False)
    reviewed_by_id = fields.Many2one("res.users", string="Reviewed By", copy=False)
    reviewed_at = fields.Datetime(copy=False)

    @api.depends("payload_json", "amount_total")
    def _compute_payload_audit(self):
        for record in self:
            line_count = 0
            payment_count = 0
            line_total = 0.0
            try:
                payload = json.loads(record.payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                lines = payload.get("lines") if isinstance(payload.get("lines"), list) else []
                payments = (
                    payload.get("payments") if isinstance(payload.get("payments"), list) else []
                )
                line_count = len(lines)
                payment_count = len(payments)
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    quantity = record._payload_float(line.get("qty", line.get("quantity")))
                    price_unit = record._payload_float(line.get("price_unit"))
                    discount = min(max(record._payload_float(line.get("discount")), 0.0), 100.0)
                    line_total += quantity * price_unit * (1.0 - discount / 100.0)
            delta = (record.amount_total or 0.0) - line_total
            if record.currency_id:
                delta = record.currency_id.round(delta)
            record.payload_line_count = line_count
            record.payload_payment_count = payment_count
            record.payload_total_delta = delta

    @api.depends("queued_at", "last_replay_at", "replayed_at")
    def _compute_replay_latency(self):
        for record in self:
            end = record.replayed_at or record.last_replay_at
            if record.queued_at and end:
                delta = fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(record.queued_at)
                record.replay_latency_minutes = max(delta.total_seconds() / 60.0, 0.0)
            else:
                record.replay_latency_minutes = 0.0

    @api.model
    def _hash_payload(self, payload_json):
        normalized = json.dumps(
            json.loads(payload_json or "{}"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("payload_hash"):
                vals["payload_hash"] = self._hash_payload(vals.get("payload_json") or "{}")
        records = super().create(vals_list)
        for record in records:
            if record.name == "New":
                record.name = "OFFPOS-%05d" % record.id
        return records

    def _payload_dict(self):
        self.ensure_one()
        try:
            payload = json.loads(self.payload_json or "{}")
        except json.JSONDecodeError as error:
            raise UserError(_("Offline POS payload is not valid JSON: %s") % error) from error
        if not isinstance(payload, dict):
            raise UserError(_("Offline POS payload must be a JSON object."))
        return payload

    @api.model
    def _json_payload(self, payload):
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @api.model
    def _payload_float(self, value, default=0.0):
        try:
            return float(value if value not in (None, "") else default)
        except (TypeError, ValueError):
            return default

    @api.model
    def _payload_datetime(self, value):
        if not value:
            return False
        try:
            return fields.Datetime.to_datetime(value)
        except Exception:
            return fields.Datetime.now()

    @api.model
    def _capture_values(self, payload):
        if not isinstance(payload, dict):
            raise UserError(_("Offline POS payload must be a JSON object."))
        config = self.env["pos.config"].sudo().browse(int(payload.get("pos_config_id") or 0)).exists()
        if not config:
            raise UserError(_("Offline POS payload must include a valid POS register."))
        source_device_id = (payload.get("source_device_id") or "").strip()
        source_order_uid = (payload.get("source_order_uid") or payload.get("uid") or "").strip()
        if not source_device_id:
            raise UserError(_("Offline POS payload must include a source device id."))
        if not source_order_uid:
            raise UserError(_("Offline POS payload must include a source order uid."))
        totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
        source_app = payload.get("source_app") or "pos_frontend"
        if source_app not in {"pos_frontend", "kiosk", "mobile", "manual"}:
            source_app = "manual"
        payment_status = payload.get("payment_status") or "paid"
        if payment_status not in {"pending", "authorized", "paid", "failed"}:
            payment_status = "paid"
        amount_total = self._payload_float(
            payload.get("amount_total", totals.get("amount_total", totals.get("total")))
        )
        payload_json = self._json_payload(payload)
        return {
            "company_id": config.company_id.id,
            "pos_config_id": config.id,
            "source_app": source_app,
            "source_device_id": source_device_id,
            "source_order_uid": source_order_uid,
            "order_reference": (payload.get("order_reference") or payload.get("name") or "").strip(),
            "payment_status": payment_status,
            "amount_total": amount_total,
            "payload_json": payload_json,
            "payload_hash": self._hash_payload(payload_json),
            "offline_captured_at": self._payload_datetime(payload.get("captured_at"))
            or fields.Datetime.now(),
            "queued_at": fields.Datetime.now(),
            "error_message": False,
        }

    def _capture_response(self, status="ok"):
        self.ensure_one()
        return {
            "status": status,
            "queue_id": self.id,
            "queue_name": self.name,
            "queue_state": self.state,
            "pos_order_id": self.replayed_pos_order_id.id or False,
            "pos_order_name": self.replayed_pos_order_id.name or "",
            "error": self.error_message or "",
        }

    def _review_write(self, action, extra_values=None):
        values = {
            "review_action": action,
            "reviewed_by_id": self.env.user.id,
            "reviewed_at": fields.Datetime.now(),
        }
        values.update(extra_values or {})
        self.write(values)

    def _find_duplicate_queue(self):
        self.ensure_one()
        domain = [
            ("id", "!=", self.id),
            ("company_id", "=", self.company_id.id),
            ("state", "in", ["validated", "replayed", "conflict", "duplicate", "merged"]),
        ]
        if self.source_device_id and self.source_order_uid:
            duplicate = self.search(
                domain
                + [
                    ("source_device_id", "=", self.source_device_id),
                    ("source_order_uid", "=", self.source_order_uid),
                ],
                order="replayed_at desc, validated_at desc, id",
                limit=1,
            )
            if duplicate:
                return duplicate
        if self.payload_hash:
            return self.search(
                domain + [("payload_hash", "=", self.payload_hash)],
                order="replayed_at desc, validated_at desc, id",
                limit=1,
            )
        return self.browse()

    @api.model
    def tijara_capture_from_browser(self, payload, replay=True):
        values = self._capture_values(payload)
        if replay and values.get("pos_config_id"):
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [19062026, values["pos_config_id"]],
            )
        queue = self.sudo().search(
            [
                ("company_id", "=", values["company_id"]),
                ("source_device_id", "=", values["source_device_id"]),
                ("source_order_uid", "=", values["source_order_uid"]),
            ],
            limit=1,
        )
        if queue and queue.state == "replayed":
            return queue._capture_response(status="duplicate")
        if queue:
            values["state"] = "queued"
            queue.write(values)
        else:
            queue = self.sudo().create(values)
        queue.action_validate_payload()
        if replay and queue.state == "validated":
            queue.action_replay_to_pos()
        return queue._capture_response()

    def action_validate_payload(self):
        for record in self:
            payload = record._payload_dict()
            if not payload.get("lines") or not isinstance(payload.get("lines"), list):
                record.write(
                    {
                        "state": "failed",
                        "error_message": _("Offline POS payload must include order lines."),
                    }
                )
                continue
            duplicate = self.search(
                [
                    ("id", "!=", record.id),
                    ("company_id", "=", record.company_id.id),
                    ("source_device_id", "=", record.source_device_id),
                    ("payload_hash", "=", record.payload_hash),
                    ("state", "in", ["validated", "replayed", "conflict"]),
                ],
                limit=1,
            )
            record.write(
                {
                    "state": "conflict" if duplicate else "validated",
                    "validated_at": fields.Datetime.now(),
                    "duplicate_of_queue_id": duplicate.id if duplicate else False,
                    "error_message": _("Duplicate offline payload detected: %s") % duplicate.name
                    if duplicate
                    else False,
                }
            )

    def _offline_pos_session(self):
        self.ensure_one()
        config = self.pos_config_id
        if not config:
            raise UserError(_("Offline POS queue has no POS register."))
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

    def _offline_partner(self, payload):
        self.ensure_one()
        partner_id = int(payload.get("partner_id") or 0)
        partner = self.env["res.partner"].sudo().browse(partner_id).exists()
        if partner:
            return partner
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
        name = (payload.get("customer_name") or customer.get("name") or "").strip()
        mobile = (payload.get("customer_mobile") or customer.get("mobile") or customer.get("phone") or "").strip()
        email = (payload.get("customer_email") or customer.get("email") or "").strip()
        if not (name or mobile or email):
            return self.env["res.partner"]
        partner_fields = self.env["res.partner"]._fields
        domain = []
        if mobile:
            if "mobile" in partner_fields:
                domain = ["|", ("mobile", "=", mobile), ("phone", "=", mobile)]
            else:
                domain = [("phone", "=", mobile)]
        elif email:
            domain = [("email", "=", email)]
        partner = self.env["res.partner"].sudo().search(domain, limit=1) if domain else False
        if not partner:
            values = {
                "name": name or mobile or email,
                "phone": mobile or False,
                "email": email or False,
                "company_id": False,
            }
            if "mobile" in partner_fields:
                values["mobile"] = mobile or False
            partner = self.env["res.partner"].sudo().create(values)
        return partner

    def _offline_payment_method(self, payment_payload=None):
        self.ensure_one()
        payment_payload = payment_payload or {}
        config_methods = self.pos_config_id.payment_method_ids
        method = self.env["pos.payment.method"]
        method_id = int(payment_payload.get("payment_method_id") or 0)
        if method_id:
            method = config_methods.filtered(lambda candidate: candidate.id == method_id)[:1]
        method_name = (payment_payload.get("payment_method_name") or "").strip().lower()
        if not method and method_name:
            method = config_methods.filtered(
                lambda candidate: method_name in (candidate.name or "").strip().lower()
            )[:1]
        if not method:
            method = config_methods.filtered(lambda candidate: candidate.is_cash_count or candidate.type == "cash")[:1]
        return method or config_methods[:1]

    def _prepare_replay_lines(self, payload, partner):
        self.ensure_one()
        currency = self.currency_id
        amount_tax = 0.0
        amount_total = 0.0
        commands = []
        for index, line in enumerate(payload.get("lines") or [], start=1):
            product = self.env["product.product"].sudo().browse(
                int(line.get("product_id") or 0)
            ).exists()
            if not product:
                raise UserError(_("Offline POS line %s has no valid product.") % index)
            quantity = self._payload_float(line.get("qty", line.get("quantity")))
            if quantity <= 0:
                raise UserError(_("Offline POS line %s has an invalid quantity.") % index)
            price_unit = self._payload_float(line.get("price_unit"))
            discount = self._payload_float(line.get("discount"))
            taxes = product.taxes_id.filtered(
                lambda tax: not tax.company_id or tax.company_id == self.company_id
            )
            discounted_unit = price_unit * (1.0 - min(max(discount, 0.0), 100.0) / 100.0)
            tax_values = taxes.compute_all(
                discounted_unit,
                currency,
                quantity,
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
                        "full_product_name": line.get("name") or product.display_name,
                        "qty": quantity,
                        "price_unit": price_unit,
                        "discount": discount,
                        "tax_ids": [(6, 0, taxes.ids)],
                        "price_subtotal": currency.round(subtotal) if currency else subtotal,
                        "price_subtotal_incl": currency.round(subtotal_incl)
                        if currency
                        else subtotal_incl,
                    },
                )
            )
        if not commands:
            raise UserError(_("Offline POS replay needs at least one order line."))
        if currency:
            amount_tax = currency.round(amount_tax)
            amount_total = currency.round(amount_total)
        return commands, amount_tax, amount_total

    def _prepare_replay_payments(self, payload, amount_total):
        self.ensure_one()
        payments = payload.get("payments") if isinstance(payload.get("payments"), list) else []
        if not payments and self.payment_status in ("paid", "authorized"):
            payments = [
                {
                    "amount": payload.get("amount_paid") or amount_total,
                    "payment_method_id": payload.get("payment_method_id"),
                    "payment_method_name": payload.get("payment_method_name"),
                    "payment_reference": payload.get("payment_reference"),
                    "payment_status": self.payment_status,
                }
            ]
        return payments

    def _create_replayed_pos_order(self):
        self.ensure_one()
        if self.pos_config_id:
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [19062026, self.pos_config_id.id],
            )
        duplicate = self.search(
            [
                ("id", "!=", self.id),
                ("company_id", "=", self.company_id.id),
                ("source_device_id", "=", self.source_device_id),
                ("source_order_uid", "=", self.source_order_uid),
                ("state", "=", "replayed"),
            ],
            limit=1,
        )
        if duplicate:
            self.write(
                {
                    "state": "conflict",
                    "duplicate_of_queue_id": duplicate.id,
                    "error_message": _("Offline order was already replayed by %s.") % duplicate.name,
                }
            )
            return False
        payload = self._payload_dict()
        session = self._offline_pos_session()
        config = session.config_id
        partner = self._offline_partner(payload)
        lines, amount_tax, amount_total = self._prepare_replay_lines(payload, partner)
        pos_reference, tracking_number = config._get_next_order_refs("O")
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
                "tijara_order_type": payload.get("order_type") or "takeaway",
                "tijara_audience": payload.get("audience") or "b2c",
                "tijara_pickup_code": payload.get("pickup_code") or False,
            }
        )
        amount_paid = 0.0
        for payment_payload in self._prepare_replay_payments(payload, amount_total):
            payment_method = self._offline_payment_method(payment_payload)
            if not payment_method:
                raise UserError(_("No POS payment method is available for offline replay."))
            amount = self._payload_float(payment_payload.get("amount"))
            if amount <= 0:
                continue
            pos_order.add_payment(
                {
                    "pos_order_id": pos_order.id,
                    "amount": amount,
                    "payment_method_id": payment_method.id,
                    "payment_date": fields.Datetime.now(),
                    "payment_ref_no": payment_payload.get("payment_reference") or False,
                    "transaction_id": payment_payload.get("transaction_id")
                    or payment_payload.get("payment_reference")
                    or False,
                    "payment_status": payment_payload.get("payment_status") or self.payment_status,
                }
            )
            amount_paid += amount
        if amount_paid and amount_paid + 0.00001 >= amount_total:
            pos_order.action_pos_order_paid()
            try:
                pos_order._create_order_picking()
            except Exception as error:
                self.error_message = _("POS order is paid; stock picking is pending: %s") % error
        return pos_order

    def action_replay_to_pos(self):
        for record in self:
            if record.state == "replayed":
                continue
            if record.state in ("queued", "failed"):
                record.action_validate_payload()
            if record.state != "validated":
                continue
            for attempt in range(6):
                try:
                    with self.env.cr.savepoint():
                        pos_order = record._create_replayed_pos_order()
                        if pos_order:
                            record.write(
                                {
                                    "state": "replayed",
                                    "replayed_at": fields.Datetime.now(),
                                    "last_replay_at": fields.Datetime.now(),
                                    "replay_attempts": record.replay_attempts + 1,
                                    "replayed_pos_order_id": pos_order.id,
                                    "error_message": record.error_message or False,
                                }
                            )
                    break
                except Exception as error:
                    message = str(error)
                    retryable = (
                        "could not obtain lock" in message.lower()
                        or "could not serialize access" in message.lower()
                    )
                    if retryable and attempt < 5:
                        time.sleep(0.25 * (attempt + 1))
                        continue
                    record.write(
                        {
                            "state": "failed",
                            "last_replay_at": fields.Datetime.now(),
                            "replay_attempts": record.replay_attempts + 1,
                            "error_message": message,
                        }
                    )
                    break

    @api.model
    def tijara_replay_pending(self, limit=20, source_device_id=False):
        domain = [("state", "in", ["queued", "validated", "failed"])]
        if source_device_id:
            domain.append(("source_device_id", "=", source_device_id))
        queues = self.sudo().search(domain, order="queued_at, id", limit=max(int(limit or 20), 1))
        queues.action_replay_to_pos()
        return {
            "status": "ok",
            "count": len(queues),
            "replayed": len(queues.filtered(lambda queue: queue.state == "replayed")),
            "failed": len(queues.filtered(lambda queue: queue.state == "failed")),
            "conflict": len(queues.filtered(lambda queue: queue.state == "conflict")),
            "items": [queue._capture_response() for queue in queues],
        }

    @api.model
    def _cron_replay_pending(self):
        self.tijara_replay_pending(limit=50)

    def action_mark_replayed(self):
        self._review_write(
            "manual_replay",
            {
                "state": "replayed",
                "replayed_at": fields.Datetime.now(),
                "error_message": False,
            },
        )

    def action_fail(self):
        self._review_write("fail", {"state": "failed"})

    def action_retry_replay(self):
        for record in self:
            record._review_write(
                "retry",
                {
                    "state": "queued" if record.state in ("failed", "cancelled") else record.state,
                    "error_message": False,
                },
            )
            record.action_replay_to_pos()

    def action_cancel(self):
        self._review_write(
            "cancel",
            {
                "state": "cancelled",
                "error_message": False,
            },
        )

    def action_mark_duplicate(self):
        for record in self:
            duplicate = record.duplicate_of_queue_id or record._find_duplicate_queue()
            if not duplicate:
                raise UserError(_("No matching offline order was found to mark as duplicate."))
            record._review_write(
                "duplicate",
                {
                    "state": "duplicate",
                    "duplicate_of_queue_id": duplicate.id,
                    "error_message": _("Marked as duplicate of %s.") % duplicate.name,
                },
            )

    def action_merge_duplicate(self):
        for record in self:
            target = record.merged_into_queue_id or record.duplicate_of_queue_id or record._find_duplicate_queue()
            if not target:
                raise UserError(_("No matching offline order was found to merge into."))
            record._review_write(
                "merge",
                {
                    "state": "merged",
                    "merged_into_queue_id": target.id,
                    "duplicate_of_queue_id": target.id,
                    "error_message": _("Merged into offline queue %s.") % target.name,
                },
            )
