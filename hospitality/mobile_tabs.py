# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "Tables", "icon": "table_restaurant", "route": "list_diningtable", "permission": "list_diningtable", "order": 10},
    {"label": "Kitchen and bar", "icon": "soup_kitchen", "route": "view_kitchen", "permission": "kitchen_prepticket", "order": 20},
    {"label": "Table requests", "icon": "notifications_active", "route": "list_tablerequest", "permission": "list_tablerequest", "order": 30},
]
