import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PosStore } from "@point_of_sale/app/services/pos_store";

function lineValue(record, names, fallback = 0) {
    for (const name of names) {
        const value = typeof record?.[name] === "function" ? record[name]() : record?.[name];
        if (value !== undefined && value !== null) {
            return value;
        }
    }
    return fallback;
}

function uuid() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `offline-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
}

function jsonFetch(url, payload) {
    return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
    }).then((response) => response.json().then((data) => ({ ok: response.ok, data })));
}

patch(PosStore.prototype, {
    setup() {
        super.setup(...arguments);
        if (typeof window === "undefined") {
            return;
        }
        this.tijaraOfflineDeviceId = this.tijaraEnsureOfflineDeviceId();
        if (!this.tijaraOfflineReplayTimer) {
            window.addEventListener("online", () => this.tijaraReplayOfflineQueue?.());
            this.tijaraOfflineReplayTimer = window.setInterval(
                () => this.tijaraReplayOfflineQueue?.(),
                10000
            );
        }
    },

    tijaraOfflineDeviceKey() {
        return `tijara.offline_pos.device.${this.config?.id || "no-config"}`;
    },

    tijaraOfflineQueueKey() {
        return `tijara.offline_pos.queue.${this.config?.id || "no-config"}`;
    },

    tijaraEnsureOfflineDeviceId() {
        const key = this.tijaraOfflineDeviceKey();
        let deviceId = localStorage.getItem(key);
        if (!deviceId) {
            deviceId = `pos-${this.config?.id || "unknown"}-${uuid()}`;
            localStorage.setItem(key, deviceId);
        }
        return deviceId;
    },

    tijaraOfflineQueue() {
        try {
            return JSON.parse(localStorage.getItem(this.tijaraOfflineQueueKey()) || "[]");
        } catch {
            return [];
        }
    },

    tijaraSaveOfflineQueue(items) {
        localStorage.setItem(this.tijaraOfflineQueueKey(), JSON.stringify(items || []));
    },

    tijaraOrderPayments(order) {
        const paymentLines = order.payment_ids || order.paymentlines || [];
        return paymentLines
            .map((payment) => {
                const method = payment.payment_method_id || payment.payment_method || {};
                return {
                    amount: Number(lineValue(payment, ["amount", "getAmount"], 0)),
                    payment_method_id: method.id || false,
                    payment_method_name: method.name || "",
                    payment_reference:
                        payment.payment_ref_no ||
                        payment.transaction_id ||
                        payment.card_type ||
                        false,
                    payment_status: payment.payment_status || "paid",
                };
            })
            .filter((payment) => payment.amount > 0);
    },

    tijaraOfflineOrderPayload(order, reason = "sync_failed") {
        const lines = order.getOrderlines().map((line) => {
            const product = line.product_id || line.getProduct?.();
            const quantity = Number(lineValue(line, ["qty", "getQuantity"], 0));
            const priceUnit = Number(lineValue(line, ["price_unit", "getUnitPrice"], 0));
            const subtotal = Number(
                lineValue(
                    line,
                    ["price_subtotal_incl", "priceIncl", "getPriceWithTax"],
                    quantity * priceUnit
                )
            );
            return {
                product_id: product?.id || false,
                name: product?.display_name || product?.name || line.full_product_name || "",
                qty: quantity,
                price_unit: priceUnit,
                discount: Number(lineValue(line, ["discount", "getDiscount"], 0)),
                subtotal,
            };
        });
        const total = Number(
            order.getTotalWithTax?.() ||
                lines.reduce((sum, line) => sum + Number(line.subtotal || 0), 0)
        );
        const payments = this.tijaraOrderPayments(order);
        const paid = payments.reduce((sum, payment) => sum + payment.amount, 0);
        const sourceOrderUid = order.uuid || order.uid || order.name || uuid();
        return {
            source_app: "pos_frontend",
            source_device_id: this.tijaraOfflineDeviceId || this.tijaraEnsureOfflineDeviceId(),
            source_order_uid: String(sourceOrderUid),
            pos_config_id: this.config?.id || false,
            order_reference: order.name || order.pos_reference || String(sourceOrderUid),
            customer_name: order.partner_id?.name || "",
            customer_mobile: order.partner_id?.mobile || order.partner_id?.phone || "",
            customer_email: order.partner_id?.email || "",
            partner_id: order.partner_id?.id || false,
            audience: order.tijara_audience || "b2c",
            order_type: order.tijara_order_type || "takeaway",
            pickup_code: order.tijara_pickup_code || "",
            payment_status: paid >= total ? "paid" : paid > 0 ? "authorized" : "pending",
            amount_total: total,
            amount_paid: paid,
            payments,
            lines,
            totals: {
                subtotal: Number(order.getTotalWithoutTax?.() || total),
                tax: Number(order.getTotalTax?.() || 0),
                total,
            },
            captured_at: new Date().toISOString(),
            capture_reason: reason,
        };
    },

    tijaraCaptureOfflineOrder(reason = "manual", order = this.getOrder?.()) {
        if (!order || !order.getOrderlines?.().length) {
            return false;
        }
        const payload = this.tijaraOfflineOrderPayload(order, reason);
        const queue = this.tijaraOfflineQueue();
        const existing = queue.find(
            (entry) =>
                entry.payload.source_device_id === payload.source_device_id &&
                entry.payload.source_order_uid === payload.source_order_uid
        );
        if (existing) {
            existing.payload = payload;
            existing.status = "queued";
            existing.error = "";
            existing.updated_at = new Date().toISOString();
        } else {
            queue.push({
                id: uuid(),
                status: "queued",
                attempts: 0,
                error: "",
                payload,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            });
        }
        this.tijaraSaveOfflineQueue(queue);
        return payload;
    },

    async tijaraReplayOfflineQueue() {
        if (typeof navigator !== "undefined" && navigator.onLine === false) {
            return;
        }
        const queue = this.tijaraOfflineQueue();
        if (!queue.length) {
            return;
        }
        const remaining = [];
        for (const entry of queue) {
            try {
                const response = await jsonFetch("/tijara/offline-pos/capture", {
                    payload: entry.payload,
                    replay: true,
                });
                if (
                    response.ok &&
                    (response.data.queue_state === "replayed" || response.data.status === "duplicate")
                ) {
                    continue;
                }
                entry.status = response.data.queue_state || "failed";
                entry.error = response.data.error || response.data.message || "";
            } catch (error) {
                entry.status = "queued";
                entry.error = error.message || String(error);
            }
            entry.attempts = (entry.attempts || 0) + 1;
            entry.updated_at = new Date().toISOString();
            remaining.push(entry);
        }
        this.tijaraSaveOfflineQueue(remaining);
    },

    async syncAllOrders() {
        if (!super.syncAllOrders) {
            await this.tijaraReplayOfflineQueue();
            return;
        }
        try {
            const result = await super.syncAllOrders(...arguments);
            await this.tijaraReplayOfflineQueue();
            return result;
        } catch (error) {
            this.tijaraCaptureOfflineOrder("syncAllOrders_failed");
            throw error;
        }
    },
});

patch(ControlButtons.prototype, {
    async clickTijaraOfflineQueue() {
        const before = this.pos.tijaraOfflineQueue?.() || [];
        const beforeCount = before.length;
        await this.pos.tijaraReplayOfflineQueue?.();
        const queue = this.pos.tijaraOfflineQueue?.() || [];
        const blocked = queue.filter((entry) =>
            ["failed", "conflict"].includes(entry.status)
        ).length;
        const replayed = Math.max(beforeCount - queue.length, 0);
        this.dialog.add(AlertDialog, {
            title: _t("Offline POS Queue"),
            body: [
                `${_t("Queued orders")}: ${queue.length}`,
                `${_t("Needs review")}: ${blocked}`,
                `${_t("Replayed now")}: ${replayed}`,
            ].join("\n"),
        });
    },
});
