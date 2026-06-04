import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

function lineValue(line, names, fallback = 0) {
    for (const name of names) {
        const value = typeof line[name] === "function" ? line[name]() : line[name];
        if (value !== undefined && value !== null) {
            return value;
        }
    }
    return fallback;
}

patch(PosStore.prototype, {
    setup() {
        super.setup(...arguments);
        this.tijaraCustomerDisplayFingerprint = "";
        if (!this.tijaraCustomerDisplayTimer && typeof window !== "undefined") {
            this.tijaraCustomerDisplayTimer = window.setInterval(
                () => this.tijaraPublishCustomerDisplay?.("building"),
                1500
            );
        }
    },

    tijaraCustomerDisplayPayload(status = "building") {
        const order = this.getOrder?.();
        if (!order) {
            return false;
        }
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
                urdu_name: product?.tijara_urdu_name || "",
                quantity,
                price_unit: priceUnit,
                discount: Number(lineValue(line, ["discount", "getDiscount"], 0)),
                subtotal,
            };
        });
        const total = Number(
            order.getTotalWithTax?.() ||
                lines.reduce((sum, line) => sum + line.subtotal, 0)
        );
        const subtotal = Number(order.getTotalWithoutTax?.() || total);
        return {
            status,
            order_reference: order.name || order.pos_reference || "",
            cashier_name: this.cashier?.name || "",
            customer_name: order.partner_id?.name || "",
            audience: order.tijara_audience || "b2c",
            order_type: order.tijara_order_type || "takeaway",
            payment_summary: status === "payment" ? "Payment in progress" : "",
            lines,
            totals: {
                subtotal,
                discount: Number(order.tijara_bill_discount_amount || 0),
                tax: Math.max(total - subtotal, 0),
                total,
            },
        };
    },

    async tijaraPublishCustomerDisplay(status = "building") {
        if (
            !this.config?.tijara_customer_display_enabled ||
            !this.config?.tijara_customer_display_id
        ) {
            return;
        }
        const payload = this.tijaraCustomerDisplayPayload(status);
        if (!payload) {
            return;
        }
        const fingerprint = JSON.stringify(payload);
        if (fingerprint === this.tijaraCustomerDisplayFingerprint) {
            return;
        }
        this.tijaraCustomerDisplayFingerprint = fingerprint;
        try {
            await rpc("/tijara/customer-display/publish", {
                config_id: this.config.id,
                status,
                order: payload,
            });
        } catch {
            this.tijaraCustomerDisplayFingerprint = "";
        }
    },
});
