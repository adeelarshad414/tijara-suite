import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import get_delivery_adapter


class TijaraEcommerceDeliveryProvider(models.Model):
    _name = "tijara.ecommerce.delivery.provider"
    _description = "Tijara Ecommerce Delivery Provider"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True)
    provider_type = fields.Selection(
        [
            ("in_house", "In House Fleet"),
            ("courier", "Courier"),
            ("aggregator", "Aggregator"),
            ("third_party", "Third Party"),
            ("dummy", "Dummy / Assumption Mode"),
        ],
        default="in_house",
        required=True,
    )
    adapter_profile = fields.Selection(
        [
            ("in_house_rider", "In-House Rider"),
            ("tcs", "TCS Pakistan"),
            ("leopards", "Leopards Courier"),
            ("postex", "PostEx"),
            ("mnp", "M&P"),
            ("blue_ex", "BlueEx"),
            ("trax", "Trax"),
            ("rider", "Rider"),
            ("call_courier", "Call Courier"),
            ("manual", "Manual Provider"),
            ("dummy", "Dummy / Assumption"),
        ],
        default="manual",
        required=True,
        help="Open-source provider profile used to seed assumed local/staging fixtures. Replace with certified API details before production.",
    )
    service_level = fields.Selection(
        [
            ("standard", "Standard"),
            ("same_day", "Same Day"),
            ("express", "Express"),
            ("scheduled", "Scheduled"),
        ],
        default="standard",
        required=True,
    )
    dry_run = fields.Boolean(
        default=True,
        help="Keep enabled until a real courier/provider integration is certified.",
    )
    adapter_mode = fields.Selection(
        [
            ("dry_run", "Dry Run Adapter"),
            ("manual", "Manual Adapter"),
            ("http_json", "HTTP JSON Adapter"),
        ],
        default="dry_run",
        required=True,
    )
    auto_assign = fields.Boolean(default=True)
    supports_delivery = fields.Boolean(default=True)
    supports_courier = fields.Boolean(default=True)
    supports_cod = fields.Boolean(default=True)
    supports_cancel = fields.Boolean(default=True)
    supports_labels = fields.Boolean(default=True)
    supports_manifests = fields.Boolean(default=True)
    supports_webhooks = fields.Boolean(default=True)
    api_base_url = fields.Char()
    create_endpoint = fields.Char()
    cancel_endpoint = fields.Char()
    status_endpoint = fields.Char()
    label_endpoint = fields.Char()
    manifest_endpoint = fields.Char()
    tracking_url_template = fields.Char(
        help="Optional URL template. Use {tracking_number} where the provider tracking number should appear.",
    )
    label_format = fields.Selection(
        [
            ("pdf", "PDF"),
            ("zpl", "ZPL"),
            ("escpos", "ESC/POS"),
            ("json", "JSON"),
            ("url", "Provider URL"),
        ],
        default="pdf",
    )
    webhook_signature_mode = fields.Selection(
        [
            ("none", "None"),
            ("dry_run", "Dry Run Header"),
            ("hmac_sha256", "HMAC SHA256"),
        ],
        default="dry_run",
        required=True,
    )
    webhook_signature_header = fields.Char(default="X-Tijara-Delivery-Signature")
    webhook_reference_field = fields.Char(default="tracking_number")
    webhook_status_field = fields.Char(default="status")
    webhook_eta_field = fields.Char(default="eta")
    contact_phone = fields.Char()
    rider_name = fields.Char()
    rider_mobile = fields.Char()
    sla_hours = fields.Float(default=24.0)
    retry_initial_delay_minutes = fields.Integer(default=5)
    retry_backoff_multiplier = fields.Float(default=2.0)
    retry_max_attempts = fields.Integer(default=5)
    provider_fee_flat = fields.Monetary(currency_field="currency_id", default=0.0)
    cod_fee_percent = fields.Float(default=0.0)
    settlement_cycle = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("fortnightly", "Fortnightly"),
            ("monthly", "Monthly"),
            ("manual", "Manual"),
        ],
        default="weekly",
    )
    webhook_secret_ref = fields.Char(
        help="Secret-manager reference only. Do not store raw courier webhook secrets here.",
    )
    shipment_count = fields.Integer(compute="_compute_shipment_count")
    event_count = fields.Integer(compute="_compute_event_count")
    retry_count = fields.Integer(compute="_compute_retry_count")
    exception_count = fields.Integer(compute="_compute_exception_count")
    reconciliation_count = fields.Integer(compute="_compute_reconciliation_count")
    notes = fields.Text()

    @api.depends("company_id")
    def _compute_shipment_count(self):
        order_model = self.env["sale.order"].sudo()
        for provider in self:
            provider.shipment_count = order_model.search_count(
                [("tijara_delivery_provider_id", "=", provider.id)]
            )

    @api.depends("company_id")
    def _compute_event_count(self):
        event_model = self.env["tijara.ecommerce.delivery.event"].sudo()
        for provider in self:
            provider.event_count = event_model.search_count([("provider_id", "=", provider.id)])

    @api.depends("company_id")
    def _compute_retry_count(self):
        retry_model = self.env["tijara.ecommerce.delivery.retry"].sudo()
        for provider in self:
            provider.retry_count = retry_model.search_count([("provider_id", "=", provider.id)])

    @api.depends("company_id")
    def _compute_exception_count(self):
        exception_model = self.env["tijara.ecommerce.delivery.exception"].sudo()
        for provider in self:
            provider.exception_count = exception_model.search_count([("provider_id", "=", provider.id)])

    @api.depends("company_id")
    def _compute_reconciliation_count(self):
        reconciliation_model = self.env["tijara.ecommerce.delivery.reconciliation"].sudo()
        for provider in self:
            provider.reconciliation_count = reconciliation_model.search_count([("provider_id", "=", provider.id)])

    @api.constrains("code", "company_id")
    def _check_unique_code(self):
        for provider in self:
            domain = [
                ("id", "!=", provider.id),
                ("company_id", "=", provider.company_id.id),
                ("code", "=", provider.code),
            ]
            if provider.code and self.search_count(domain):
                raise ValidationError(_("Delivery provider code must be unique per company."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            profile_defaults = self._adapter_profile_defaults(vals.get("adapter_profile"))
            for key, value in profile_defaults.items():
                if key not in vals or vals.get(key) in (None, ""):
                    vals[key] = value
            vals["code"] = self._normalize_code(vals.get("code") or vals.get("name"))
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals:
            vals = dict(vals, code=self._normalize_code(vals.get("code")))
        return super().write(vals)

    @api.model
    def _normalize_code(self, value):
        value = re.sub(r"[^A-Za-z0-9]+", "-", value or "").strip("-").upper()
        return value or "DELIVERY"

    @api.model
    def _adapter_profile_defaults(self, profile):
        profiles = {
            "in_house_rider": {
                "provider_type": "in_house",
                "service_level": "same_day",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": True,
                "supports_cod": True,
                "supports_labels": True,
                "supports_manifests": True,
                "supports_webhooks": True,
                "sla_hours": 4.0,
                "retry_initial_delay_minutes": 3,
                "settlement_cycle": "daily",
            },
            "tcs": {
                "provider_type": "courier",
                "service_level": "standard",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/tcs/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 48.0,
                "provider_fee_flat": 180.0,
                "cod_fee_percent": 1.5,
                "settlement_cycle": "weekly",
            },
            "leopards": {
                "provider_type": "courier",
                "service_level": "standard",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/leopards/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 48.0,
                "provider_fee_flat": 170.0,
                "cod_fee_percent": 1.4,
                "settlement_cycle": "weekly",
            },
            "postex": {
                "provider_type": "aggregator",
                "service_level": "standard",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/postex/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 48.0,
                "provider_fee_flat": 160.0,
                "cod_fee_percent": 1.25,
                "settlement_cycle": "daily",
            },
            "mnp": {
                "provider_type": "courier",
                "service_level": "standard",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/mnp/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 72.0,
                "provider_fee_flat": 175.0,
                "cod_fee_percent": 1.5,
                "settlement_cycle": "weekly",
            },
            "blue_ex": {
                "provider_type": "courier",
                "service_level": "express",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/blueex/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 36.0,
                "provider_fee_flat": 190.0,
                "cod_fee_percent": 1.6,
                "settlement_cycle": "weekly",
            },
            "trax": {
                "provider_type": "courier",
                "service_level": "express",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/trax/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 36.0,
                "provider_fee_flat": 185.0,
                "cod_fee_percent": 1.45,
                "settlement_cycle": "weekly",
            },
            "rider": {
                "provider_type": "third_party",
                "service_level": "same_day",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/rider/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 24.0,
                "provider_fee_flat": 150.0,
                "cod_fee_percent": 1.3,
                "settlement_cycle": "daily",
            },
            "call_courier": {
                "provider_type": "courier",
                "service_level": "standard",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": False,
                "tracking_url_template": "https://tracking.example.test/call-courier/{tracking_number}",
                "label_format": "pdf",
                "sla_hours": 48.0,
                "provider_fee_flat": 175.0,
                "cod_fee_percent": 1.5,
                "settlement_cycle": "weekly",
            },
            "dummy": {
                "provider_type": "dummy",
                "service_level": "same_day",
                "adapter_mode": "dry_run",
                "dry_run": True,
                "auto_assign": True,
                "sla_hours": 4.0,
                "settlement_cycle": "manual",
            },
        }
        defaults = profiles.get(profile or "", {})
        common = {
            "supports_delivery": True,
            "supports_courier": True,
            "supports_cod": True,
            "supports_cancel": True,
            "supports_labels": True,
            "supports_manifests": True,
            "supports_webhooks": True,
            "webhook_signature_mode": "dry_run",
            "webhook_signature_header": "X-Tijara-Delivery-Signature",
            "webhook_reference_field": "tracking_number",
            "webhook_status_field": "status",
            "webhook_eta_field": "eta",
        }
        return dict(common, **defaults) if defaults else {}

    def action_apply_profile_defaults(self):
        for provider in self:
            defaults = provider._adapter_profile_defaults(provider.adapter_profile)
            if defaults:
                provider.write(defaults)
        return True

    def _tracking_number_for_order(self, order):
        self.ensure_one()
        raw_order = re.sub(r"[^A-Za-z0-9]+", "", order.name or str(order.id))[-10:]
        raw_order = raw_order or str(order.id)
        return "%s-%s" % (self.code, raw_order)

    def _tracking_url_for_number(self, tracking_number):
        self.ensure_one()
        template = self.tracking_url_template or ""
        if not template:
            return ""
        return template.replace("{tracking_number}", tracking_number or "")

    def action_open_shipments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Provider Shipments"),
            "res_model": "sale.order",
            "view_mode": "list,form,pivot,graph",
            "domain": [("tijara_delivery_provider_id", "=", self.id)],
            "context": {"search_default_tijara_ecommerce": 1},
        }

    def action_open_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Adapter Events"),
            "res_model": "tijara.ecommerce.delivery.event",
            "view_mode": "list,form,pivot,graph",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_open_retries(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Retry Queue"),
            "res_model": "tijara.ecommerce.delivery.retry",
            "view_mode": "list,form,pivot,graph",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_open_exceptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Exceptions"),
            "res_model": "tijara.ecommerce.delivery.exception",
            "view_mode": "list,form,pivot,graph",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_open_reconciliations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Reconciliations"),
            "res_model": "tijara.ecommerce.delivery.reconciliation",
            "view_mode": "list,form,pivot,graph",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_test_provider(self):
        self.ensure_one()
        message = _("Dry-run provider is ready for assumed local certification.")
        if not self.dry_run:
            message = _("Provider is configured for live mode; complete courier certification before production.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Delivery Provider Check"),
                "message": message,
                "type": "success" if self.dry_run else "warning",
                "sticky": False,
            },
        }

    def _require_live_endpoint(self, endpoint_field, operation):
        self.ensure_one()
        if self.dry_run or self.adapter_mode in {"dry_run", "manual"}:
            return
        if not self[endpoint_field]:
            raise UserError(
                _("%s requires %s for live HTTP JSON providers.")
                % (operation, endpoint_field.replace("_", " "))
            )

    def _delivery_event(
        self,
        order=False,
        event_type="shipment_create",
        direction="outbound",
        status="queued",
        payload=False,
        response=False,
        message="",
        signature_status="not_required",
        external_reference="",
        tracking_number="",
        manifest_reference="",
    ):
        self.ensure_one()
        event_model = self.env["tijara.ecommerce.delivery.event"].sudo()
        event = event_model.create(
            {
                "name": "%s/%s/%s" % (self.code, event_type, fields.Datetime.now()),
                "provider_id": self.id,
                "sale_order_id": order.id if order else False,
                "company_id": self.company_id.id,
                "direction": direction,
                "event_type": event_type,
                "status": status,
                "signature_status": signature_status,
                "external_reference": external_reference or "",
                "tracking_number": tracking_number or "",
                "manifest_reference": manifest_reference or "",
                "payload_json": event_model.payload_to_json(payload),
                "response_json": event_model.payload_to_json(response),
                "message": message or "",
            }
        )
        event.write_payload_hash()
        if order:
            order.tijara_delivery_last_event_id = event.id
        return event

    def _delivery_sla_deadline(self):
        self.ensure_one()
        return fields.Datetime.now() + timedelta(hours=self.sla_hours or 24.0)

    def _queue_retry_if_needed(self, operation, payload, order=False, event=False, endpoint_field=""):
        self.ensure_one()
        if self.dry_run or self.adapter_mode != "http_json":
            return self.env["tijara.ecommerce.delivery.retry"].browse()
        return self.env["tijara.ecommerce.delivery.retry"].sudo().create(
            {
                "provider_id": self.id,
                "sale_order_id": order.id if order else False,
                "company_id": self.company_id.id,
                "operation": operation,
                "state": "pending",
                "priority": 20 if operation == "shipment_create" else 10,
                "max_attempts": self.retry_max_attempts or 5,
                "next_attempt_at": fields.Datetime.now()
                + timedelta(minutes=max(self.retry_initial_delay_minutes or 5, 1)),
                "last_event_id": event.id if event else False,
                "api_base_url_snapshot": self.api_base_url or "",
                "endpoint_snapshot": self[endpoint_field] if endpoint_field else "",
                "payload_json": json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str),
                "notes": _("Created automatically from delivery adapter event %s.") % (event.name if event else ""),
            }
        )

    def _assumed_http_adapter_response(self, operation, payload, order=False):
        self.ensure_one()
        order = order or self.env["sale.order"].sudo().browse(payload.get("order_id")).exists()
        return self._profile_adapter().assumed_response(self, operation, payload, order=order)

    def _raise_delivery_exception(
        self,
        order,
        category="manual_review",
        message="",
        severity="warning",
        event=False,
        retry=False,
    ):
        self.ensure_one()
        return self.env["tijara.ecommerce.delivery.exception"].sudo().create_for_order(
            self,
            order,
            category=category,
            message=message,
            severity=severity,
            event=event,
            retry=retry,
            deadline=order.tijara_delivery_sla_deadline if order else False,
        )

    def _order_line_payload(self, order):
        return [
            {
                "sku": line.product_id.default_code or "",
                "name": line.product_id.display_name,
                "quantity": line.product_uom_qty,
                "subtotal": line.price_subtotal,
            }
            for line in order.order_line
            if line.product_id and line.product_uom_qty
        ]

    def _profile_adapter(self):
        self.ensure_one()
        return get_delivery_adapter(self.adapter_profile)

    def _shipment_payload(self, order):
        self.ensure_one()
        return self._profile_adapter().shipment_payload(self, order, self._order_line_payload(order))

    def _provider_reference_for_order(self, order):
        raw_order = re.sub(r"[^A-Za-z0-9]+", "", order.name or str(order.id))[-10:]
        raw_order = raw_order or str(order.id)
        return "%s-REF-%s" % (self.code, raw_order)

    def tijara_prepare_shipment(self, order):
        self.ensure_one()
        return self.tijara_create_shipment(order)

    def tijara_create_shipment(self, order):
        self.ensure_one()
        self._require_live_endpoint("create_endpoint", _("Shipment create"))
        tracking_number = order.tijara_delivery_tracking_number or self._tracking_number_for_order(order)
        tracking_url = order.tijara_delivery_tracking_url or self._tracking_url_for_number(tracking_number)
        external_reference = order.tijara_delivery_provider_reference or self._provider_reference_for_order(order)
        request_payload = self._shipment_payload(order)
        payload = {
            "provider": self.code,
            "provider_type": self.provider_type,
            "adapter_profile": self.adapter_profile,
            "adapter_mode": self.adapter_mode,
            "service_level": self.service_level,
            "dry_run": self.dry_run,
            "order_id": order.id,
            "order_name": order.name,
            "fulfillment_method": order.tijara_fulfillment_method,
            "external_reference": external_reference,
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
        }
        event = self._delivery_event(
            order=order,
            event_type="shipment_create",
            status="processed" if self.dry_run or self.adapter_mode != "http_json" else "queued",
            payload=request_payload,
            response=payload,
            external_reference=external_reference,
            tracking_number=tracking_number,
            message=_("Dry-run/manual shipment interface prepared.")
            if self.dry_run or self.adapter_mode != "http_json"
            else _("Live HTTP shipment request queued for provider adapter."),
        )
        self._queue_retry_if_needed(
            "shipment_create",
            request_payload,
            order=order,
            event=event,
            endpoint_field="create_endpoint",
        )
        order.write(
            {
                "tijara_delivery_provider_id": self.id,
                "tijara_delivery_status": "assigned",
                "tijara_delivery_adapter_state": "created",
                "tijara_delivery_provider_reference": external_reference,
                "tijara_delivery_tracking_number": tracking_number,
                "tijara_delivery_tracking_url": tracking_url,
                "tijara_delivery_provider_payload": json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
                "tijara_last_tracking_at": fields.Datetime.now(),
                "tijara_delivery_sla_deadline": self._delivery_sla_deadline(),
                "tijara_delivery_sla_state": "on_track",
                "tijara_delivery_last_event_id": event.id,
            }
        )
        return payload

    def tijara_cancel_shipment(self, order, reason=""):
        self.ensure_one()
        self._require_live_endpoint("cancel_endpoint", _("Shipment cancel"))
        payload = self._profile_adapter().cancel_payload(self, order, reason or _("Cancelled by operator"))
        event = self._delivery_event(
            order=order,
            event_type="shipment_cancel",
            status="processed" if self.dry_run or self.adapter_mode != "http_json" else "queued",
            payload=payload,
            response=dict(payload, cancelled=True),
            external_reference=payload["external_reference"],
            tracking_number=payload["tracking_number"],
            message=_("Shipment cancel interface processed."),
        )
        self._queue_retry_if_needed(
            "shipment_cancel",
            payload,
            order=order,
            event=event,
            endpoint_field="cancel_endpoint",
        )
        order.write(
            {
                "tijara_delivery_status": "cancelled",
                "tijara_delivery_adapter_state": "cancelled",
                "tijara_delivery_exception_reason": reason or _("Cancelled by operator"),
                "tijara_last_tracking_at": fields.Datetime.now(),
                "tijara_delivery_sla_state": "cancelled",
                "tijara_delivery_last_event_id": event.id,
            }
        )
        return payload

    def tijara_generate_label(self, order):
        self.ensure_one()
        if not self.supports_labels:
            raise UserError(_("This delivery provider does not support labels."))
        self._require_live_endpoint("label_endpoint", _("Label generation"))
        label_payload = self._profile_adapter().label_payload(self, order)
        event = self._delivery_event(
            order=order,
            event_type="label",
            status="processed" if self.dry_run or self.adapter_mode != "http_json" else "queued",
            payload=label_payload,
            response=label_payload,
            external_reference=order.tijara_delivery_provider_reference or "",
            tracking_number=order.tijara_delivery_tracking_number or "",
            message=_("Label interface generated."),
        )
        self._queue_retry_if_needed(
            "label",
            label_payload,
            order=order,
            event=event,
            endpoint_field="label_endpoint",
        )
        order.write(
            {
                "tijara_delivery_label_format": self.label_format,
                "tijara_delivery_label_payload": json.dumps(label_payload, ensure_ascii=False, sort_keys=True),
                "tijara_delivery_adapter_state": "label_ready",
                "tijara_delivery_last_event_id": event.id,
            }
        )
        return label_payload

    def tijara_create_manifest(self, orders):
        self.ensure_one()
        orders = orders.filtered(lambda order: order.tijara_delivery_provider_id == self)
        if not orders:
            raise UserError(_("Select ecommerce orders assigned to this provider."))
        if not self.supports_manifests:
            raise UserError(_("This delivery provider does not support manifests."))
        self._require_live_endpoint("manifest_endpoint", _("Manifest create"))
        manifest_reference = "%s-MAN-%s" % (
            self.code,
            datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        )
        payload = self._profile_adapter().manifest_payload(self, manifest_reference, orders)
        event = self._delivery_event(
            event_type="manifest",
            status="processed" if self.dry_run or self.adapter_mode != "http_json" else "queued",
            payload=payload,
            response=payload,
            manifest_reference=manifest_reference,
            message=_("Manifest interface generated."),
        )
        self._queue_retry_if_needed(
            "manifest",
            payload,
            event=event,
            endpoint_field="manifest_endpoint",
        )
        orders.write(
            {
                "tijara_delivery_manifest_reference": manifest_reference,
                "tijara_delivery_adapter_state": "manifested",
                "tijara_delivery_last_event_id": event.id,
            }
        )
        return payload

    def _webhook_secret_value(self):
        self.ensure_one()
        if not self.webhook_secret_ref:
            return ""
        parameter_key = "tijara.delivery.webhook.%s.secret" % self.code
        return self.env["ir.config_parameter"].sudo().get_param(parameter_key, default="") or ""

    def _webhook_signature_status(self, headers, payload=False, raw_body=""):
        self.ensure_one()
        if self.webhook_signature_mode == "none":
            return "not_required"
        signature = headers.get(self.webhook_signature_header or "") if headers else ""
        if not signature:
            return "missing"
        if self.webhook_signature_mode == "dry_run":
            return "valid" if signature in {"dry-run", "tijara-dry-run"} else "invalid"
        secret = self._webhook_secret_value()
        if not secret:
            return "missing"
        raw_payload = raw_body or json.dumps(
            payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
        expected = hmac.new(secret.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        provided = signature.strip()
        if provided.lower().startswith("sha256="):
            provided = provided.split("=", 1)[1].strip()
        return "valid" if hmac.compare_digest(provided, expected) else "invalid"

    def _delivery_status_from_provider(self, provider_status):
        status = str(provider_status or "").strip().lower().replace("-", "_").replace(" ", "_")
        return {
            "created": "assigned",
            "assigned": "assigned",
            "picked": "picked",
            "pickup": "picked",
            "out_for_delivery": "out_for_delivery",
            "out": "out_for_delivery",
            "delivered": "delivered",
            "complete": "delivered",
            "failed": "failed",
            "exception": "failed",
            "cancelled": "cancelled",
            "canceled": "cancelled",
        }.get(status, "assigned")

    def tijara_process_webhook(self, payload, headers=False, raw_body=""):
        self.ensure_one()
        if not self.supports_webhooks:
            raise UserError(_("This delivery provider does not accept webhooks."))
        if not isinstance(payload, dict):
            raise UserError(_("Delivery webhook payload must be a JSON object."))
        signature_status = self._webhook_signature_status(headers or {}, payload=payload, raw_body=raw_body)
        tracking = payload.get(self.webhook_reference_field or "tracking_number") or payload.get("tracking_number")
        external_reference = payload.get("external_reference") or payload.get("reference") or ""
        order_domain = [("tijara_delivery_provider_id", "=", self.id)]
        if tracking:
            order_domain.append(("tijara_delivery_tracking_number", "=", tracking))
        elif external_reference:
            order_domain.append(("tijara_delivery_provider_reference", "=", external_reference))
        else:
            raise UserError(_("Delivery webhook must include tracking number or external reference."))
        order = self.env["sale.order"].sudo().search(order_domain, limit=1)
        provider_status = payload.get(self.webhook_status_field or "status") or payload.get("status")
        mapped_status = self._delivery_status_from_provider(provider_status)
        event_status = "processed" if order and signature_status in {"valid", "not_required"} else "failed"
        message = _("Webhook processed.") if event_status == "processed" else _("Webhook could not be applied.")
        event = self._delivery_event(
            order=order,
            event_type="webhook",
            direction="inbound",
            status=event_status,
            payload=payload,
            response={"mapped_status": mapped_status, "order_found": bool(order)},
            signature_status=signature_status,
            external_reference=external_reference,
            tracking_number=tracking,
            message=message,
        )
        if order and event_status == "processed":
            values = {
                "tijara_delivery_status": mapped_status,
                "tijara_delivery_adapter_state": "failed" if mapped_status == "failed" else "webhook_synced",
                "tijara_last_tracking_at": fields.Datetime.now(),
                "tijara_delivery_last_event_id": event.id,
            }
            if mapped_status in {"delivered", "cancelled"}:
                values["tijara_delivery_sla_state"] = "resolved"
            eta = payload.get(self.webhook_eta_field or "eta") or payload.get("eta")
            if eta:
                values["tijara_delivery_eta"] = eta
            if mapped_status == "failed":
                values["tijara_delivery_exception_reason"] = payload.get("reason") or payload.get("message") or ""
            order.write(values)
            if mapped_status == "failed":
                self._raise_delivery_exception(
                    order,
                    category="failed_delivery",
                    severity="critical",
                    message=payload.get("reason") or payload.get("message") or _("Provider reported delivery failure."),
                    event=event,
                )
        elif order and event_status == "failed":
            self._raise_delivery_exception(
                order,
                category="webhook_error",
                severity="critical",
                message=_("Delivery webhook failed signature or status validation."),
                event=event,
            )
        return {
            "status": "ok" if event_status == "processed" else "error",
            "event_id": event.id,
            "signature_status": signature_status,
            "delivery_status": mapped_status,
            "order_id": order.id if order else False,
        }
