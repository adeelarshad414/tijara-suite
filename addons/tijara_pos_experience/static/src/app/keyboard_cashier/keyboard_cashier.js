import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

const INPUT_SELECTOR = "input, textarea, select, [contenteditable='true']";
const BUFFER_CLEAR_MS = 900;
const ORDER_TYPES = ["dine_in", "takeaway", "pickup", "delivery"];
const SEARCH_SELECTORS = [
    ".product-screen input[type='search']",
    ".product-screen input[placeholder]",
    ".pos-content input[type='search']",
    ".pos-content input[placeholder]",
    "input[type='search']",
];

function normalized(value) {
    return String(value || "").trim().toLowerCase();
}

function activeInput() {
    const element = document.activeElement;
    return element?.matches?.(INPUT_SELECTOR) ? element : null;
}

function enabledButton(element) {
    return element && !element.disabled && element.getAttribute("aria-disabled") !== "true";
}

function clickButtonByText(patterns) {
    const buttons = [...document.querySelectorAll("button, [role='button'], .btn")];
    for (const button of buttons) {
        const label = normalized(button.textContent || button.getAttribute("aria-label") || "");
        if (enabledButton(button) && patterns.some((pattern) => pattern.test(label))) {
            button.click();
            return true;
        }
    }
    return false;
}

function clickSelector(selectors) {
    for (const selector of selectors) {
        const element = document.querySelector(selector);
        if (enabledButton(element)) {
            element.click();
            return true;
        }
    }
    return false;
}

function recordsFromModel(pos, modelName) {
    const model = pos.models?.[modelName];
    if (!model) {
        return [];
    }
    if (Array.isArray(model)) {
        return model;
    }
    if (typeof model.getAll === "function") {
        return model.getAll();
    }
    if (model.records) {
        return Array.isArray(model.records) ? model.records : Object.values(model.records);
    }
    if (typeof model.values === "function") {
        return [...model.values()];
    }
    return [];
}

