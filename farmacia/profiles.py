"""Perfis (Group templates) do módulo farmacia - mesmo mecanismo de
saude/profiles.py (group_creator()).

'Pharmacist' e 'Pharmacy Technician' são deliberadamente os MESMOS
nomes já usados em saude/profiles.py - Group.name é único
globalmente, por isso group_creator() reutiliza o MESMO Group e só
acrescenta as permissões de farmacia às que saude já concede (aditivo)
- um farmacêutico que também atenda em contexto clínico fica com o
conjunto combinado automaticamente. Não inclui 'Inventory Controller'/
'Procurement Officer'/'Cashier' (sugeridos genericamente para
farmácia): essas responsabilidades já pertencem a inventory/sales,
farmacia só trata do workflow clínico de dispensação (ver
farmacia/models/filafarmacia.py, itemdispensa.py) - CLAUDE.md #41/#88.
"""

FARMACIA_PROFILES = [
    {
        "name": "Pharmacy Manager",
        "permissions": [
            "view_filafarmacia", "list_filafarmacia", "change_filafarmacia",
            "view_dispensa", "add_dispensa", "list_dispensa",
            "view_itemdispensa", "add_itemdispensa",
            "revisar_filafarmacia", "dispensar_filafarmacia", "concluir_filafarmacia",
            "view_farmacia_dashboard",
        ],
    },
    {
        "name": "Pharmacist",
        "permissions": [
            "view_filafarmacia", "list_filafarmacia",
            "revisar_filafarmacia", "dispensar_filafarmacia", "concluir_filafarmacia",
            "view_dispensa", "add_dispensa",
            "view_itemdispensa", "add_itemdispensa",
        ],
    },
    {
        "name": "Pharmacy Technician",
        "permissions": [
            "view_filafarmacia", "dispensar_filafarmacia",
            "view_dispensa", "add_dispensa",
            "view_itemdispensa", "add_itemdispensa",
        ],
    },
    {
        "name": "Dispensing Assistant",
        "permissions": ["view_filafarmacia", "view_dispensa", "view_itemdispensa"],
    },
]
