"""Configuração declarativa do dashboard da app 'hr' - só metadados,
sem queries (ver dashboard_providers.py). Um subconjunto representativo
das métricas já existentes no mecanismo antigo (views/dashboard.py's 8
secções via TenantDashboardAPIView), agora também disponível como um
único dashboard do motor novo (saas/core/dashboards/) - as 8 páginas
antigas continuam a existir e a funcionar sem alteração."""

from hr import dashboard_providers  # noqa: F401

DASHBOARD = {
    "schema_version": "1.0",

    "name": "hr",
    "label": "HR",
    "icon": "mdi-account-group-outline",
    "route": "dashboard_hr",
    "order": 20,

    "visible": True,

    # Sem 'permission' própria: cada widget declara a permissão da
    # secção antiga equivalente (view_dashboard_hr_*, já existentes) -
    # mesma política "sem permission = autorizado por omissão" do
    # dashboard demo, aplicada aqui ao nível do dashboard porque as
    # métricas vêm de secções com permissões distintas entre si.
    "permission": None,

    "layout": {
        "columns": 12,
        "gap": "md",
        "dense": False,
    },

    "refresh": {
        "enabled": False,
        "interval": 300,
    },

    "filters": [],

    "widgets": [
        {
            "name": "headcount_total",
            "type": "stat",
            "label": "Employees",
            "icon": "mdi-account-group",
            "color": "primary",

            "provider": "hr.headcount_total",

            "permissions": ["view_dashboard_hr_organizacao"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3, "lg": 3, "xl": 3},
            "order": 10,

            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "pending_leave_approvals",
            "type": "stat",
            "label": "Pending Leave",
            "icon": "mdi-calendar-clock",
            "color": "warning",

            "provider": "hr.pending_leave_approvals",

            "permissions": ["view_dashboard_hr_ausencias"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3, "lg": 3, "xl": 3},
            "order": 20,

            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "today_attendance",
            "type": "stat",
            "label": "Today's Attendance",
            "icon": "mdi-clock-check-outline",
            "color": "positive",

            "provider": "hr.today_attendance",

            "permissions": ["view_dashboard_hr_tempo_presenca"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3, "lg": 3, "xl": 3},
            "order": 30,

            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "open_payroll_periods",
            "type": "stat",
            "label": "Open Payroll Periods",
            "icon": "mdi-cash-multiple",
            "color": "secondary",

            "provider": "hr.open_payroll_periods",

            "permissions": ["view_dashboard_hr_salario_folha"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3, "lg": 3, "xl": 3},
            "order": 40,

            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "upcoming_holidays",
            "type": "table",
            "label": "Upcoming Holidays",

            "provider": "hr.upcoming_holidays",

            "permissions": ["view_dashboard_hr_tempo_presenca"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12},
            "order": 50,

            "accepts_filters": [],
            "filters": [],
        },
    ],
}
