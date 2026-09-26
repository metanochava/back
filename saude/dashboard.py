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
            "cols": {"xs": 12, "sm": 12, "md": 12, "lg": 12, "xl": 12},
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
            "cols": {"xs": 12, "sm": 6, "md": 8, "lg": 8, "xl": 8},
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
            "cols": {"xs": 12, "sm": 12, "md": 12, "lg": 12, "xl": 12},
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


# ============================================================
# OPERATIONAL DASHBOARDS PER WORK AREA
#
# Extra dashboards of this module (DASHBOARDS - django_resaas discovers
# DASHBOARD and DASHBOARDS). Which one a user gets is decided ONLY by
# permissions: the dashboard permission (granted to the matching profiles
# by saude/profiles.py) plus each widget's own permissions - never by the
# profile's name. Data: saude/dashboard_flow_providers.py.
# ============================================================

from saude import dashboard_flow_providers  # noqa: F401,E402  (regista os providers)

_STAT_COLS = {"xs": 12, "sm": 6, "md": 3, "lg": 3, "xl": 3}
_FULL_COLS = {"xs": 12, "sm": 12, "md": 12, "lg": 12, "xl": 12}

_OPEN_PATIENT = {
    "name": "view_patient",
    "type": "route",
    "icon": "person",
    "tooltip": "Open the patient record (appointments, check-in, history)",
    "route": {"name": "view_paciente", "params": {"id": "{paciente_id}"}},
    "permissions": ["view_paciente"],
}

# per queue row: opens the vital-signs dialog registered by the frontend
# (dev/front pages/saude/dashboard/dashboard.js -> VitalSignsDialog.vue) for
# that appointment; the row's "id" is the Agenda. Patient, appointment, doctor
# and professional are filled in by the server (GET dadovitals/intake/).
# Reception: the patient arrives / leaves. POST to the explicit actions of
# AgendaAPIView (state checked on the server: 409 otherwise); each button only
# shows on the rows whose state allows it ("when").
_CHECK_IN = {
    "name": "check_in",
    "type": "request",
    "request": {"method": "POST", "endpoint": "saude/agendas/{id}/check_in/"},
    "when": {"field": "estado", "in": ["marcada", "confirmada"]},
    "icon": "login",
    "color": "positive",
    "tooltip": "Check in (patient arrived)",
    "success": "Patient checked in.",
    "permissions": ["check_in_agenda"],
}

_CHECK_OUT = {
    "name": "check_out",
    "type": "request",
    "request": {"method": "POST", "endpoint": "saude/agendas/{id}/check_out/"},
    "when": {"field": "estado", "in": ["em_espera", "em_atendimento"]},
    "icon": "logout",
    "color": "primary",
    "tooltip": "Check out (patient leaves)",
    "confirm": "Check out this patient? The appointment will be marked as completed.",
    "success": "Patient checked out.",
    "permissions": ["check_out_agenda"],
}

_RECORD_VITALS = {
    "name": "record_vital_signs",
    "type": "dialog",
    "dialog": "saude.record_vital_signs",
    "icon": "monitor_heart",
    "tooltip": "Record vital signs",
    "permissions": ["add_dadovital"],
}


def _stat(name, label, provider, icon, permissions, order, tooltip):
    return {
        "name": name,
        "type": "stat",
        "label": label,
        "icon": icon,
        "color": "primary",
        "provider": provider,
        "permissions": permissions,
        "permission_mode": "all",
        "tooltip": tooltip,
        "visible": True,
        "cols": _STAT_COLS,
        "order": order,
        "accepts_filters": [],
        "filters": [],
    }


def _queue(name, label, provider, permissions, order, tooltip, actions=(), row_actions=()):
    return {
        "name": name,
        "type": "table",
        "label": label,
        "provider": provider,
        "permissions": permissions,
        "permission_mode": "all",
        "tooltip": tooltip,
        "actions": list(actions),
        "row_actions": [*row_actions, _OPEN_PATIENT],
        "visible": True,
        "cols": _FULL_COLS,
        "order": order,
        "accepts_filters": [],
        "filters": [],
    }


