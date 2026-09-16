ALL = [{
'MENU' : "Farmacia",
'ICON' : "local_pharmacy",
'SUBMENUS' : [
    {
        "menu": "Dashboard",
        "icon": "dashboard",
        "role": "view_farmacia_dashboard",
        "route": "view_farmacia_dashboard",
    },

    # 💊 FILA / DISPENSAÇÃO
    {
        "icon": "fact_check",
        "menu": "Pharmacy Queue",
        "role": "list_filafarmacia",
        "route": "list_filafarmacia",
    },
    {
        "icon": "medication",
        "menu": "Dispensations",
        "role": "list_dispensa",
        "route": "list_dispensa",
    },
]
}]
