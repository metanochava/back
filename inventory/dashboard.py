"""Configuração declarativa do dashboard 'inventory' (motor genérico -
django_resaas.engine.core.dashboards). Só metadados - toda a lógica
vive em inventory/dashboard_providers.py.

6 dos 7 tipos de widget (sem 'calendar' - inventory não tem nenhum
conceito de evento agendado; forçar um calendário aqui seria inventar
dados que o domínio não tem). Modelos reais usados: Product, StockItem,
StockMovement, Warehouse - nenhum campo inventado.

Reutiliza a permissão já existente 'view_dashboard_inventory'
(inventory/signals.py's DASHBOARD_PERMISSIONS, já concedida a Root) -
não cria uma nova só porque o motor é novo.
"""

from inventory import dashboard_providers  # noqa: F401  (regista os providers)

DASHBOARD = {
    "schema_version": "1.0",

    "name": "inventory",
    "label": "Inventário",
    "icon": "inventory_2",
    "route": "dashboard_inventory",
    "order": 20,

    "visible": True,

    "permission": "view_dashboard_inventory",

    "layout": {"columns": 12, "gap": "md", "dense": False},

    "refresh": {"enabled": False, "interval": 300},

    "filters": [
        {
            "name": "period",
            "type": "date_range",
            "label": "Período",
            "scope": "global",
        },
        {
            "name": "warehouse",
            "type": "select",
            "label": "Armazém",
            "scope": "global",
            "clearable": True,
            "options_provider": "inventory.warehouse_options",
        },
    ],

    "widgets": [
        {
            "name": "valor_total_stock",
            "type": "stat",
            "label": "Valor total em stock",
            "icon": "payments",
            "color": "primary",
            "provider": "inventory.total_stock_value",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3},
            "order": 10,
            "accepts_filters": ["warehouse"],
            "filters": [],
        },
        {
            "name": "valor_por_armazem",
            "type": "bar_chart",
            "label": "Valor em stock por armazém",
            "provider": "inventory.value_by_warehouse",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6},
            "order": 20,
            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "movimentos_por_dia",
            "type": "line_chart",
            "label": "Movimentos por dia",
            "provider": "inventory.movements_by_day",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6},
            "order": 30,
            "accepts_filters": ["period", "warehouse"],
            "filters": [],
        },
        {
            "name": "movimentos_por_tipo",
            "type": "pie_chart",
            "label": "Movimentos por tipo",
            "provider": "inventory.movements_by_type",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4},
            "order": 40,
            "accepts_filters": ["period", "warehouse"],
            "filters": [],
        },
        {
            "name": "produtos_abaixo_minimo",
            "type": "table",
            "label": "Produtos abaixo do stock mínimo",
            "provider": "inventory.products_below_minimum",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 8},
            "order": 50,
            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "movimentos_recentes",
            "type": "list",
            "label": "Movimentos recentes",
            "provider": "inventory.recent_movements",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4},
            "order": 60,
            "accepts_filters": ["warehouse"],
            "filters": [],
        },
    ],
}
