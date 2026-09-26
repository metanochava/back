"""
Perfis (Group templates) essenciais do módulo saude.

Baseado nos modelos/actions actualmente existentes em metanochava/back.

PRINCÍPIOS
----------
- Group representa PERFIL DE ACESSO, não profissão/especialidade.
- A autorização depende das permissions efectivas, nunca de Group.name.
- As permissões aqui declaradas têm de existir; group_creator() não inventa
  permissions inexistentes.
- group_creator() é aditivo: acrescenta defaults e preserva permissões
  personalizadas já atribuídas.
- Patient é um perfil real (Group), atribuído pelo grant do portal
  (BranchUserGroup na Branch do Paciente). As suas permissões são só do
  portal (view_patient_portal, view_own_*): nunca permissões clínicas de
  modelo. O perfil NÃO substitui o ownership - o portal resolve sempre o
  Paciente pelo request.user (ver saude/services/patient_portal_service.py).
- Cashier permanece mínimo neste módulo porque os modelos financeiros não
  pertencem actualmente ao app saude.
"""

CLINICAL_PROFILES = [
    {
        "name": "Doctor",
        "permissions": [
            "view_paciente", "list_paciente",
            "view_agenda", "list_agenda",
            "view_consulta", "add_consulta", "change_consulta", "list_consulta",
            "view_episodioclinico", "list_episodioclinico",
            "view_observacaoclinica", "add_observacaoclinica", "change_observacaoclinica",
            "view_diagnostico", "add_diagnostico", "change_diagnostico",
            "view_doencacorrente", "add_doencacorrente", "change_doencacorrente",
            "view_alergiacorrente", "add_alergiacorrente", "change_alergiacorrente",
            "view_alergiamedicamentosa", "add_alergiamedicamentosa", "change_alergiamedicamentosa",
            "view_dadovital", "list_dadovital", "add_dadovital",
            "view_medicacaocorrente", "add_medicacaocorrente", "change_medicacaocorrente",
            "view_medicamento", "list_medicamento",
            "view_receitamedica", "add_receitamedica", "list_receitamedica",
            "view_itemreceita", "add_itemreceita",
            "view_vacina", "view_imunizacao",
            "view_atestadomedico", "add_atestadomedico",
            "view_guiatransferencia", "add_guiatransferencia",
            "view_relatoriomedico", "add_relatoriomedico",
            "view_procedimento", "view_internamento", "view_cirurgia",
            "view_pedidoexamemedico", "add_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "add_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico", "view_classeexamemedico",
            "view_resultadoexamemedico", "lab_evolution_paciente",
            "view_dashboard_saude_doctor",
            # PDF of the documents the doctor already sees (same content, another
            # format): consultation, prescription, certificate, referral, report,
            # exam request and result, and the patient card
            "pdf_consulta", "pdf_receitamedica", "pdf_atestadomedico", "pdf_guiatransferencia",
            "pdf_relatoriomedico", "pdf_pedidoexamemedico", "pdf_resultadoexamemedico", "pdf_paciente",
            # the documents the doctor issues - listed in their side menus,
            # edited / reprinted and (soft) deleted there; restoring stays with
            # restore_* (not granted). Consultations are not deleted by doctors.
            "list_atestadomedico", "change_atestadomedico", "delete_atestadomedico",
            "list_guiatransferencia", "change_guiatransferencia", "delete_guiatransferencia",
            "list_relatoriomedico", "change_relatoriomedico", "delete_relatoriomedico",
            "change_receitamedica", "delete_receitamedica",
            "list_itemreceita", "change_itemreceita", "delete_itemreceita",
            "change_pedidoexamemedico", "delete_pedidoexamemedico",
            "list_itempedidoexamemedico", "change_itempedidoexamemedico", "delete_itempedidoexamemedico",
            # results are read (the laboratory records them)
            "list_resultadoexamemedico",
            # correcting a vital-sign value; a medication missing from the
            # catalogue ("New medication" on the prescription screen)
            "change_dadovital", "add_medicamento",
        ],
    },
    {
        "name": "Nurse",
        "permissions": [
            "view_paciente", "list_paciente",
            "view_agenda", "list_agenda", "view_consulta",
            "view_episodioclinico",
            "view_observacaoclinica", "add_observacaoclinica", "change_observacaoclinica",
            "view_dadovital", "list_dadovital", "add_dadovital", "change_dadovital",
            "view_doencacorrente", "view_alergiacorrente", "view_alergiamedicamentosa",
            "view_medicacaocorrente", "add_medicacaocorrente", "change_medicacaocorrente",
            "view_medicamento",
            "view_vacina", "add_vacina", "change_vacina",
            "view_imunizacao", "add_imunizacao", "change_imunizacao",
            "view_internamento", "view_procedimento",
            "view_dashboard_saude_nursing",
        ],
    },
]

FRONT_OFFICE_PROFILES = [
    {
        "name": "Medical Receptionist",
        "permissions": [
            "view_paciente", "add_paciente", "change_paciente", "list_paciente",
            "register_paciente", "search_candidates_paciente",
            "add_person", "add_document", "add_personcontact",
            "view_agenda", "add_agenda", "change_agenda", "list_agenda",
            "view_consulta", "list_consulta",
            "view_pedidoexamemedico", "add_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "add_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico",
            "check_in_pedidoexamemedico",
            "check_in_agenda", "check_out_agenda",
            "grant_portal_access_paciente",
            "view_dashboard_saude_reception",
        ],
    },
]

