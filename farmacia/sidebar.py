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
        "menu": "Fila de Farmácia",
        "role": "list_filafarmacia",
        "route": "list_filafarmacia",
    },
    {
        "icon": "medication",
        "menu": "Dispensas",
        "role": "list_dispensa",
        "route": "list_dispensa",
    },
]
}]
