"""Perfis (Group templates) do módulo sales - mesmo mecanismo de
saude/profiles.py (group_creator(), ver engine/core/utils/
group_creator.py).

sales/apps.py chamava group_creator() com a lista CLÍNICA da saúde
copiada por engano ("Médico Geral", "Farmacêutico", etc. dentro de
Vendas) - substituído por perfis reais de vendas. Sem rename_from: os
nomes antigos nunca pertenceram de facto a sales (Group.name é único
globalmente - o group_creator() de sales só estava a religar os
MESMOS Groups que saude já cria, não a criar duplicados), por isso não
há nada para migrar aqui, só corrigir a lista usada daqui para a
frente.

Perfis financeiros genéricos (Finance Manager/Accountant/Treasurer/
Auditor) são deliberadamente os MESMOS nomes que saude/profiles.py usa
- CLAUDE.md "avoid role explosion": um "Accountant" não precisa de
uma variante por módulo, os módulos activos e as permissões
concedidas é que definem o que vê.
"""

SALES_PROFILES = [
    {
        "name": "Sales Manager",
        "permissions": [
            "view_sale", "add_sale", "change_sale", "list_sale",
            "view_saleitem", "add_saleitem", "list_saleitem",
            "view_customer", "add_customer", "change_customer", "list_customer",
            "view_payment", "add_payment", "list_payment",
            "view_dashboard_sales",
        ],
    },
    {
        "name": "Sales Representative",
        "permissions": [
            "view_sale", "add_sale", "change_sale", "list_sale",
            "view_saleitem", "add_saleitem",
            "view_customer", "add_customer", "list_customer",
        ],
    },
    {
        "name": "Cashier",
        "permissions": ["view_sale", "add_sale", "view_payment", "add_payment"],
    },
    {
        "name": "Customer Service Representative",
        "permissions": [
            "view_customer", "add_customer", "change_customer", "list_customer",
            "view_customercontact", "add_customercontact",
        ],
    },
    {"name": "Finance Manager", "permissions": ["view_sale", "view_payment", "view_dashboard_sales"]},
    {"name": "Accountant", "permissions": ["view_sale", "view_payment", "view_dashboard_sales"]},
    {"name": "Treasurer", "permissions": ["view_payment", "add_payment"]},
    {
        "name": "Auditor",
        "permissions": [
            "view_sale", "view_saleitem", "view_payment", "view_customer",
            "view_dashboard_sales",
        ],
    },
]
