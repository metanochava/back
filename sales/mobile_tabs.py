# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "Point of sale", "icon": "point_of_sale", "route": "add_sale", "permission": "add_sale", "order": 15},
    {"label": "Sales", "icon": "receipt_long", "route": "list_sale", "permission": "list_sale", "order": 40},
    {"label": "Customers", "icon": "groups", "route": "list_customer", "permission": "list_customer", "order": 60},
]
