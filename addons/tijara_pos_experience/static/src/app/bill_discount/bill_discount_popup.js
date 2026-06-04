import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class TijaraBillDiscountPopup extends Component {
    static template = "tijara_pos_experience.BillDiscountPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        baseAmount: Number,
        defaultMode: { type: String, optional: true },
        startingPercent: { type: Number, optional: true },
        startingAmount: { type: Number, optional: true },
        maxPercent: { type: Number, optional: true },
        formatCurrency: Function,
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        title: _t("Bill Discount"),
        defaultMode: "percent",
        startingPercent: 0,
        startingAmount: 0,
        maxPercent: 100,
    };

    setup() {
        const baseAmount = this.roundCurrency(Math.abs(this.props.baseAmount || 0));
        const percent =
            this.props.defaultMode === "amount"
                ? this.percentFromAmount(this.props.startingAmount || 0, baseAmount)
                : this.clampPercent(this.props.startingPercent || 0);
        const amount =
            this.props.defaultMode === "amount"
                ? this.clampAmount(this.props.startingAmount || 0, baseAmount)
                : this.amountFromPercent(percent, baseAmount);

        this.state = useState({
            mode: this.props.defaultMode,
            baseAmount,
            percent,
            amount,
            netAmount: this.roundCurrency(baseAmount - amount),
        });
    }

    parseNumber(value) {
        const parsed = Number.parseFloat((value || "0").toString().replace(/,/g, ""));
        return Number.isFinite(parsed) ? parsed : 0;
    }

    roundCurrency(value) {
        return Math.round((value + Number.EPSILON) * 100) / 100;
    }

    clampPercent(value) {
        const maxPercent = Math.max(0, Math.min(this.props.maxPercent || 100, 100));
        return Math.max(0, Math.min(this.roundCurrency(value), maxPercent));
    }

    clampAmount(value, baseAmount = this.state.baseAmount) {
        const maxAmount = this.amountFromPercent(this.props.maxPercent || 100, baseAmount);
        return Math.max(0, Math.min(this.roundCurrency(value), maxAmount));
    }

    amountFromPercent(percent, baseAmount = this.state.baseAmount) {
        return this.roundCurrency((baseAmount * this.clampPercent(percent)) / 100);
    }

    percentFromAmount(amount, baseAmount = this.state.baseAmount) {
        if (!baseAmount) {
            return 0;
        }
        return this.clampPercent((this.clampAmount(amount, baseAmount) / baseAmount) * 100);
    }

    syncNetAmount() {
        this.state.netAmount = this.roundCurrency(this.state.baseAmount - this.state.amount);
    }

    onPercentInput(event) {
        this.state.mode = "percent";
        this.state.percent = this.clampPercent(this.parseNumber(event.target.value));
        this.state.amount = this.amountFromPercent(this.state.percent);
        this.syncNetAmount();
    }

    onAmountInput(event) {
        this.state.mode = "amount";
        this.state.amount = this.clampAmount(this.parseNumber(event.target.value));
        this.state.percent = this.percentFromAmount(this.state.amount);
        this.syncNetAmount();
    }

    confirm() {
        this.props.getPayload({
            mode: this.state.mode,
            baseAmount: this.state.baseAmount,
            percent: this.state.percent,
            amount: this.state.amount,
            netAmount: this.state.netAmount,
        });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
