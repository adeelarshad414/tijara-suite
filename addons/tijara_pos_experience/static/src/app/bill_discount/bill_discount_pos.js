import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { TijaraBillDiscountPopup } from "@tijara_pos_experience/app/bill_discount/bill_discount_popup";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.tijara_bill_discount_mode =
            vals.tijara_bill_discount_mode ||
            this.config?.tijara_bill_discount_default_mode ||
            "percent";
        this.tijara_bill_discount_base_amount = vals.tijara_bill_discount_base_amount || 0;
        this.tijara_bill_discount_percent = vals.tijara_bill_discount_percent || 0;
        this.tijara_bill_discount_amount = vals.tijara_bill_discount_amount || 0;
        this.tijara_bill_discount_net_amount = vals.tijara_bill_discount_net_amount || 0;
    },

    get tijaraBillDiscountBaseAmount() {
        const lines = this.getOrderlines().filter((line) =>
            line.isGlobalDiscountApplicable ? line.isGlobalDiscountApplicable() : true
        );
        return this.currency.round(
            lines.reduce((sum, line) => sum + Math.abs(line.priceIncl || 0), 0)
        );
    },

    tijaraClampBillDiscountPercent(percent) {
        const maxPercent = Math.max(
            0,
            Math.min(this.config?.tijara_bill_discount_max_percent || 100, 100)
        );
        return Math.max(0, Math.min(percent || 0, maxPercent));
    },

    tijaraSetBillDiscount(payload) {
        this.tijara_bill_discount_mode = payload.mode || "percent";
        this.tijara_bill_discount_base_amount = this.currency.round(payload.baseAmount || 0);
        this.tijara_bill_discount_percent = this.tijaraClampBillDiscountPercent(
            payload.percent || 0
        );
        this.tijara_bill_discount_amount = this.currency.round(payload.amount || 0);
        this.tijara_bill_discount_net_amount = this.currency.round(payload.netAmount || 0);
    },

    tijaraSyncBillDiscountFromPercent(percent) {
        const baseAmount = this.tijaraBillDiscountBaseAmount;
        let discountPercent = this.tijaraClampBillDiscountPercent(percent || 0);
        let discountAmount = this.currency.round((baseAmount * discountPercent) / 100);

        if (this.tijara_bill_discount_mode === "amount") {
            const maxAmount = this.currency.round(
                (baseAmount * (this.config?.tijara_bill_discount_max_percent || 100)) / 100
            );
            discountAmount = Math.max(
                0,
                Math.min(this.currency.round(this.tijara_bill_discount_amount || 0), maxAmount)
            );
            discountPercent = baseAmount
                ? this.tijaraClampBillDiscountPercent((discountAmount / baseAmount) * 100)
                : 0;
        }

        this.tijara_bill_discount_base_amount = baseAmount;
        this.tijara_bill_discount_percent = discountPercent;
        this.tijara_bill_discount_amount = discountAmount;
        this.tijara_bill_discount_net_amount = this.currency.round(baseAmount - discountAmount);
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data.tijara_bill_discount_mode = this.tijara_bill_discount_mode || "percent";
        data.tijara_bill_discount_base_amount = this.tijara_bill_discount_base_amount || 0;
        data.tijara_bill_discount_percent = this.tijara_bill_discount_percent || 0;
        data.tijara_bill_discount_amount = this.tijara_bill_discount_amount || 0;
        data.tijara_bill_discount_net_amount = this.tijara_bill_discount_net_amount || 0;
        return data;
    },
});

patch(PosStore.prototype, {
    async applyDiscount(percent, order = this.getOrder()) {
        let discountPercent = percent;
        if (order?.tijara_bill_discount_mode === "amount") {
            const baseAmount = order.tijaraBillDiscountBaseAmount;
            discountPercent = baseAmount
                ? (order.tijara_bill_discount_amount / baseAmount) * 100
                : 0;
        }

        discountPercent = order?.tijaraClampBillDiscountPercent
            ? order.tijaraClampBillDiscountPercent(discountPercent)
            : discountPercent;
        const result = await super.applyDiscount(discountPercent, order);
        order?.tijaraSyncBillDiscountFromPercent?.(discountPercent);
        return result;
    },
});

patch(ControlButtons.prototype, {
    async clickDiscount() {
        if (!this.pos.config.tijara_bill_discount_enabled) {
            return super.clickDiscount(...arguments);
        }

        return this.clickTijaraBillDiscount();
    },

    async clickTijaraBillDiscount() {
        if (!this.pos.config.tijara_bill_discount_enabled) {
            this.dialog.add(AlertDialog, {
                title: _t("Bill discount disabled"),
                body: _t("Enable bill discounts in the POS configuration before using this action."),
            });
            return;
        }

        if (
            this.pos.config.tijara_bill_discount_requires_manager &&
            this.pos.cashier._role !== "manager"
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("Manager approval required"),
                body: _t("Ask a POS manager to apply an overall bill discount."),
            });
            return;
        }

        const order = this.pos.getOrder();
        const baseAmount = order.tijaraBillDiscountBaseAmount;
        if (!baseAmount) {
            this.dialog.add(AlertDialog, {
                title: _t("No bill amount"),
                body: _t("Add products before applying an overall bill discount."),
            });
            return;
        }

        const startingPercent = order.tijara_bill_discount_percent || order.globalDiscountPc || 0;
        const startingAmount =
            order.tijara_bill_discount_amount ||
            order.currency.round((baseAmount * startingPercent) / 100);

        this.dialog.add(TijaraBillDiscountPopup, {
            title: _t("Overall Bill Discount"),
            baseAmount,
            defaultMode:
                order.tijara_bill_discount_mode ||
                this.pos.config.tijara_bill_discount_default_mode ||
                "percent",
            startingPercent,
            startingAmount,
            maxPercent: this.pos.config.tijara_bill_discount_max_percent || 100,
            formatCurrency: (amount) => this.env.utils.formatCurrency(amount),
            getPayload: async (payload) => {
                order.tijaraSetBillDiscount(payload);
                await this.pos.applyDiscount(payload.percent, order);
            },
        });
    },
});
