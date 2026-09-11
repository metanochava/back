"""Perfis (Group templates) do módulo inventory - mesmo mecanismo de
saude/profiles.py (group_creator()).

inventory ainda não tinha nenhum mecanismo de perfis (confirmado -
apps.py só ligava create_inventory_dashboard_permissions). Não inclui
'Procurement Officer': não existe nenhum modelo de encomenda/compra em
inventory (só Product/StockItem/StockMovement/Warehouse/
InventoryCount) - criar essa permissão seria inventar uma
funcionalidade que o módulo não tem.
"""

INVENTORY_PROFILES = [
    {
        "name": "Inventory Manager",
        "permissions": [
            "view_product", "add_product", "change_product", "list_product",
            "view_stockitem", "list_stockitem",
            "view_stockmovement", "add_stockmovement", "list_stockmovement",
            "view_warehouse", "add_warehouse", "change_warehouse", "list_warehouse",
            "view_inventorycount", "add_inventorycount", "change_inventorycount",
            "view_inventorycountline", "add_inventorycountline",
            "view_dashboard_inventory", "view_consolidated_dashboard_inventory",
        ],
    },
    {
        "name": "Inventory Controller",
        "permissions": [
            "view_product", "list_product",
            "view_stockitem", "list_stockitem",
            "view_inventorycount", "add_inventorycount", "change_inventorycount",
            "view_inventorycountline", "add_inventorycountline",
            "view_dashboard_inventory",
        ],
    },
    {
        "name": "Warehouse Manager",
        "permissions": [
            "view_product", "list_product",
            "view_stockitem", "list_stockitem",
            "view_stockmovement", "add_stockmovement", "list_stockmovement",
            "view_warehouse", "change_warehouse",
            "view_dashboard_inventory",
        ],
    },
    {
        "name": "Warehouse Supervisor",
        "permissions": [
            "view_product", "view_stockitem", "view_stockmovement", "add_stockmovement",
            "view_warehouse",
        ],
    },
    {
        "name": "Storekeeper",
        "permissions": ["view_product", "view_stockitem", "view_stockmovement", "add_stockmovement"],
    },
    {
        "name": "Receiving Clerk",
        "permissions": ["view_product", "view_warehouse", "add_stockmovement"],
    },
    {
        "name": "Stock Clerk",
        "permissions": ["view_product", "view_stockitem"],
    },
]
