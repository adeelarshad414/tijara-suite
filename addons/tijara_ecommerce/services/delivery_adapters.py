class BaseDeliveryAdapter:
    profile_code = "manual"
    provider_name = "Manual"
    sandbox_base_url = "https://delivery-sandbox.example.test"

    def credential_refs(self, provider):
        return {
            "api_token_ref": "secret://tijara/delivery/%s/api-token" % provider.code,
            "webhook_secret_ref": provider.webhook_secret_ref
            or "secret://tijara/delivery/%s/webhook-secret" % provider.code,
        }

    def canonical_order(self, provider, order, lines):
        return {
            "provider": provider.code,
            "adapter_profile": provider.adapter_profile,
            "adapter_mode": provider.adapter_mode,
            "dry_run": provider.dry_run,
            "order": {
                "id": order.id,
                "name": order.name,
                "reference": order.client_order_ref or order.tijara_ecommerce_reference or "",
                "fulfillment_method": order.tijara_fulfillment_method,
                "amount_total": order.amount_total,
                "currency": order.currency_id.name,
            },
            "customer": {
                "name": order.partner_id.name or "",
                "mobile": order.tijara_delivery_mobile
                or getattr(order.partner_id, "mobile", "")
                or order.partner_id.phone
                or "",
                "email": order.partner_id.email or "",
                "address": order.tijara_delivery_address or "",
            },
            "lines": lines,
        }

    def shipment_payload(self, provider, order, lines):
        canonical = self.canonical_order(provider, order, lines)
        return {
            "adapter": {
                "profile": self.profile_code,
                "provider_name": self.provider_name,
                "sandbox_base_url": provider.api_base_url or self.sandbox_base_url,
                "credential_refs": self.credential_refs(provider),
                "assumption_mode": True,
            },
            "canonical": canonical,
            "provider_payload": self.provider_shipment_payload(provider, order, lines, canonical),
        }

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "reference": canonical["order"]["reference"] or canonical["order"]["name"],
            "tracking_number": order.tijara_delivery_tracking_number or provider._tracking_number_for_order(order),
            "cod_amount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
            "recipient": canonical["customer"],
            "items": lines,
            "service_level": provider.service_level,
        }

    def cancel_payload(self, provider, order, reason):
        return {
            "provider": provider.code,
            "adapter_profile": provider.adapter_profile,
            "order_id": order.id,
            "order_name": order.name,
            "external_reference": order.tijara_delivery_provider_reference or "",
            "tracking_number": order.tijara_delivery_tracking_number or "",
            "reason": reason or "Cancelled by operator",
            "provider_payload": {
                "cancel_reference": order.tijara_delivery_provider_reference or order.name,
                "reason": reason or "Cancelled by operator",
            },
        }

    def label_payload(self, provider, order):
        return {
            "format": provider.label_format,
            "provider": provider.code,
            "adapter_profile": provider.adapter_profile,
            "tracking_number": order.tijara_delivery_tracking_number or "",
            "order_name": order.name,
            "dry_run": provider.dry_run,
            "content": "TIJARA LABEL %s %s" % (provider.code, order.tijara_delivery_tracking_number or order.name),
            "provider_payload": {
                "label_reference": order.tijara_delivery_tracking_number or order.name,
                "format": provider.label_format,
            },
        }

    def manifest_payload(self, provider, manifest_reference, orders):
        return {
            "provider": provider.code,
            "adapter_profile": provider.adapter_profile,
            "manifest_reference": manifest_reference,
            "orders": [
                {
                    "order_id": order.id,
                    "order_name": order.name,
                    "tracking_number": order.tijara_delivery_tracking_number or "",
                    "external_reference": order.tijara_delivery_provider_reference or "",
                }
                for order in orders
            ],
            "provider_payload": {
                "manifest_no": manifest_reference,
                "shipment_refs": [
                    order.tijara_delivery_provider_reference or order.name for order in orders
                ],
            },
        }

    def assumed_response(self, provider, operation, payload, order=False):
        response = {
            "provider": provider.code,
            "adapter_profile": provider.adapter_profile,
            "operation": operation,
            "assumed": True,
            "status": "accepted",
            "provider_reference_field": "reference",
        }
        if order:
            response.update(
                {
                    "tracking_number": order.tijara_delivery_tracking_number
                    or provider._tracking_number_for_order(order),
                    "external_reference": order.tijara_delivery_provider_reference
                    or provider._provider_reference_for_order(order),
                }
            )
        else:
            response.update(
                {
                    "tracking_number": payload.get("tracking_number") or "",
                    "external_reference": payload.get("external_reference") or "",
                }
            )
        if operation == "shipment_cancel":
            response["status"] = "cancelled"
        if operation == "label":
            response.update({"label_format": provider.label_format, "label_ready": True})
        if operation == "manifest":
            response.update({"manifest_reference": payload.get("manifest_reference") or ""})
        return response


class InHouseRiderAdapter(BaseDeliveryAdapter):
    profile_code = "in_house_rider"
    provider_name = "In-House Rider"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "task_type": "local_delivery",
            "rider": {
                "name": provider.rider_name or "Assumed Rider",
                "mobile": provider.rider_mobile or provider.contact_phone or "0300-0000000",
            },
            "pickup": {"branch": provider.company_id.name, "phone": provider.contact_phone or ""},
            "dropoff": canonical["customer"],
            "order_ref": canonical["order"]["reference"] or canonical["order"]["name"],
            "cod_amount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
            "items": lines,
            "sla_hours": provider.sla_hours,
        }