patch(PosStore.prototype, {
    setup() {
        const result = super.setup(...arguments);
        this.tijaraInstallKeyboardCashierFlow();
        return result;
    },

    tijaraInstallKeyboardCashierFlow() {
        if (this.tijaraKeyboardCashierInstalled || typeof window === "undefined") {
            return;
        }
        this.tijaraKeyboardCashierInstalled = true;
        this.tijaraKeyboardBuffer = "";
        this.tijaraKeyboardBufferTimer = null;
        this.tijaraKeyboardHandler = (event) => this.tijaraHandleKeyboardCashierEvent(event);
        window.addEventListener("keydown", this.tijaraKeyboardHandler, true);
    },

    tijaraKeyboardEnabled() {
        return this.config?.tijara_keyboard_shortcuts_enabled !== false;
    },

    tijaraNotify(message, type = "info") {
        this.notification?.add?.(message, { type });
    },

    tijaraClearKeyboardBuffer() {
        this.tijaraKeyboardBuffer = "";
        if (this.tijaraKeyboardBufferTimer) {
            window.clearTimeout(this.tijaraKeyboardBufferTimer);
            this.tijaraKeyboardBufferTimer = null;
        }
    },

    tijaraAppendKeyboardBuffer(value) {
        this.tijaraKeyboardBuffer = `${this.tijaraKeyboardBuffer || ""}${value}`;
        if (this.tijaraKeyboardBufferTimer) {
            window.clearTimeout(this.tijaraKeyboardBufferTimer);
        }
        this.tijaraKeyboardBufferTimer = window.setTimeout(
            () => this.tijaraClearKeyboardBuffer(),
            BUFFER_CLEAR_MS
        );
    },

    async tijaraHandleKeyboardCashierEvent(event) {
        if (
            !this.tijaraKeyboardEnabled() ||
            event.defaultPrevented ||
            event.isComposing ||
            event.altKey ||
            event.metaKey ||
            event.ctrlKey
        ) {
            return;
        }

        const input = activeInput();
        if (input && event.key !== "Escape") {
            return;
        }

        const handled = await this.tijaraRunKeyboardCommand(event);
        if (handled) {
            event.preventDefault();
            event.stopPropagation();
        }
    },

    async tijaraRunKeyboardCommand(event) {
        const key = event.key;
        if (key === "Escape") {
            this.tijaraClearKeyboardBuffer();
            activeInput()?.blur?.();
            return true;
        }
        if (key === "F2" || key === "/") {
            this.tijaraFocusProductSearch();
            return true;
        }
        if (key === "F4") {
            return this.tijaraGoPayment();
        }
        if (key === "F5") {
            return await this.tijaraPrintCurrentReceipt();
        }
        if (key === "F6") {
            return this.tijaraStartNewOrder();
        }
        if (key === "F7") {
            return this.tijaraCycleAudience();
        }
        if (key === "F8") {
            return this.tijaraCycleOrderType();
        }
        if (key === "Enter") {
            if (this.tijaraKeyboardBuffer) {
                const query = this.tijaraKeyboardBuffer;
                this.tijaraClearKeyboardBuffer();
                return await this.tijaraAddProductFromKeyboard(query);
            }
            return this.tijaraEnterPrimaryFlow();
        }
        if (key === "Delete" || key === "Backspace") {
            if (this.tijaraKeyboardBuffer) {
                this.tijaraKeyboardBuffer = this.tijaraKeyboardBuffer.slice(0, -1);
                return true;
            }
            return this.tijaraRemoveSelectedLine();
        }
        if (key === "+" || key === "=") {
            return this.tijaraAdjustSelectedQuantity(1);
        }
        if (key === "-") {
            return this.tijaraAdjustSelectedQuantity(-1);
        }
        if (key === "ArrowUp") {
            return this.tijaraSelectRelativeOrderline(-1);
        }
        if (key === "ArrowDown") {
            return this.tijaraSelectRelativeOrderline(1);
        }
        if (key.length === 1) {
            this.tijaraAppendKeyboardBuffer(key);
            return false;
        }
        return false;
    },

    tijaraFocusProductSearch(seed = "") {
        const search = SEARCH_SELECTORS.map((selector) => document.querySelector(selector)).find(Boolean);
        if (!search) {
            return false;
        }
        search.focus();
        if (seed) {
            search.value = seed;
            search.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: seed }));
        }
        return true;
    },

    tijaraFindKeyboardProduct(query) {
        const needle = normalized(query);
        if (!needle) {
            return false;
        }
        const products = recordsFromModel(this, "product.product");
        return products.find((product) => {
            const candidates = [
                product.barcode,
                product.tijara_barcode_alias,
                product.default_code,
                product.display_name,
                product.name,
                product.tijara_label_name,
                product.tijara_urdu_name,
            ].map(normalized);
            return candidates.some((candidate) => candidate === needle);
        }) || products.find((product) => {
            const name = normalized(
                product.display_name ||
                    product.name ||
                    product.tijara_label_name ||
                    product.tijara_urdu_name
            );
            return name.includes(needle);
        });
    },

    async tijaraAddProductFromKeyboard(query) {
        const product = this.tijaraFindKeyboardProduct(query);
        if (!product) {
            this.tijaraFocusProductSearch(query);
            this.tijaraNotify(_t("Product not found. Search field focused."), "warning");
            return true;
        }
        if (typeof this.addProductToCurrentOrder === "function") {
            await this.addProductToCurrentOrder(product, {});
        } else {
            const order = this.getOrder?.();
            if (typeof order?.addProduct === "function") {
                await order.addProduct(product, {});
            } else if (typeof order?.add_product === "function") {
                await order.add_product(product, {});
            } else {
                this.tijaraFocusProductSearch(query);
                return true;
            }
        }
        this.tijaraNotify(_t("Product added from keyboard input."), "success");
        return true;
    },

    tijaraSelectedOrderline() {
        const order = this.getOrder?.();
        return order?.getSelectedOrderline?.() || order?.selected_orderline || false;
    },

    tijaraOrderlines() {
        const order = this.getOrder?.();
        const lines = order?.getOrderlines?.() || order?.orderlines || [];
        if (Array.isArray(lines)) {
            return lines;
        }
        if (typeof lines[Symbol.iterator] === "function") {
            return [...lines];
        }
        if (lines.records) {
            return Array.isArray(lines.records) ? lines.records : Object.values(lines.records);
        }
        return Object.values(lines || {});
    },

    tijaraAdjustSelectedQuantity(delta) {
        const line = this.tijaraSelectedOrderline();
        if (!line) {
            return false;
        }
        const currentQty = Number(line.qty ?? line.quantity ?? line.getQuantity?.() ?? 0);
        const nextQty = Math.max(0, currentQty + delta);
        if (typeof line.setQuantity === "function") {
            line.setQuantity(nextQty);
        } else if (typeof line.set_quantity === "function") {
            line.set_quantity(nextQty);
        } else {
            line.qty = nextQty;
        }
        return true;
    },

    tijaraRemoveSelectedLine() {
        const line = this.tijaraSelectedOrderline();
        const order = this.getOrder?.();
        if (!line || !order) {
            return false;
        }
        if (typeof order.removeOrderline === "function") {
            order.removeOrderline(line);
        } else if (typeof order.remove_orderline === "function") {
            order.remove_orderline(line);
        } else {
            this.tijaraAdjustSelectedQuantity(-Number(line.qty ?? line.quantity ?? 1));
        }
        return true;
    },

    tijaraSelectRelativeOrderline(delta) {
        const order = this.getOrder?.();
        const lines = this.tijaraOrderlines();
        if (!order || !lines.length) {
            return false;
        }
        const selected = this.tijaraSelectedOrderline();
        const currentIndex = Math.max(0, lines.indexOf(selected));
        const nextIndex = Math.max(0, Math.min(lines.length - 1, currentIndex + delta));
        const nextLine = lines[nextIndex];
        if (typeof order.selectOrderline === "function") {
            order.selectOrderline(nextLine);
        } else if (typeof order.select_orderline === "function") {
            order.select_orderline(nextLine);
        }
        return true;
    },

    tijaraGoPayment() {
        if (typeof this.showScreen === "function") {
            this.showScreen("PaymentScreen");
            return true;
        }
        return clickButtonByText([/payment/, /pay/, /ادائیگی/]);
    },

    tijaraEnterPrimaryFlow() {
        if (
            clickSelector([
                ".modal-footer .btn-primary",
                ".popup .btn-primary",
                ".button.next.highlight",
                ".validation.highlight",
            ])
        ) {
            return true;
        }
        if (clickButtonByText([/^validate$/, /^confirm$/, /^pay$/, /^payment$/, /^print$/, /رسید/])) {
            return true;
        }
        if (this.tijaraOrderlines().length) {
            return this.tijaraGoPayment();
        }
        this.tijaraFocusProductSearch();
        return true;
    },

    async tijaraPrintCurrentReceipt() {
        if (typeof this.printReceipt === "function") {
            await this.printReceipt({ order: this.getOrder?.() });
            return true;
        }
        return clickButtonByText([/^print$/, /receipt/, /رسید/]);
    },

    tijaraStartNewOrder() {
        if (typeof this.addNewOrder === "function") {
            this.addNewOrder();
            return true;
        }
        if (typeof this.add_new_order === "function") {
            this.add_new_order();
            return true;
        }
        return clickButtonByText([/new order/, /new sale/, /نیا/]);
    },

    tijaraCycleAudience() {
        const order = this.getOrder?.();
        if (!order?.tijaraSetAudience) {
            return false;
        }
        const canB2B = this.config?.tijara_allow_b2b;
        const canB2C = this.config?.tijara_allow_b2c !== false;
        if (!canB2B || !canB2C) {
            return false;
        }
        const nextAudience = order.tijara_audience === "b2b" ? "b2c" : "b2b";
        order.tijaraSetAudience(nextAudience);
        this.tijaraNotify(nextAudience === "b2b" ? _t("B2B pricing selected.") : _t("B2C pricing selected."));
        return true;
    },

    tijaraCycleOrderType() {
        const order = this.getOrder?.();
        if (!order?.tijaraSetOrderType) {
            return false;
        }
        const currentIndex = Math.max(0, ORDER_TYPES.indexOf(order.tijara_order_type));
        const nextType = ORDER_TYPES[(currentIndex + 1) % ORDER_TYPES.length];
        order.tijaraSetOrderType(nextType);
        this.tijaraNotify(_t("Service mode changed."));
        return true;
    },
});
