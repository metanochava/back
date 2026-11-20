ALL = [{
    'MENU': "Hospitality",
    'ICON': "table_bar",

    'SUBMENUS': [
        {"icon": "table_restaurant", "menu": "Tables", "role": "list_diningtable", "route": "list_diningtable"},
        {"icon": "chair", "menu": "Dining areas", "role": "list_diningarea", "route": "list_diningarea"},
        {"icon": "soup_kitchen", "menu": "Kitchen and bar", "role": "kitchen_prepticket", "route": "view_kitchen"},
        {"icon": "receipt", "menu": "Table orders", "role": "list_tableorder", "route": "list_tableorder"},
        {"icon": "notifications_active", "menu": "Table requests", "role": "list_tablerequest", "route": "list_tablerequest"},
        {"icon": "outdoor_grill", "menu": "Preparation stations", "role": "list_prepstation", "route": "list_prepstation"},
    ],
}]