LABORATORY_PROFILES = [
    {
        "name": "Medical Laboratory Technician",
        "permissions": [
            "view_paciente",
            "view_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico", "view_classeexamemedico",
            "view_examparameter", "view_examreferencerange",
            "check_in_pedidoexamemedico",
            "collect_itempedidoexamemedico",
            "reject_sample_itempedidoexamemedico",
            "record_result_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
            "view_resultparametervalue", "add_resultparametervalue",
            "view_dashboard_saude_laboratory",
        ],
    },
    {
        "name": "Medical Laboratory Scientist",
        "permissions": [
            "view_paciente",
            "view_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico", "view_classeexamemedico",
            "view_examparameter", "add_examparameter", "change_examparameter",
            "view_examreferencerange", "add_examreferencerange", "change_examreferencerange",
            "check_in_pedidoexamemedico",
            "collect_itempedidoexamemedico",
            "reject_sample_itempedidoexamemedico",
            "record_result_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico", "change_resultadoexamemedico",
            "view_resultparametervalue", "add_resultparametervalue", "change_resultparametervalue",
            "validate_resultadoexamemedico",
            "release_resultadoexamemedico",
            "amend_resultadoexamemedico",
            "lab_evolution_paciente",
            "view_dashboard_saude_laboratory",
        ],
    },
]

PHARMACY_PROFILES = [
    {
        "name": "Pharmacist",
        "permissions": [
            "view_paciente",
            "view_receitamedica", "list_receitamedica",
            "view_itemreceita", "list_itemreceita",
            "view_medicamento", "list_medicamento",
            "view_medicacaocorrente", "view_alergiamedicamentosa",
            # O workflow de dispensa pertence ao app farmacia.
            # farmacia/profiles.py reutiliza este mesmo Group global e
            # acrescenta as permissões próprias do módulo.
        ],
    },
]

FINANCE_PROFILES = [
    {
        "name": "Cashier",
        "permissions": [
            "view_paciente",
            # Não inventar permissions financeiras dentro de saude.
            # Devem vir do módulo que possuir Invoice/Payment/Cash Register.
        ],
    },
]

MANAGEMENT_PROFILES = [
    {
        "name": "Healthcare Administrator",
        "permissions": [
            "view_paciente", "list_paciente",
            "view_agenda", "list_agenda",
            "view_consulta", "list_consulta",
            "view_medico", "list_medico",
            "view_consultorio", "list_consultorio",
            "view_horariomedico", "list_horariomedico",
            "view_episodioclinico", "list_episodioclinico",
            "view_diagnostico", "view_dadovital", "list_dadovital", "view_observacaoclinica",
            "view_doencacorrente", "view_alergiacorrente", "view_alergiamedicamentosa",
            "view_medicacaocorrente", "view_vacina", "view_imunizacao",
            "view_procedimento",
            "view_internamento", "list_internamento",
            "view_cirurgia", "list_cirurgia",
            "view_receitamedica", "list_receitamedica", "view_itemreceita",
            "view_atestadomedico", "view_guiatransferencia", "view_relatoriomedico",
            "view_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico", "view_classeexamemedico",
            "view_resultadoexamemedico",
            "view_dashboard_saude_clinica",
        ],
    },
]

# ============================================================
# PATIENT / PATIENT PORTAL
# ============================================================

PATIENT_PROFILES = [
    {
        "name": "Patient",
        "permissions": [
            # Capacidades do portal, sempre sobre os PRÓPRIOS dados
            # (saude/signals/permissions.py DASHBOARD_PERMISSIONS). Nunca
            # permissões clínicas de modelo (view_paciente,
            # view_resultadoexamemedico, ...): dariam acesso aos
            # recursos clínicos em geral, não só aos do próprio.
            "view_patient_portal",
            "view_own_appointments",
            "view_own_exams",
            "view_own_results",
            "view_own_trends",
            "view_own_prescriptions",
            "view_own_vitals",
        ],
    },
]

SAUDE_PROFILES = (
    CLINICAL_PROFILES
    + FRONT_OFFICE_PROFILES
    + LABORATORY_PROFILES
    + PHARMACY_PROFILES
    + FINANCE_PROFILES
    + MANAGEMENT_PROFILES
    + PATIENT_PROFILES
)

# Nome(s) antigo(s) -> nome novo, renomeados no lugar (Group.id e todas as
# relações preservados) pelo group_creator(). Uma lista cobre instalações
# ainda com o nome em português e as que já passaram ao nome em inglês
# anterior; o primeiro que existir é renomeado.
SAUDE_RENAME_FROM = {
    "Doctor": ["General Practitioner", "Médico Geral"],
    "Nurse": ["Registered Nurse", "Enfermeiro"],
    "Medical Receptionist": "Recepcionista",
    "Medical Laboratory Technician": "Técnico de Laboratório",
    "Medical Laboratory Scientist": "Analista Clínico",
    "Pharmacist": "Farmacêutico",
    "Cashier": "Faturamento",
    "Healthcare Administrator": "Administrador",
    # Patient é novo; não há Group antigo verificado para renomear.
}
