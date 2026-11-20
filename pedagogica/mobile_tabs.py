# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "My lessons", "icon": "history_edu", "route": "view_own_lesson", "permission": "view_own_lesson", "order": 12},
    {"label": "Digital board", "icon": "draw", "route": "list_lesson", "permission": "list_lesson", "order": 15},
    {"label": "Assignments", "icon": "assignment", "route": "list_assignment", "permission": "list_assignment", "order": 25},
]
