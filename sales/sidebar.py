ALL = [{
'MENU' : "Sales",
'ICON' : "point_of_sale",

'SUBMENUS' : [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_dashboard_sales",
        "route": "view_sales_dashboard",
    },

    # 🛒 SALES
    {
        "add_role": "add_sale",
        "add_route": "add_sale",
        "icon": "point_of_sale",
        "menu": "Sales",
        "role": "list_sale",
        "route": "list_sale",
    },
    {
        "icon": "payments",
        "menu": "Payments",
        "role": "list_payment",
        "route": "list_payment",
    },

    # 👤 CUSTOMERS
    {
        "icon": "groups",
        "menu": "Customers",
        "role": "list_customer",
        "route": "list_customer",
    },
    {
        "icon": "contact_phone",
        "menu": "Customer Contacts",
        "role": "list_customercontact",
        "route": "list_customercontact",
    },
]}]