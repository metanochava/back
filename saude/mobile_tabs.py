# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "My Health", "icon": "favorite", "route": "my_health", "permission": "view_patient_portal", "order": 5},
    {"label": "Patient", "icon": "person", "route": "list_paciente", "permission": "list_paciente", "order": 10},
    {"label": "Consultation", "icon": "health_and_safety", "route": "list_consulta", "permission": "list_consulta", "order": 20},
    {"label": "Prescription", "icon": "medication", "route": "list_receitamedica", "permission": "list_receitamedica", "order": 30},
    {"label": "Doctor Schedule", "icon": "schedule", "route": "list_horariomedico", "permission": "list_horariomedico", "order": 40},
]
