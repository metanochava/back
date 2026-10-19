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
            # marketplace: the Branch's listing and offers; the common
            # catalogue is read only (Root writes it)
            "list_medicinecatalogitem", "view_medicinecatalogitem",
            "list_medicinecatalogmedia", "view_medicinecatalogmedia",
            "list_pharmacylisting", "view_pharmacylisting", "add_pharmacylisting", "change_pharmacylisting",
            "list_pharmacyoffer", "view_pharmacyoffer", "add_pharmacyoffer", "change_pharmacyoffer",
            "delete_pharmacyoffer",
            # online orders and the counter (a paper prescription is verified by a person)
            "list_onlineorder", "view_onlineorder", "collect_onlineorder", "cancel_onlineorder",
            "list_countersale", "view_countersale", "add_countersale",
            "lookup_patient_filafarmacia", "enqueue_filafarmacia",
        ],
    },
    {
        "name": "Pharmacist",
        "permissions": [
            "view_filafarmacia", "list_filafarmacia",
            "revisar_filafarmacia", "dispensar_filafarmacia", "concluir_filafarmacia",
            "view_dispensa", "add_dispensa",
            "view_itemdispensa", "add_itemdispensa",
            "list_medicinecatalogitem", "view_medicinecatalogitem",
            "list_medicinecatalogmedia", "view_medicinecatalogmedia",
            "list_pharmacyoffer", "view_pharmacyoffer",
            "list_onlineorder", "view_onlineorder", "collect_onlineorder", "cancel_onlineorder",
            "list_countersale", "view_countersale", "add_countersale",
            "lookup_patient_filafarmacia", "enqueue_filafarmacia",
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
