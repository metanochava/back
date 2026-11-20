# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "My virtual machines", "icon": "terminal", "route": "view_own_virtualmachine", "permission": "view_own_virtualmachine", "order": 35},
    {"label": "Lab sessions", "icon": "co_present", "route": "list_labsession", "permission": "list_labsession", "order": 45},
]
