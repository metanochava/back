"""Configuração declarativa do dashboard 'sales' (motor genérico -
django_resaas.saas.core.dashboards). Só metadados - toda a lógica
vive em sales/dashboard_providers.py.

6 dos 7 tipos de widget (sem 'calendar' - sales não tem nenhum
conceito de evento agendado). Modelos reais usados: Sale, SaleItem,
Payment, Customer - nenhum campo inventado.

Reutiliza a permissão já existente 'view_dashboard_sales'
(sales/signals.py's DASHBOARD_PERMISSIONS, já concedida a Root).
"""

from sales import dashboard_providers  # noqa: F401  (regista os providers)

DASHBOARD = {
    "schema_version": "1.0",

    "name": "sales",
    "label": "Sales",
    "icon": "point_of_sale",
    "route": "dashboard_sales",
    "order": 30,

    "visible": True,

    "permission": "view_dashboard_sales",

    "layout": {"columns": 12, "gap": "md", "dense": False},

    "refresh": {"enabled": False, "interval": 300},

    "filters": [
        {
            "name": "period",
            "type": "date_range",
            "label": "Period",
            "scope": "global",
        },
    ],

    "widgets": [
        {
            "name": "resumo_periodo",
            "type": "stat",
            "label": "Revenue for the Period",
            "icon": "payments",
            "color": "positive",
            "provider": "sales.period_summary",
            "permissions": ["view_dashboard_sales"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3},
            "order": 10,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "vendas_por_estado",
            "type": "bar_chart",
            "label": "Sales by Status",
            "provider": "sales.sales_by_status",
            "permissions": ["view_dashboard_sales"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6},
            "order": 20,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "receita_por_dia",
            "type": "line_chart",
            "label": "Revenue per Day",
            "provider": "sales.revenue_by_day",
            "permissions": ["view_dashboard_sales"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6},
            "order": 30,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "pagamentos_por_forma",
            "type": "pie_chart",
            "label": "Payments by Method",
            "provider": "sales.payments_by_method",
            "permissions": ["view_dashboard_sales"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4},
            "order": 40,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "top_produtos",
            "type": "table",
            "label": "Top Selling Products",
            "provider": "sales.top_products",
            "permissions": ["view_dashboard_sales"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 8},
            "order": 50,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "vendas_recentes",
            "type": "list",
            "label": "Recent Sales",
            "provider": "sales.recent_sales",
            "permissions": ["view_dashboard_sales"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4},
            "order": 60,
            "accepts_filters": [],
            "filters": [],
        },
    ],
}
