"""Configuração declarativa do dashboard 'inventory' (motor genérico -
django_resaas.saas.core.dashboards). Só metadados - toda a lógica
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
    "label": "Inventory",
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
            "label": "Period",
            "scope": "global",
        },
        {
            "name": "warehouse",
            "type": "select",
            "label": "Warehouse",
            "scope": "global",
            "clearable": True,
            "options_provider": "inventory.warehouse_options",
        },
    ],

    "widgets": [
        {
            "name": "valor_total_stock",
            "type": "stat",
            "label": "Total Stock Value",
            "icon": "payments",
            "color": "primary",
            "provider": "inventory.total_stock_value",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 12},
            "order": 10,
            "accepts_filters": ["warehouse"],
            "filters": [],
        },
        {
            "name": "valor_por_armazem",
            "type": "bar_chart",
            "label": "Stock Value by Warehouse",
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
            "label": "Movements per Day",
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
            "label": "Movements by Type",
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
            "label": "Products Below Minimum Stock",
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
            "label": "Recent Movements",
            "provider": "inventory.recent_movements",
            "permissions": ["view_dashboard_inventory"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 12},
            "order": 60,
            "accepts_filters": ["warehouse"],
            "filters": [],
        },
    ],
}
