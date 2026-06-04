import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models/base";

export class TijaraReceiptProfile extends Base {
    static pythonModel = "tijara.receipt.profile";
}

registry.category("pos_available_models").add(TijaraReceiptProfile.pythonModel, TijaraReceiptProfile);
