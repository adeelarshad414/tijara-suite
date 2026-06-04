import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

const AUDIENCE_LABELS = {
    b2c: _t("B2C"),
    b2b: _t("B2B"),
};

const ORDER_TYPE_LABELS = {
    dine_in: _t("Dine In"),
    takeaway: _t("Takeaway"),
    pickup: _t("Pickup"),
};

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.tijara_audience =
            vals.tijara_audience || this.config?.tijara_default_audience || "b2c";
        this.tijara_order_type = vals.tijara_order_type || "takeaway";
        this.tijara_pickup_code = vals.tijara_pickup_code || "";
        this.tijara_promised_at = vals.tijara_promised_at || false;
    },

    get tijaraAudienceLabel() {
        return AUDIENCE_LABELS[this.tijara_audience] || _t("B2C");
    },

    get tijaraOrderTypeLabel() {
        return ORDER_TYPE_LABELS[this.tijara_order_type] || _t("Takeaway");
    },

    tijaraSetAudience(audience) {
        this.tijara_audience = audience || "b2c";
        for (const line of this.getOrderlines()) {
            const product = line.product_id;
            const price =
                this.tijara_audience === "b2b"
                    ? product?.tijara_b2b_price
                    : product?.tijara_b2c_price;
            if (price) {
                line.setUnitPrice(price);
            }
        }
    },

    tijaraSetOrderType(orderType) {
        this.tijara_order_type = orderType || "takeaway";
        if (this.tijara_order_type === "pickup" && !this.tijara_pickup_code) {
            this.tijara_pickup_code = `PK-${Math.floor(100 + Math.random() * 900)}`;
        }
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data.tijara_audience = this.tijara_audience || "b2c";
        data.tijara_order_type = this.tijara_order_type || "takeaway";
        data.tijara_pickup_code = this.tijara_pickup_code || false;
        data.tijara_promised_at = this.tijara_promised_at || false;
        return data;
    },
});

patch(ControlButtons.prototype, {
    async clickTijaraAudience() {
        const order = this.pos.getOrder();
        const list = [];
        if (this.pos.config.tijara_allow_b2c) {
            list.push({
                id: "b2c",
                label: _t("B2C Retail"),
                isSelected: order.tijara_audience === "b2c",
                item: "b2c",
            });
        }
        if (this.pos.config.tijara_allow_b2b) {
            list.push({
                id: "b2b",
                label: _t("B2B Trade"),
                isSelected: order.tijara_audience === "b2b",
                item: "b2b",
            });
        }
        const payload = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Select sale type"),
            list,
        });
        if (payload) {
            order.tijaraSetAudience(payload);
        }
    },

    async clickTijaraOrderType() {
        const order = this.pos.getOrder();
        const list = [
            {
                id: "dine_in",
                label: _t("Dine In"),
                isSelected: order.tijara_order_type === "dine_in",
                item: "dine_in",
            },
            {
                id: "takeaway",
                label: _t("Takeaway"),
                isSelected: order.tijara_order_type === "takeaway",
                item: "takeaway",
            },
            {
                id: "pickup",
                label: _t("Pickup"),
                isSelected: order.tijara_order_type === "pickup",
                item: "pickup",
            },
        ];
        const payload = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Select service mode"),
            list,
        });
        if (payload) {
            order.tijaraSetOrderType(payload);
        }
    },
});
