import { markup } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { generateQRCodeDataUrl } from "@point_of_sale/utils";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

const TOKEN_PATTERN = /{{\s*([a-zA-Z0-9_]+)\s*}}/g;

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.tijara_fbr_invoice_number = vals.tijara_fbr_invoice_number || false;
        this.tijara_fbr_qr_payload = vals.tijara_fbr_qr_payload || false;
        this.tijara_invoice_barcode = vals.tijara_invoice_barcode || false;
        this.tijara_exchange_origin_ref = vals.tijara_exchange_origin_ref || false;
        this.tijara_is_refund_exchange = vals.tijara_is_refund_exchange || false;
    },

    get tijaraInvoiceBarcode() {
        return this.tijara_invoice_barcode || `TJINV:${this.tijara_fbr_invoice_number || this.name || this.id || ""}`;
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data.tijara_fbr_invoice_number = this.tijara_fbr_invoice_number || false;
        data.tijara_fbr_qr_payload = this.tijara_fbr_qr_payload || false;
        data.tijara_exchange_origin_ref = this.tijara_exchange_origin_ref || false;
        data.tijara_is_refund_exchange = Boolean(this.tijara_is_refund_exchange);
        return data;
    },
});

patch(OrderReceipt.prototype, {
    get tijaraProfile() {
        const configuredProfile = this.order.config?.tijara_receipt_profile_id;
        if (configuredProfile) {
            return configuredProfile;
        }
        return this.order.models?.["tijara.receipt.profile"]?.find(
            (profile) => profile.template_scope === "pos_receipt" && profile.active !== false
        );
    },

    tijaraShow(fieldName, fallback = true) {
        const profile = this.tijaraProfile;
        return profile ? Boolean(profile[fieldName]) : fallback;
    },

    get tijaraTitleEnglish() {
        return this.tijaraProfile?.receipt_title_english || "";
    },

    get tijaraTitleUrdu() {
        return this.tijaraProfile?.receipt_title_urdu || "";
    },

    get tijaraHeaderEnglish() {
        return this.tijaraProfile?.header_english || "";
    },

    get tijaraHeaderUrdu() {
        return this.tijaraProfile?.header_urdu || "";
    },

    get tijaraTermsEnglish() {
        return this.tijaraProfile?.terms_english || "";
    },

    get tijaraTermsUrdu() {
        return this.tijaraProfile?.terms_urdu || "";
    },

    get tijaraFooterEnglish() {
        return this.tijaraProfile?.footer_english || "";
    },

    get tijaraFooterUrdu() {
        return this.tijaraProfile?.footer_urdu || "";
    },

    get tijaraCustomCss() {
        return this.tijaraProfile?.custom_css || "";
    },

    get tijaraCustomBody() {
        const html = this.tijaraProfile?.custom_body_html;
        if (!html) {
            return "";
        }
        return markup(
            html.replace(TOKEN_PATTERN, (_match, key) =>
                escapeHtml(this.tijaraTemplateTokens[key] ?? "")
            )
        );
    },

    get tijaraTemplateTokens() {
        return {
            document_number: this.order.name || "",
            document_date: this.order.date_order?.toFormat?.("yyyy-LL-dd HH:mm") || "",
            customer_name: this.order.getPartnerName?.() || "Walk-in",
            cashier_name: this.order.getCashierName?.() || "",
            company_name: this.order.company?.name || "",
            amount_total: this.formatCurrency(this.order.priceIncl || this.order.amount_total || 0),
            amount_tax: this.formatCurrency(this.order.amount_tax || 0),
            barcode_value: this.tijaraBarcodeValue,
            fbr_invoice_number: this.order.tijara_fbr_invoice_number || "",
            sale_type: this.order.tijaraAudienceLabel || "",
            service_mode: this.order.tijaraOrderTypeLabel || "",
            pickup_code: this.order.tijara_pickup_code || "",
        };
    },

    get tijaraBarcodeValue() {
        const profile = this.tijaraProfile;
        if (!profile) {
            return this.order.tijaraInvoiceBarcode;
        }
        if (profile.barcode_source === "custom") {
            return profile.custom_barcode_value || "";
        }
        if (profile.barcode_source === "order_name") {
            return this.order.name || "";
        }
        if (profile.barcode_source === "fbr_invoice_number") {
            return this.order.tijara_fbr_invoice_number || this.order.name || "";
        }
        return this.order.tijaraInvoiceBarcode;
    },

    get tijaraBarcodeUrl() {
        const value = this.tijaraBarcodeValue;
        if (!value) {
            return "";
        }
        return `/report/barcode/Code128/${encodeURIComponent(value)}?width=600&height=120`;
    },

    get tijaraQrUrl() {
        const value = this.order.tijara_fbr_qr_payload || this.tijaraBarcodeValue;
        return value ? generateQRCodeDataUrl(value) : "";
    },

    get tijaraCustomerName() {
        return this.order.getPartnerName?.() || "Walk-in";
    },

    get tijaraServiceMode() {
        return this.order.tijaraOrderTypeLabel || "";
    },

    get tijaraSaleType() {
        return this.order.tijaraAudienceLabel || "";
    },
});