def _operational(name, label, icon, permission, order, tooltip, widgets):
    return {
        "schema_version": "1.0",
        "name": name,
        "module": "saude",
        "label": label,
        "icon": icon,
        "order": order,
        "visible": True,
        "permission": permission,
        "tooltip": tooltip,
        "layout": {"columns": 12, "gap": "md", "dense": False},
        "refresh": {"enabled": True, "interval": 60},
        "filters": [],
        "widgets": widgets,
    }


DASHBOARDS = [
    _operational(
        "saude_reception", "Reception", "how_to_reg", "view_dashboard_saude_reception", 1,
        "Today's appointments, arrivals and waiting times.",
        [
            _stat("appointments_today", "Appointments Today", "saude.reception.appointments_today",
                  "event", ["view_agenda"], 10, "Appointments booked for today (cancelled excluded)."),
            _stat("checked_in_today", "Patients Arrived", "saude.reception.checked_in_today",
                  "login", ["view_agenda"], 20, "Patients checked in today."),
            _stat("waiting_now", "Patients Waiting", "saude.flow.waiting_now",
                  "hourglass_top", ["view_agenda"], 30, "Checked in and not yet being seen."),
            _stat("average_waiting", "Average Waiting Time", "saude.flow.average_waiting_today",
                  "timer", ["view_agenda"], 40, "From check-in to the start of the consultation, today."),
            _queue("reception_queue", "Reception Queue", "saude.reception.queue", ["view_agenda"], 50,
                   "Today's appointments in scheduled order: check the patient in on arrival and out on leaving.",
                   row_actions=[_CHECK_IN, _CHECK_OUT],
                   actions=[{
                       "name": "add_patient",
                       "type": "route",
                       "icon": "person_add",
                       "tooltip": "Register patient",
                       "route": {"name": "add_paciente"},
                       "permissions": ["add_paciente"],
                   }]),
        ],
    ),
    _operational(
        "saude_nursing", "Nursing", "monitor_heart", "view_dashboard_saude_nursing", 2,
        "Patients waiting, vital signs to record and patients ready for the doctor.",
        [
            _stat("waiting_now", "Patients Waiting", "saude.flow.waiting_now",
                  "hourglass_top", ["view_agenda"], 10, "Checked in and not yet being seen."),
            _stat("vitals_pending", "Vital Signs Pending", "saude.nursing.vitals_pending",
                  "pending_actions", ["view_agenda", "view_dadovital"], 20,
                  "Waiting patients without vital signs since check-in."),
            _stat("ready_for_doctor", "Ready for Doctor", "saude.nursing.ready_for_doctor",
                  "task_alt", ["view_agenda", "view_dadovital"], 30,
                  "Waiting patients whose vital signs are recorded."),
            _stat("vitals_recorded_today", "Vital Signs Recorded Today", "saude.nursing.vitals_recorded_today",
                  "monitor_heart", ["view_dadovital"], 40, "Vital-sign records taken today."),
            _queue("nursing_queue", "Nursing Queue", "saude.nursing.queue",
                   ["view_agenda", "view_dadovital"], 50,
                   "Waiting patients, vital signs pending first.", row_actions=[_RECORD_VITALS]),
        ],
    ),
    _operational(
        "saude_doctor", "My Patients", "medical_services", "view_dashboard_saude_doctor", 3,
        "Your appointments today, your queue and your patients' results.",
        [
            _stat("my_appointments_today", "My Appointments Today", "saude.doctor.my_appointments_today",
                  "event", ["view_agenda"], 10, "Your appointments today (cancelled excluded)."),
            _stat("waiting_for_me", "Patients Waiting for Me", "saude.doctor.waiting_for_me",
                  "hourglass_top", ["view_agenda"], 20, "Your patients checked in and waiting."),
            _stat("completed_today", "Completed Consultations", "saude.doctor.completed_today",
                  "task_alt", ["view_agenda"], 30, "Your appointments completed today."),
            _stat("pending_exams", "Pending Exams", "saude.doctor.pending_exams",
                  "science", ["view_pedidoexamemedico"], 40,
                  "Open exam items from your consultations."),
            _queue("my_queue", "My Queue", "saude.doctor.my_queue", ["view_agenda"], 50,
                   "Your appointments today that are not closed.", row_actions=[_RECORD_VITALS]),
            {
                "name": "recent_results",
                "type": "list",
                "label": "Recent Exam Results",
                "provider": "saude.doctor.recent_results",
                "permissions": ["view_resultadoexamemedico"],
                "permission_mode": "all",
                "tooltip": "Released results of exams you requested, last 7 days.",
                "item_action": {
                    "name": "open_patient",
                    "type": "route",
                    "route": {"name": "view_paciente", "params": {"id": "{paciente_id}"}},
                    "permissions": ["view_paciente"],
                },
                "visible": True,
                "cols": _FULL_COLS,
                "order": 60,
                "accepts_filters": [],
                "filters": [],
            },
        ],
    ),
    _operational(
        "saude_laboratory", "Laboratory", "science", "view_dashboard_saude_laboratory", 4,
        "Exam requests from doctors and exam-only patients: collection, processing and results to validate.",
        [
            _stat("requests_today", "Exam Requests Today", "saude.lab.requests_today",
                  "assignment", ["view_pedidoexamemedico"], 10,
                  "Exam requests created today (doctor requests and exam only)."),
            _stat("pending_collection", "Pending Collection", "saude.lab.pending_collection",
                  "pending_actions", ["view_itempedidoexamemedico"], 20,
                  "Exam items not collected yet."),
            _stat("in_process", "Processing", "saude.lab.in_process",
                  "biotech", ["view_itempedidoexamemedico"], 30,
                  "Exam items collected or being processed."),
            _stat("results_to_validate_count", "Results to Validate", "saude.lab.results_to_validate_count",
                  "fact_check", ["view_resultadoexamemedico"], 40,
                  "Recorded results waiting for clinical validation."),
            _stat("results_to_record", "Results to Record", "saude.lab.results_to_record",
                  "edit_note", ["view_itempedidoexamemedico"], 41,
                  "Collected or processing exams without a result yet."),
            _stat("results_to_release", "Results to Release", "saude.lab.results_to_release",
                  "publish", ["view_resultadoexamemedico", "release_resultadoexamemedico"], 42,
                  "Validated results not yet released to the requester and the patient."),
            _stat("average_tat", "Average Turnaround Time", "saude.lab.average_tat_today",
                  "timelapse", ["view_resultadoexamemedico"], 43,
                  "From sample collection to result release, results released today."),
            _stat("recollection_required", "Recollection Required", "saude.lab.recollection_required",
                  "block", ["view_itempedidoexamemedico"], 44,
                  "Rejected samples waiting for a new collection."),
            {
                **_queue("lab_queue", "Laboratory Queue", "saude.lab.queue",
                         ["view_pedidoexamemedico", "view_itempedidoexamemedico"], 50,
                         "Requests with open exams, checked-in patients first. Waiting counts from check-in to the first collection."),
                "row_actions": [
                    {
                        "name": "open_request",
                        "type": "route",
                        "icon": "assignment",
                        "tooltip": "Open the exam request",
                        "route": {"name": "view_pedidoexamemedico", "params": {"id": "{id}"}},
                        "permissions": ["view_pedidoexamemedico"],
                    },
                    _OPEN_PATIENT,
                ],
            },
            {
                "name": "results_to_validate",
                "type": "list",
                "label": "Results to Validate",
                "provider": "saude.lab.results_to_validate",
                "permissions": ["view_resultadoexamemedico", "validate_resultadoexamemedico"],
                "permission_mode": "all",
                "tooltip": "Oldest recorded results not yet validated. Only users who can validate see this list.",
                "item_action": {
                    "name": "open_result",
                    "type": "route",
                    "route": {"name": "view_resultadopedidoexamemedico", "params": {"id": "{id}"}},
                    "permissions": ["view_resultadoexamemedico"],
                },
                "visible": True,
                "cols": _FULL_COLS,
                "order": 60,
                "accepts_filters": [],
                "filters": [],
            },
            {
                "name": "attention",
                "type": "list",
                "label": "Attention Required",
                "provider": "saude.lab.attention",
                "permissions": ["view_itempedidoexamemedico", "view_resultadoexamemedico"],
                "permission_mode": "all",
                "tooltip": "Rejected samples, and unreleased results flagged critical by a configured critical range.",
                "visible": True,
                "cols": _FULL_COLS,
                "order": 70,
                "accepts_filters": [],
                "filters": [],
            },
        ],
    ),
]


