"""Configuração declarativa do dashboard 'farmacia' (motor genérico -
django_resaas.engine.core.dashboards). Só metadados - toda a lógica
vive em farmacia/dashboard_providers.py.

farmacia não tinha nenhum dashboard (nem o antigo
TenantDashboardAPIView) - primeiro dashboard deste módulo. 6 dos 7
tipos de widget (sem 'calendar' - Dispensa é um registo pontual sem
duração, não um evento agendado; forçar aqui seria inventar semântica
que o modelo não tem). Modelos reais usados: FilaFarmacia, Dispensa -
nenhum campo inventado.

'permission' reutiliza o codename 'view_farmacia_dashboard' já
referenciado em farmacia/sidebar.py - ver farmacia/signals.py para a
nota sobre essa permissão nunca ter sido criada até agora.
"""

from farmacia import dashboard_providers  # noqa: F401  (regista os providers)

DASHBOARD = {
    "schema_version": "1.0",

    "name": "farmacia",
    "label": "Farmácia",
    "icon": "local_pharmacy",
    "route": "dashboard_farmacia",
    "order": 40,

    "visible": True,

    "permission": "view_farmacia_dashboard",

    "layout": {"columns": 12, "gap": "md", "dense": False},

    "refresh": {"enabled": False, "interval": 300},

    "filters": [
        {
            "name": "period",
            "type": "date_range",
            "label": "Período",
            "scope": "global",
        },
    ],

    "widgets": [
        {
            "name": "fila_pendente",
            "type": "stat",
            "label": "Fila pendente",
            "icon": "fact_check",
            "color": "warning",
            "provider": "farmacia.pending_queue",
            "permissions": ["view_farmacia_dashboard"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3},
            "order": 10,
            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "fila_por_estado",
            "type": "bar_chart",
            "label": "Fila por estado",
            "provider": "farmacia.queue_by_status",
            "permissions": ["view_farmacia_dashboard"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6},
            "order": 20,
            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "dispensas_por_dia",
            "type": "line_chart",
            "label": "Dispensas por dia",
            "provider": "farmacia.dispensations_by_day",
            "permissions": ["view_farmacia_dashboard"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6},
            "order": 30,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "dispensas_por_estado",
            "type": "pie_chart",
            "label": "Dispensas por estado",
            "provider": "farmacia.dispensations_by_status",
            "permissions": ["view_farmacia_dashboard"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4},
            "order": 40,
            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "fila_pendente_tabela",
            "type": "table",
            "label": "Fila pendente",
            "provider": "farmacia.pending_queue_table",
            "permissions": ["view_farmacia_dashboard"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 8},
            "order": 50,
            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "dispensas_recentes",
            "type": "list",
            "label": "Dispensas recentes",
            "provider": "farmacia.recent_dispensations",
            "permissions": ["view_farmacia_dashboard"],
            "permission_mode": "all",
            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4},
            "order": 60,
            "accepts_filters": [],
            "filters": [],
        },
    ],
}
