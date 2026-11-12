# the catalog module's menu: what the Entity sells or buys (was under Inventory)
ALL = [{
'MENU' : "Catalog",
'ICON' : "category",

'SUBMENUS' : [
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
]
}]