class TCSAdapter(BaseDeliveryAdapter):
    profile_code = "tcs"
    provider_name = "TCS Pakistan"
    sandbox_base_url = "https://sandbox.example.test/tcs"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "consignmentNumber": order.tijara_delivery_tracking_number or "",
            "customerReferenceNo": canonical["order"]["reference"] or canonical["order"]["name"],
            "service": provider.service_level,
            "codAmount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
            "shipper": {"name": provider.company_id.name, "phone": provider.contact_phone or ""},
            "consignee": {
                "name": canonical["customer"]["name"],
                "phone": canonical["customer"]["mobile"],
                "email": canonical["customer"]["email"],
                "address": canonical["customer"]["address"],
            },
            "pieces": max(len(lines), 1),
            "productDetails": lines,
        }


class LeopardsAdapter(BaseDeliveryAdapter):
    profile_code = "leopards"
    provider_name = "Leopards Courier"
    sandbox_base_url = "https://sandbox.example.test/leopards"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "book_packet": {
                "packet_reference": canonical["order"]["reference"] or canonical["order"]["name"],
                "consignee_name": canonical["customer"]["name"],
                "consignee_phone": canonical["customer"]["mobile"],
                "consignee_address": canonical["customer"]["address"],
                "cod_amount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
                "pieces": max(len(lines), 1),
                "weight_grams": max(len(lines), 1) * 500,
                "instructions": "Assumed Tijara local/staging payload.",
            }
        }


class PostExAdapter(BaseDeliveryAdapter):
    profile_code = "postex"
    provider_name = "PostEx"
    sandbox_base_url = "https://sandbox.example.test/postex"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "orderReferenceNumber": canonical["order"]["reference"] or canonical["order"]["name"],
            "invoicePayment": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
            "orderDetail": ", ".join(line.get("name") or line.get("product") or "" for line in lines)[:250],
            "customerName": canonical["customer"]["name"],
            "customerPhone": canonical["customer"]["mobile"],
            "deliveryAddress": canonical["customer"]["address"],
            "transactionNotes": "Assumed PostEx sandbox payload for Tijara.",
        }


class MNPAdapter(BaseDeliveryAdapter):
    profile_code = "mnp"
    provider_name = "M&P"
    sandbox_base_url = "https://sandbox.example.test/mnp"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "order_id": canonical["order"]["reference"] or canonical["order"]["name"],
            "service_type": provider.service_level,
            "consignee": canonical["customer"],
            "cod_amount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
            "no_of_pieces": max(len(lines), 1),
            "product_detail": lines,
            "fragile": False,
        }


class BlueExAdapter(BaseDeliveryAdapter):
    profile_code = "blue_ex"
    provider_name = "BlueEx"
    sandbox_base_url = "https://sandbox.example.test/blueex"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "create_packet": {
                "order_ref": canonical["order"]["reference"] or canonical["order"]["name"],
                "consignee_name": canonical["customer"]["name"],
                "consignee_phone": canonical["customer"]["mobile"],
                "consignee_email": canonical["customer"]["email"],
                "consignee_address": canonical["customer"]["address"],
                "cod": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
                "items": lines,
            }
        }


class TraxAdapter(BaseDeliveryAdapter):
    profile_code = "trax"
    provider_name = "Trax"
    sandbox_base_url = "https://sandbox.example.test/trax"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "shipments": [
                {
                    "reference_number": canonical["order"]["reference"] or canonical["order"]["name"],
                    "service_type_id": provider.service_level,
                    "pickup_address": provider.company_id.name,
                    "delivery_address": canonical["customer"]["address"],
                    "customer": canonical["customer"],
                    "cod_amount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
                    "items": lines,
                }
            ]
        }


class RiderAdapter(BaseDeliveryAdapter):
    profile_code = "rider"
    provider_name = "Rider"
    sandbox_base_url = "https://sandbox.example.test/rider"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "order": {
                "order_id": canonical["order"]["reference"] or canonical["order"]["name"],
                "value": canonical["order"]["amount_total"],
                "payment_mode": "COD" if order.tijara_payment_method == "cod" else "PREPAID",
            },
            "dropoff": canonical["customer"],
            "items": lines,
            "delivery_window": {"sla_hours": provider.sla_hours or 24.0},
        }


class CallCourierAdapter(BaseDeliveryAdapter):
    profile_code = "call_courier"
    provider_name = "Call Courier"
    sandbox_base_url = "https://sandbox.example.test/call-courier"

    def provider_shipment_payload(self, provider, order, lines, canonical):
        return {
            "consignment": {
                "reference_no": canonical["order"]["reference"] or canonical["order"]["name"],
                "consignee": canonical["customer"],
                "cod_amount": order.amount_total if order.tijara_payment_method == "cod" else 0.0,
                "pieces": max(len(lines), 1),
                "weight": max(len(lines), 1) * 0.5,
                "remarks": "Assumed Call Courier payload generated by Tijara.",
            }
        }


ADAPTERS = {
    "in_house_rider": InHouseRiderAdapter(),
    "tcs": TCSAdapter(),
    "leopards": LeopardsAdapter(),
    "postex": PostExAdapter(),
    "mnp": MNPAdapter(),
    "blue_ex": BlueExAdapter(),
    "trax": TraxAdapter(),
    "rider": RiderAdapter(),
    "call_courier": CallCourierAdapter(),
    "manual": BaseDeliveryAdapter(),
    "dummy": BaseDeliveryAdapter(),
}


def get_delivery_adapter(profile):
    return ADAPTERS.get(profile or "manual", ADAPTERS["manual"])
