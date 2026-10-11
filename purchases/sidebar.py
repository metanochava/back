ALL = [{
    'MENU': "Purchases",
    'ICON': "shopping_cart",

    'SUBMENUS': [
        {
            "add_role": "add_purchaseorder",
            "add_route": "add_purchaseorder",
            "icon": "receipt_long",
            "menu": "Purchase orders",
            "role": "list_purchaseorder",
            "route": "list_purchaseorder",
        },
        {
            "icon": "move_to_inbox",
            "menu": "Goods receipts",
            "role": "list_goodsreceipt",
            "route": "list_goodsreceipt",
        },
        {
            "icon": "local_shipping",
            "menu": "Suppliers",
            "role": "list_supplier",
            "route": "list_supplier",
        },
    ],
}]
