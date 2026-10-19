ALL = [{
'MENU' : "Farmacia",
'ICON' : "local_pharmacy",
'SUBMENUS' : [
    {
        "menu": "Dashboard",
        "icon": "dashboard",
        "role": "view_farmacia_dashboard",
        "route": "view_farmacia_dashboard",
    },

    # 💊 FILA / DISPENSAÇÃO
    {
        "icon": "fact_check",
        "menu": "Pharmacy Queue",
        "role": "list_filafarmacia",
        "route": "list_filafarmacia",
    },
    {
        "icon": "medication",
        "menu": "Dispensations",
        "role": "list_dispensa",
        "route": "list_dispensa",
    },

    # 🛒 MARKETPLACE
    {
        "icon": "travel_explore",
        "menu": "Online pharmacy",
        "role": "view_medicinecatalogitem",
        "route": "farmacia_marketplace",
    },
    {
        "icon": "storefront",
        "menu": "Marketplace listing",
        "role": "list_pharmacylisting",
        "route": "list_pharmacylisting",
    },
    {
        "icon": "sell",
        "menu": "Marketplace offers",
        "role": "list_pharmacyoffer",
        "route": "list_pharmacyoffer",
    },
    {
        "icon": "menu_book",
        "menu": "Medicine catalogue",
        "role": "list_medicinecatalogitem",
        "route": "list_medicinecatalogitem",
    },
    {
        "icon": "point_of_sale",
        "menu": "Pharmacy counter",
        "role": "add_countersale",
        "route": "farmacia_counter",
    },
    {
        "icon": "person_search",
        "menu": "Find patient",
        "role": "lookup_patient_filafarmacia",
        "route": "farmacia_patient_lookup",
    },
    {
        "icon": "shopping_bag",
        "menu": "Online orders",
        "role": "list_onlineorder",
        "route": "farmacia_online_orders",
    },
]
}]
