MENU = "Stock"
ICON = "inventory_2"

SUBMENUS = [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_dashboard_inventory",
        "route": "view_inventory_dashboard",
    },

    # 📦 CATÁLOGO
    {
        "icon": "inventory_2",
        "menu": "Produtos",
        "role": "list_product",
        "route": "list_product",
    },
    {
        "icon": "category",
        "menu": "Categorias de Produto",
        "role": "list_productcategory",
        "route": "list_productcategory",
    },
    {
        "icon": "warehouse",
        "menu": "Armazéns",
        "role": "list_warehouse",
        "route": "list_warehouse",
    },

    # 📊 STOCK
    {
        "icon": "inventory",
        "menu": "Saldo de Stock",
        "role": "list_stockitem",
        "route": "list_stockitem",
    },
    {
        "icon": "receipt_long",
        "menu": "Movimentos de Stock",
        "role": "list_stockmovement",
        "route": "list_stockmovement",
    },
    {
        "icon": "fact_check",
        "menu": "Contagens Físicas",
        "role": "list_inventorycount",
        "route": "list_inventorycount",
    },

    # ⚙️ CONFIGURAÇÃO
    {
        "icon": "settings",
        "menu": "Configurações",
        "role": "list_inventorysetting",
        "route": "list_inventorysetting",
    },
]
