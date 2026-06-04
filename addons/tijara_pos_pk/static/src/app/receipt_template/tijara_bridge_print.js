import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

function hasTijaraBridgePrinter(order) {
    return Boolean(order?.config?.tijara_receipt_printer_device_id);
}

function receiptPayloadFromElement(el, order, basicReceipt) {
    const receiptRoot = el?.querySelector?.(".pos-receipt") || el;
    return {
        basic_receipt: Boolean(basicReceipt),
        ticket_html: receiptRoot?.outerHTML || el?.outerHTML || "",
        ticket_text: receiptRoot?.textContent?.trim() || el?.textContent?.trim() || "",
        document_number: order?.name || "",
        barcode_value: order?.tijaraInvoiceBarcode || "",
    };
}

patch(PosStore.prototype, {
    async printReceipt(options = {}) {
        const order = options.order || this.getOrder();
        if (!hasTijaraBridgePrinter(order)) {
            return await super.printReceipt(...arguments);
        }

        const previousDevice = this.printer.device;
        this.printer.setPrinter({
            printReceipt: async (el) => {
                const payload = receiptPayloadFromElement(el, order, options.basic);
                const result = await this.data.call("pos.order", "action_tijara_print_receipt_to_bridge", [
                    [order.id],
                    payload,
                ]);
                if (result?.successful) {
                    const acceptedLabel = result.job_id || _t("accepted");
                    this.notification.add(
                        `${_t("Receipt sent to Tijara bridge")}: ${acceptedLabel}`,
                        { type: "success" }
                    );
                    return { successful: true, bridgeJobId: result.job_id };
                }
                return {
                    successful: false,
                    canRetry: true,
                    message: result?.message || {
                        title: _t("Tijara Bridge Printer"),
                        body: _t("The local bridge did not accept the receipt print job."),
                    },
                };
            },
        });
        try {
            return await super.printReceipt(...arguments);
        } finally {
            this.printer.setPrinter(previousDevice || null);
        }
    },
});
