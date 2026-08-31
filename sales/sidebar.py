MENU = "Vendas"
ICON = "point_of_sale"

SUBMENUS = [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_dashboard_sales",
        "route": "view_sales_dashboard",
    },

    # 🛒 VENDAS
    {
        "add_role": "add_sale",
        "add_route": "add_sale",
        "icon": "point_of_sale",
        "menu": "Vendas",
        "role": "list_sale",
        "route": "list_sale",
    },
    {
        "icon": "payments",
        "menu": "Pagamentos",
        "role": "list_payment",
        "route": "list_payment",
    },

    # 👤 CLIENTES
    {
        "icon": "groups",
        "menu": "Clientes",
        "role": "list_customer",
        "route": "list_customer",
    },
    {
        "icon": "contact_phone",
        "menu": "Contactos de Cliente",
        "role": "list_customercontact",
        "route": "list_customercontact",
    },
]
