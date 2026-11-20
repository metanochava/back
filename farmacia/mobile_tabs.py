# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "Pharmacy counter", "icon": "point_of_sale", "route": "farmacia_counter", "permission": "add_countersale", "order": 5},
    {"label": "Pharmacy Queue", "icon": "fact_check", "route": "list_filafarmacia", "permission": "list_filafarmacia", "order": 6},
    {"label": "Dispensations", "icon": "medication", "route": "list_dispensa", "permission": "list_dispensa", "order": 7},
    {"label": "Online orders", "icon": "shopping_bag", "route": "farmacia_online_orders", "permission": "list_onlineorder", "order": 8},
]
