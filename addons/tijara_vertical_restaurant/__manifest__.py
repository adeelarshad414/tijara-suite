{
    "name": "Tijara Vertical Restaurant",
    "summary": "Restaurant table and kitchen ticket foundation",
    "version": "19.0.1.0.0",
    "category": "Tijara/Verticals",
    "author": "Tijara Suite",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "tijara_retail_core"],
    "data": [
        "security/ir.model.access.csv",
        "views/restaurant_table_views.xml",
        "views/service_profile_views.xml",
        "views/kitchen_ticket_views.xml",
    ],
    "installable": True,
    "application": False,
}
