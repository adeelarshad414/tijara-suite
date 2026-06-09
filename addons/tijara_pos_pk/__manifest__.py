{
    "name": "Tijara POS Pakistan",
    "summary": "Pakistan POS receipts, QR payloads, and FBR integration queue foundation",
    "version": "19.0.1.0.0",
    "category": "Tijara",
    "author": "Tijara Suite",
    "license": "LGPL-3",
    "depends": ["account", "point_of_sale", "tijara_retail_core"],
    "data": [
        "security/ir.model.access.csv",
        "data/fbr_cron.xml",
        "report/tijara_receipt_reports.xml",
        "views/fbr_invoice_queue_views.xml",
        "views/receipt_profile_views.xml",
        "views/pos_config_views.xml",
        "views/pos_order_views.xml",
        "views/account_move_views.xml",
        "views/product_template_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "tijara_pos_pk/static/src/app/receipt_template/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
