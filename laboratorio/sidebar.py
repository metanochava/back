# the laboratorio module's menu (front/src/modules/laboratorio)
ALL = [{
    'MENU': "Laboratories",
    'ICON': "computer",
    'SUBMENUS': [
        {"icon": "co_present", "menu": "Lab sessions", "role": "list_labsession", "route": "list_labsession"},
        {"icon": "computer", "menu": "My lab sessions", "role": "view_own_labsession", "route": "view_own_labsession"},
        {"icon": "dns", "menu": "Virtual labs", "role": "list_virtuallab", "route": "list_virtuallab"},
        {"icon": "terminal", "menu": "My virtual machines", "role": "view_own_virtualmachine",
         "route": "view_own_virtualmachine"},
        {"icon": "meeting_room", "menu": "Rooms", "role": "list_room", "route": "list_room"},
        {"icon": "desktop_windows", "menu": "Workstations", "role": "list_workstation", "route": "list_workstation"},
        {"icon": "precision_manufacturing", "menu": "Equipment", "role": "list_equipment", "route": "list_equipment"},
        {"icon": "lan", "menu": "Networks", "role": "list_network", "route": "list_network"},
        {"icon": "layers", "menu": "Environments", "role": "list_environment", "route": "list_environment"},
        {"icon": "screen_share", "menu": "Remote accesses", "role": "list_remoteaccesssession",
         "route": "list_remoteaccesssession"},
    ],
}]
