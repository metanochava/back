# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "Stock Balance", "icon": "inventory", "route": "list_stockitem", "permission": "list_stockitem", "order": 50},
]
