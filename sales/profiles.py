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

# the point of sale (SaleSEPage): one checkout, then the payments; it lists
# the customers, the catalogued items and their categories and (with
# inventory) the warehouses; the same capability opens and runs the tabs
POINT_OF_SALE = ["checkout_sale", "pagar_sale", "list_customer", "list_product", "list_productcategory",
                 "list_warehouse"]

SALES_PROFILES = [
    {
        "name": "Sales Manager",
        "permissions": [
            "view_sale", "add_sale", "change_sale", "list_sale",
            "view_saleitem", "add_saleitem", "list_saleitem",
            "view_customer", "add_customer", "change_customer", "list_customer",
            "view_payment", "add_payment", "list_payment",
            "view_dashboard_sales",
            "view_tax", "list_tax", "add_tax", "change_tax", "delete_tax",
            "reservar_sale", "preco_sale",
            *POINT_OF_SALE, "confirmar_sale", "anular_sale", "disponibilidade_sale", "discount_sale",
        ],
    },
    {
        "name": "Sales Representative",
        "permissions": [
            "view_sale", "add_sale", "change_sale", "list_sale",
            "view_saleitem", "add_saleitem",
            "view_customer", "add_customer", "list_customer",
            "view_tax", "list_tax",
            "reservar_sale", "preco_sale",
            *POINT_OF_SALE, "confirmar_sale", "disponibilidade_sale",
        ],
    },
    {
        "name": "Cashier",
        # the point of sale: check the cart out, take the payment, void a sale
        # the customer walked away from
        "permissions": ["view_sale", "add_sale", "view_payment", "add_payment", "view_tax", "list_tax",
                        *POINT_OF_SALE, "anular_sale"],
    },
    {
        "name": "Customer Service Representative",
        "permissions": [
            "view_customer", "add_customer", "change_customer", "list_customer",
            "view_customercontact", "add_customercontact",
        ],
    },
    {"name": "Finance Manager", "permissions": ["view_sale", "view_payment", "view_dashboard_sales"]},
    {"name": "Accountant", "permissions": ["view_sale", "view_payment", "view_dashboard_sales", "view_tax", "list_tax"]},
    {"name": "Treasurer", "permissions": ["view_payment", "add_payment"]},
    {
        "name": "Auditor",
        "permissions": [
            "view_sale", "view_saleitem", "view_payment", "view_customer",
            "view_dashboard_sales",
        ],
    },
]

# the Entity's "Admin" (django_resaas saas/profiles.py; group_creator() is
# additive by name) also sells and gives discounts at the point of sale
SALES_PROFILES += [
    {"name": "Admin", "permissions": [*POINT_OF_SALE, "confirmar_sale", "anular_sale", "disponibilidade_sale",
                                      "discount_sale"]},
]
