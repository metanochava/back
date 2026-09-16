"""Configuração declarativa do dashboard clínico (motor genérico -
django_resaas.saas.core.dashboards). Só metadados; toda a lógica
vive em saude/dashboard_providers.py (import abaixo é só para os
providers correrem @register_provider antes de qualquer request).

Cobre os 7 tipos de widget do motor, todos com modelos REAIS já
existentes em saude (Paciente, Agenda, Consulta, Person.gender) - não
foi inventado nenhum campo. Ver docs/architecture/dashboards.md para a
justificação de cada escolha.
"""

from saude import dashboard_providers  # noqa: F401  (regista os providers)
from saude.models.agenda import Agenda

# Lista pequena e estável (definida no próprio modelo) - opções
# estáticas resolvidas aqui, sem precisar de nenhum provider (não é
# uma query: só introspecção do Field.choices já declarado na classe).
_ESTADO_OPTIONS = [
    {"value": codigo, "label": label}
    for codigo, label in Agenda._meta.get_field("estado").choices
]

DASHBOARD = {
    "schema_version": "1.0",

    "name": "saude",
    "label": "Clinic",
    "icon": "medical_services",
    "route": "dashboard_saude_clinica",
    "order": 10,

    "visible": True,

    "permission": "view_dashboard_saude_clinica",

    "tooltip": "Clinical overview: active patients, appointments and consultations for the selected period.",

    "layout": {
        "columns": 12,
        "gap": "md",
        "dense": False,
    },

    "refresh": {
        "enabled": False,
        "interval": 300,
    },

    "filters": [
        {
            "name": "period",
            "type": "date_range",
            "label": "Period",
            "scope": "global",
            # Sem 'default' estático - ver dashboard_providers.py's
            # _period_bounds() para porque um "últimos 30 dias"
            # calculado agora não pode viver num dict congelado no
            # arranque do processo.
        },
        {
            "name": "status",
            "type": "select",
            "label": "Status",
            "scope": "global",
            "clearable": True,
            "options": _ESTADO_OPTIONS,
        },
        {
            "name": "search",
            "type": "search",
            "label": "Search patient",
            "scope": "global",
        },
    ],

    "widgets": [
        {
            "name": "total_pacientes",
            "type": "stat",
            "label": "Total Patients",
            "icon": "groups",
            "color": "primary",

            "provider": "saude.total_patients",

            "permissions": ["view_paciente"],
            "permission_mode": "all",

            "tooltip": "Total active patients. Click to open the full list.",

            # primary_action: clicar no cabeçalho do widget abre a
            # lista de pacientes (rota real 'list_paciente',
            # já registada em saude/router.js). 'actions': botão extra
            # no cabeçalho, só visível para quem tem add_paciente -
            # exactamente o cenário "widget visível mas action escondida
            # sem a permissão extra" coberto por
            # test_dashboard_actions.py.
            "primary_action": {
                "name": "open_patients",
                "type": "route",
                "route": {"name": "list_paciente"},
                "permissions": ["view_paciente"],
            },
            "actions": [
                {
                    "name": "add_patient",
                    "type": "route",
                    "icon": "person_add",
                    "tooltip": "Register patient",
                    "route": {"name": "add_paciente"},
                    "permissions": ["add_paciente"],
                },
            ],

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 3, "lg": 3, "xl": 3},
            "order": 10,

            "accepts_filters": ["search"],
            "filters": [],
        },
        {
            "name": "agendas_por_estado",
            "type": "bar_chart",
            "label": "Appointments by Status",

            "provider": "saude.appointments_by_status",

            "permissions": ["view_agenda"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6},
            "order": 20,

            "accepts_filters": ["period", "status"],
            "filters": [],
        },
        {
            "name": "consultas_por_dia",
            "type": "line_chart",
            "label": "Consultations per Day",

            "provider": "saude.consultations_by_day",

            "permissions": ["view_consulta"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6},
            "order": 30,

            "accepts_filters": ["period"],
            "filters": [],
        },
        {
            "name": "pacientes_por_genero",
            "type": "pie_chart",
            "label": "Patients by Gender",

            "provider": "saude.patients_by_gender",

            "permissions": ["view_paciente"],
            "permission_mode": "all",

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4, "lg": 4, "xl": 4},
            "order": 40,

            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "proximas_consultas",
            "type": "table",
            "label": "Appointments",

            "provider": "saude.upcoming_appointments",

            "permissions": ["view_agenda"],
            "permission_mode": "all",

            "tooltip": "Upcoming appointments. Use the row action to open the patient record.",

            # row_actions: cada linha é uma Agenda (marcação), não uma
            # Consulta - por isso a acção da linha aponta para a ficha
            # do PACIENTE (rota real 'view_paciente'), usando
            # 'paciente_id' (campo extra devolvido pelo provider, ver
            # dashboard_providers.py) para resolver {id}. Só visível
            # para quem tem view_paciente, independentemente de ver
            # view_agenda (permissão do próprio widget).
            "row_actions": [
                {
                    "name": "view_patient",
                    "type": "route",
                    "icon": "person",
                    "tooltip": "View patient record",
                    "route": {"name": "view_paciente", "params": {"id": "{paciente_id}"}},
                    "permissions": ["view_paciente"],
                },
            ],

            "visible": True,
            "cols": {"xs": 12, "sm": 12, "md": 8, "lg": 8, "xl": 8},
            "order": 50,

            "accepts_filters": ["status", "search", "medico"],
            # Filtro próprio deste widget (âmbito 'widget', não
            # global): opções dinâmicas e específicas do tenant (a
            # lista de médicos), ao contrário de 'status' acima
            # (lista estática, resolvida em dashboard.py) - caso de
            # uso real para options_provider.
            "filters": [
                {
                    "name": "medico",
                    "type": "autocomplete",
                    "label": "Doctor",
                    "scope": "widget",
                    "clearable": True,
                    "options_provider": "saude.doctor_options",
                },
            ],
        },
        {
            "name": "ultimos_pacientes",
            "type": "list",
            "label": "Recent Patients",

            "provider": "saude.recent_patients",

            "permissions": ["view_paciente"],
            "permission_mode": "all",

            "tooltip": "Recently registered patients. Click an item to open the record.",

            # item_action: um único destino para qualquer item da lista
            # ({id} já vem no dict de cada item, ver
            # UltimosPacientesProvider) - substitui o antigo mecanismo
            # ad-hoc 'item.route' por widget a widget.
            "item_action": {
                "name": "open_patient",
                "type": "route",
                "route": {"name": "view_paciente", "params": {"id": "{id}"}},
                "permissions": ["view_paciente"],
            },

            "visible": True,
            "cols": {"xs": 12, "sm": 6, "md": 4, "lg": 4, "xl": 4},
            "order": 60,

            "accepts_filters": [],
            "filters": [],
        },
        {
            "name": "agenda_calendario",
            "type": "calendar",
            "label": "Appointment Calendar",

            "provider": "saude.appointment_calendar",

            "permissions": ["view_agenda"],
            "permission_mode": "all",

            "tooltip": "Appointment calendar for the period. Click an event to open the patient record.",

            "item_action": {
                "name": "open_patient",
                "type": "route",
                "route": {"name": "view_paciente", "params": {"id": "{paciente_id}"}},
                "permissions": ["view_paciente"],
            },

            "visible": True,
            "cols": {"xs": 12},
            "order": 70,

            "accepts_filters": ["period"],
            "filters": [],
        },
    ],
}
