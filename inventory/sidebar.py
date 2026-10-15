ALL = [{
'MENU' : "Inventory",
'ICON' : "inventory_2",

'SUBMENUS' : [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_dashboard_inventory",
        "route": "view_inventory_dashboard",
    },

    # 📦 CATÁLOGO
    {
        "icon": "inventory_2",
        "menu": "Products",
        "role": "list_product",
        "route": "list_product",
    },
    {
        "icon": "category",
        "menu": "Product Categories",
        "role": "list_productcategory",
        "route": "list_productcategory",
    },
    {
        "icon": "sell",
        "menu": "Price lists",
        "role": "list_pricelist",
        "route": "list_pricelist",
    },
    {
        "icon": "price_change",
        "menu": "Prices",
        "role": "list_pricelistitem",
        "route": "list_pricelistitem",
    },
    {
        "icon": "warehouse",
        "menu": "Warehouses",
        "role": "list_warehouse",
        "route": "list_warehouse",
    },

    # 📊 STOCK
    {
        "icon": "inventory",
        "menu": "Stock Balance",
        "role": "list_stockitem",
        "route": "list_stockitem",
    },
    {
        "icon": "receipt_long",
        "menu": "Stock Movements",
        "role": "list_stockmovement",
        "route": "list_stockmovement",
    },
    {
        "icon": "lock",
        "menu": "Stock reservations",
        "role": "list_stockreservation",
        "route": "list_stockreservation",
    },
    {
        "icon": "qr_code_2",
        "menu": "Lots",
        "role": "list_batch",
        "route": "list_batch",
    },
    {
        "icon": "event_busy",
        "menu": "Expiring lots",
        "role": "expiring_batch",
        "route": "view_expiring_batches",
    },
    {
        "icon": "fact_check",
        "menu": "Physical Counts",
        "role": "list_inventorycount",
        "route": "list_inventorycount",
    },

    # ⚙️ CONFIGURAÇÃO
    {
        "icon": "settings",
        "menu": "Settings",
        "role": "list_inventorysetting",
        "route": "list_inventorysetting",
    },
]}]