# ============================================================
# PATIENT (the Patient profile's home - its own data only)
#
# Ownership, not tenant scope: the providers resolve the caller's own
# Paciente (saude/dashboard_patient_providers.py). Permissions are the
# portal capabilities the Patient profile has; no operational dashboard
# permission is involved.
# ============================================================

from saude import dashboard_patient_providers  # noqa: F401,E402  (regista os providers)

_HALF_COLS = {"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6}

_OPEN_MY_HEALTH = {
    "name": "open_my_health",
    "type": "route",
    "icon": "favorite",
    "tooltip": "Open My Health",
    "route": {"name": "my_health"},
    "permissions": ["view_patient_portal"],
}


def _patient_list(name, label, provider, icon, permission, order, tooltip):
    return {
        "name": name,
        "type": "list",
        "label": label,
        "icon": icon,
        "provider": provider,
        "permissions": [permission],
        "permission_mode": "all",
        "tooltip": tooltip,
        "actions": [_OPEN_MY_HEALTH],
        "visible": True,
        "cols": _HALF_COLS,
        "order": order,
        "accepts_filters": [],
        "filters": [],
    }


DASHBOARDS.append(_operational(
    "saude_patient", "My Health", "favorite", "view_patient_portal", 0,
    "Your appointments, exams, results and vital signs.",
    [
        _stat("next_appointment", "Next appointment", "saude.patient.next_appointment",
              "event", ["view_own_appointments"], 10, "Your next appointment."),
        _stat("pending_exams", "Pending Exams", "saude.patient.pending_exams",
              "science", ["view_own_exams"], 20, "Your exams not finished yet."),
        _stat("new_results", "New Results", "saude.patient.new_results",
              "fact_check", ["view_own_results"], 30, "Results released to you in the last 30 days."),
        _stat("prescriptions", "Prescriptions", "saude.patient.prescriptions",
              "medication", ["view_own_prescriptions"], 40, "Your prescriptions."),
        {
            "name": "upcoming_appointments",
            "type": "table",
            "label": "Upcoming Appointments",
            "provider": "saude.patient.upcoming_appointments",
            "permissions": ["view_own_appointments"],
            "permission_mode": "all",
            "tooltip": "Your next appointments.",
            "actions": [_OPEN_MY_HEALTH],
            "visible": True,
            "cols": _FULL_COLS,
            "order": 50,
            "accepts_filters": [],
            "filters": [],
        },
        _patient_list("recent_results", "My Results", "saude.patient.recent_results",
                      "fact_check", "view_own_results", 60, "Your latest released results."),
        _patient_list("latest_vitals", "My Vital Signs", "saude.patient.latest_vitals",
                      "monitor_heart", "view_own_vitals", 70, "Your latest vital-sign record."),
    ],
))
