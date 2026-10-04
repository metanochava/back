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
            # exam catalogue of the exam request (saude/catalogoexames/ lists
            # with list_tipoexamemedico) and the read-only lookups of the
            # appointment screens (specialty -> doctor -> room/schedule)
            "list_tipoexamemedico",
            "list_specialty", "view_specialty",
            "list_medico", "view_medico",
            "list_consultorio", "view_consultorio",
            "list_horariomedico", "view_horariomedico",
            # Clinical Summary of the patient record (ClinicalListCard): lists the patient's allergies / conditions / medication and removes an entry
            "list_alergiacorrente", "list_doencacorrente", "list_medicacaocorrente", "delete_alergiacorrente", "delete_doencacorrente", "delete_medicacaocorrente",
            # statistics dashboards of the clinical work (medication, documents, exams, clinical history)
            "view_dashboard_saude_medicacao", "view_dashboard_saude_documentos_medicos", "view_dashboard_saude_exames", "view_dashboard_saude_historico_clinico",
            # --- held by the Doctor group in dev and production, codified on
            # 2026-10-04: the code is the source of truth for the profile ---
            "add_agenda", "change_agenda", "check_in_agenda", "check_out_agenda", "delete_agenda", "hard_delete_agenda", "pdf_agenda", "pdf_list_agenda", "restore_agenda",
            "hard_delete_alergiacorrente", "pdf_alergiacorrente", "pdf_list_alergiacorrente", "restore_alergiacorrente",
            "delete_alergiamedicamentosa", "hard_delete_alergiamedicamentosa", "list_alergiamedicamentosa", "pdf_alergiamedicamentosa", "pdf_list_alergiamedicamentosa", "restore_alergiamedicamentosa",
            "hard_delete_atestadomedico", "pdf_list_atestadomedico", "restore_atestadomedico",
            "search_candidates_paciente",
            "add_cirurgia", "change_cirurgia", "delete_cirurgia", "hard_delete_cirurgia", "list_cirurgia", "pdf_cirurgia", "pdf_list_cirurgia", "restore_cirurgia",
            "add_classeexamemedico", "change_classeexamemedico", "delete_classeexamemedico", "hard_delete_classeexamemedico", "list_classeexamemedico", "pdf_classeexamemedico", "pdf_list_classeexamemedico", "restore_classeexamemedico",
            "grant_consent_paciente", "revoke_consent_paciente",
            "add_consentgrant", "change_consentgrant", "delete_consentgrant", "hard_delete_consentgrant", "list_consentgrant", "pdf_consentgrant", "pdf_list_consentgrant", "restore_consentgrant", "view_consentgrant",
            "delete_consulta", "hard_delete_consulta", "pdf_list_consulta", "restore_consulta",
            "add_consultorio", "change_consultorio", "delete_consultorio", "hard_delete_consultorio", "pdf_consultorio", "pdf_list_consultorio", "restore_consultorio",
            "delete_dadovital", "hard_delete_dadovital", "pdf_dadovital", "pdf_list_dadovital", "restore_dadovital",
            "delete_diagnostico", "hard_delete_diagnostico", "list_diagnostico", "pdf_diagnostico", "pdf_list_diagnostico", "restore_diagnostico",
            "hard_delete_doencacorrente", "pdf_doencacorrente", "pdf_list_doencacorrente", "restore_doencacorrente",
            "add_emergencyaccess", "change_emergencyaccess", "delete_emergencyaccess", "end_emergencyaccess", "hard_delete_emergencyaccess", "list_emergencyaccess", "pdf_emergencyaccess", "pdf_list_emergencyaccess", "restore_emergencyaccess", "review_emergencyaccess", "start_emergencyaccess", "view_emergencyaccess",
            "list_employeespecialty",
            "add_episodioclinico", "change_episodioclinico", "delete_episodioclinico", "hard_delete_episodioclinico", "pdf_episodioclinico", "pdf_list_episodioclinico", "restore_episodioclinico",
            "add_examemedico", "change_examemedico", "delete_examemedico", "hard_delete_examemedico", "list_examemedico", "pdf_examemedico", "pdf_list_examemedico", "restore_examemedico",
            "delete_examparameter", "hard_delete_examparameter", "list_examparameter", "pdf_examparameter", "pdf_list_examparameter", "restore_examparameter", "view_examparameter",
            "delete_examreferencerange", "hard_delete_examreferencerange", "list_examreferencerange", "pdf_examreferencerange", "pdf_list_examreferencerange", "restore_examreferencerange", "view_examreferencerange",
            "hard_delete_guiatransferencia", "pdf_list_guiatransferencia", "restore_guiatransferencia",
            "add_horariomedico", "change_horariomedico", "delete_horariomedico", "hard_delete_horariomedico", "pdf_horariomedico", "pdf_list_horariomedico", "restore_horariomedico",
            "add_imunizacao", "change_imunizacao", "delete_imunizacao", "hard_delete_imunizacao", "list_imunizacao", "pdf_imunizacao", "pdf_list_imunizacao", "restore_imunizacao",
            "add_internamento", "change_internamento", "delete_internamento", "hard_delete_internamento", "list_internamento", "pdf_internamento", "pdf_list_internamento", "restore_internamento",
            "collect_itempedidoexamemedico", "hard_delete_itempedidoexamemedico", "pdf_itempedidoexamemedico", "pdf_list_itempedidoexamemedico", "restore_itempedidoexamemedico",
            "hard_delete_itemreceita", "pdf_itemreceita", "pdf_list_itemreceita", "restore_itemreceita",
            "hard_delete_medicacaocorrente", "pdf_list_medicacaocorrente", "pdf_medicacaocorrente", "restore_medicacaocorrente",
            "change_medicamento", "delete_medicamento", "hard_delete_medicamento", "pdf_list_medicamento", "pdf_medicamento", "restore_medicamento",
            "add_medico", "change_medico", "delete_medico", "hard_delete_medico", "pdf_list_medico", "pdf_medico", "restore_medico",
            "delete_observacaoclinica", "hard_delete_observacaoclinica", "list_observacaoclinica", "pdf_list_observacaoclinica", "pdf_observacaoclinica", "restore_observacaoclinica",
            "add_paciente", "change_paciente", "delete_paciente", "hard_delete_paciente", "pdf_list_paciente", "register_paciente", "restore_paciente", "timeline_paciente",
            "add_patientidentifier", "change_patientidentifier", "delete_patientidentifier", "hard_delete_patientidentifier", "list_patientidentifier", "pdf_list_patientidentifier", "pdf_patientidentifier", "restore_patientidentifier", "view_patientidentifier",
            "add_patientmerge", "change_patientmerge", "delete_patientmerge", "hard_delete_patientmerge", "list_patientmerge", "pdf_list_patientmerge", "pdf_patientmerge", "restore_patientmerge", "view_patientmerge",
            "merge_patients_paciente",
            "check_in_pedidoexamemedico", "hard_delete_pedidoexamemedico", "pdf_list_pedidoexamemedico", "restore_pedidoexamemedico",
            "grant_portal_access_paciente",
            "add_procedimento", "change_procedimento", "delete_procedimento", "hard_delete_procedimento", "list_procedimento", "pdf_list_procedimento", "pdf_procedimento", "restore_procedimento",
            "hard_delete_receitamedica", "pdf_list_receitamedica", "restore_receitamedica",
            "hard_delete_relatoriomedico", "pdf_list_relatoriomedico", "restore_relatoriomedico",
            "record_result_itempedidoexamemedico",
            "add_resultadoexamemedico", "amend_resultadoexamemedico", "change_resultadoexamemedico", "delete_resultadoexamemedico", "hard_delete_resultadoexamemedico", "pdf_list_resultadoexamemedico", "release_resultadoexamemedico", "restore_resultadoexamemedico", "validate_resultadoexamemedico",
            "add_resultparametervalue", "change_resultparametervalue", "delete_resultparametervalue", "hard_delete_resultparametervalue", "list_resultparametervalue", "pdf_list_resultparametervalue", "pdf_resultparametervalue", "restore_resultparametervalue", "view_resultparametervalue",
            "reject_sample_itempedidoexamemedico",
            "add_tipoexamemedico", "change_tipoexamemedico", "delete_tipoexamemedico", "hard_delete_tipoexamemedico", "pdf_list_tipoexamemedico", "pdf_tipoexamemedico", "restore_tipoexamemedico",
            "add_vacina", "change_vacina", "delete_vacina", "hard_delete_vacina", "list_vacina", "pdf_list_vacina", "pdf_vacina", "restore_vacina",
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
            # Clinical Summary of the patient record: lists allergies / conditions / medication; removes a medication it records
            "list_alergiacorrente", "list_doencacorrente", "list_medicacaocorrente", "delete_medicacaocorrente",
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
            # editing a patient (change_paciente) also saves the Person, its
            # contacts and documents (quasar_resaas usePersonIntake.saveExisting),
            # loads them (list_*) and picks the document type
            "view_person", "change_person",
            "list_personcontact", "view_personcontact", "change_personcontact", "delete_personcontact",
            "list_document", "view_document", "change_document", "delete_document",
            "list_documenttype", "view_documenttype",
            "view_agenda", "add_agenda", "change_agenda", "list_agenda",
            "view_consulta", "list_consulta",
            "view_pedidoexamemedico", "add_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "add_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico",
            "check_in_pedidoexamemedico",
            "check_in_agenda", "check_out_agenda",
            # exam catalogue of the exam request (saude/catalogoexames/)
            "list_tipoexamemedico",
            # lookups of the booking dialog (specialty -> doctor -> room/schedule)
            "list_specialty", "view_specialty",
            "list_medico", "view_medico",
            "list_consultorio", "view_consultorio",
            "list_horariomedico", "view_horariomedico",
            "grant_portal_access_paciente",
            # online booking requests from the public site
            "view_appointmentrequest", "list_appointmentrequest",
            "confirm_appointmentrequest", "reject_appointmentrequest",
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
            # the results list page (list_resultadopedidoexamemedico route)
            "list_resultadoexamemedico",
            "view_resultparametervalue", "add_resultparametervalue",
            "view_dashboard_saude_laboratory",
            # exams statistics dashboard
            "view_dashboard_saude_exames",
        ],
    },
    {
        "name": "Medical Laboratory Scientist",
        "permissions": [
            "view_paciente",
            "view_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_examemedico", "view_tipoexamemedico", "view_classeexamemedico",
            # exam catalogue (types and classes of exam); deleting stays with Admin
            "list_tipoexamemedico", "add_tipoexamemedico", "change_tipoexamemedico",
            "list_classeexamemedico", "add_classeexamemedico", "change_classeexamemedico",
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
            # the results list page (list_resultadopedidoexamemedico route)
            "list_resultadoexamemedico",
            # exam catalogue: the exams themselves (types and classes above); exams statistics dashboard
            "list_examemedico", "add_examemedico", "change_examemedico", "view_dashboard_saude_exames",
            # --- granted to the Medical Laboratory Scientist group in the database (dev),
            # codified on 2026-10-04: the code is the source of truth ---
            # results: PDF, delete / restore / hard delete; their parameter values
            "pdf_resultadoexamemedico", "pdf_list_resultadoexamemedico",
            "delete_resultadoexamemedico", "restore_resultadoexamemedico", "hard_delete_resultadoexamemedico",
            "list_resultparametervalue", "pdf_resultparametervalue", "pdf_list_resultparametervalue",
            "delete_resultparametervalue", "restore_resultparametervalue", "hard_delete_resultparametervalue",
            # patients and their people / contacts (read)
            "list_paciente", "list_person", "view_person", "list_personcontact", "view_personcontact",
            # entity and entity type (read)
            "list_entity", "view_entity", "list_entitytype", "view_entitytype",
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
            # medication catalogue upkeep; medication statistics dashboard
            "add_medicamento", "change_medicamento", "view_dashboard_saude_medicacao",
            # --- held by the Pharmacist group in dev and production, codified on
            # 2026-10-04: the code is the source of truth for the profile ---
            "add_itemreceita",
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
            # exam catalogue (types and classes of exam); deleting stays with Admin
            "list_tipoexamemedico", "add_tipoexamemedico", "change_tipoexamemedico",
            "list_classeexamemedico", "add_classeexamemedico", "change_classeexamemedico",
            "view_resultadoexamemedico",
            "view_dashboard_saude_clinica",
            # Clinical Summary lists (read)
            "list_alergiacorrente", "list_doencacorrente", "list_medicacaocorrente",
            # doctors and their schedules; exam and medication catalogues
            "add_medico", "change_medico", "add_horariomedico", "change_horariomedico", "list_examemedico", "add_examemedico", "change_examemedico", "list_medicamento", "view_medicamento", "add_medicamento", "change_medicamento",
            # health dashboards (general and the statistics ones)
            "view_saude_dashboard", "view_dashboard_saude_medicacao", "view_dashboard_saude_documentos_medicos", "view_dashboard_saude_exames", "view_dashboard_saude_historico_clinico",
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
