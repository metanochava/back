ALL = [{
'MENU' : "Saude",
'ICON' : "local_hospital",  # 🔥 identity médica

'SUBMENUS' : [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_saude_dashboard",
        "route": "view_saude_dashboard",
    },

    # 📊 CLÍNICA (dashboard dinâmico - saude/dashboard.py, motor
    # django_resaas.saas.core.dashboards. Entrada nova e adicional,
    # não substitui o "Dashboard" acima nem os 4 dashboards por grupo
    # já existentes mais abaixo - ver docs/architecture/dashboards.md)
    {
        "icon": "medical_services",
        "menu": "Clinic",
        "role": "view_dashboard_saude_clinica",
        "route": "dashboard_saude_clinica",
    },

    # 👤 PACIENTE
    {
        "add_role": "add_paciente",
        "add_route": "add_paciente",
        "icon": "person",
        "menu": "Patient",
        "role": "list_paciente",
        "route": "list_paciente",
    },

    # 📅 CONSULTA
    {
        "add_role": "add_consulta",
        "add_route": "add_consulta",
        "icon": "health_and_safety",
        "menu": "Consultation",
        "role": "list_consulta",
        "route": "list_consulta",
    },

    # 🩺 MÉDICO
    {
        "add_role": "add_medico",
        "add_route": "add_medico",
        "icon": "medical_services",
        "menu": "Doctor",
        "role": "list_medico",
        "route": "list_medico",
    },

    # 🕒 HORÁRIO DO MÉDICO
    {
        "add_role": "add_horariomedico",
        "add_route": "add_horariomedico",
        "icon": "schedule",
        "menu": "Doctor Schedule",
        "role": "list_horariomedico",
        "route": "list_horariomedico",
    },

    # 💊 MEDICAÇÃO (grupo: gerador de menu suporta "submenu" aninhado,
    # ver "Dev" em django_resaas/engine/sidebar.py)
    {
        "menu": "Medication",
        "icon": "medication",
        "role": "list_receitamedica",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_saude_medicacao",
                "route": "view_dashboard_saude_medicacao",
            },
            {
                "add_role": "add_receitamedica",
                "add_route": "add_receitamedica",
                "icon": "medication",
                "menu": "Prescription",
                "role": "list_receitamedica",
                "route": "list_receitamedica",
            },
            {
                "add_role": "add_medicamento",
                "add_route": "add_medicamento",
                "icon": "vaccines",
                "menu": "Medicine",
                "role": "list_medicamento",
                "route": "list_medicamento",
            },
            {
                "add_role": "add_medicacaocorrente",
                "add_route": "add_medicacaocorrente",
                "icon": "medication_liquid",
                "menu": "Current Medication",
                "role": "list_medicacaocorrente",
                "route": "list_medicacaocorrente",
            },
        ],
    },

    # 📄 DOCUMENTOS MÉDICOS (grupo)
    {
        "menu": "Medical Documents",
        "icon": "assignment",
        "role": "list_atestadomedico",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_saude_documentos_medicos",
                "route": "view_dashboard_saude_documentos_medicos",
            },
            {
                "add_role": "add_atestadomedico",
                "add_route": "add_atestadomedico",
                "icon": "assignment",
                "menu": "Medical Certificate",
                "role": "list_atestadomedico",
                "route": "list_atestadomedico",
            },
            {
                "add_role": "add_relatoriomedico",
                "add_route": "add_relatoriomedico",
                "icon": "description",
                "menu": "Medical Report",
                "role": "list_relatoriomedico",
                "route": "list_relatoriomedico",
            },
            {
                "add_role": "add_guiatransferencia",
                "add_route": "add_guiatransferencia",
                "icon": "transfer_within_a_station",
                "menu": "Transfer Referral",
                "role": "list_guiatransferencia",
                "route": "list_guiatransferencia",
            },
        ],
    },

    # 🧪 EXAMES (grupo)
    {
        "menu": "Exams",
        "icon": "biotech",
        "role": "list_pedidoexamemedico",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_saude_exames",
                "route": "view_dashboard_saude_exames",
            },
            {
                "add_role": "add_pedidoexamemedico",
                "add_route": "add_pedidoexamemedico",
                "icon": "request_page",
                "menu": "Exam Request",
                "role": "list_pedidoexamemedico",
                "route": "list_pedidoexamemedico",
            },
            {
                "add_role": "add_examemedico",
                "add_route": "add_examemedico",
                "icon": "biotech",
                "menu": "Medical Exam",
                "role": "list_examemedico",
                "route": "list_examemedico",
            },
            {
                "add_role": "add_classeexamemedico",
                "add_route": "add_classeexamemedico",
                "icon": "category",
                "menu": "Exam Class",
                "role": "list_classeexamemedico",
                "route": "list_classeexamemedico",
            },
            {
                "add_role": "add_tipoexamemedico",
                "add_route": "add_tipoexamemedico",
                "icon": "tune",
                "menu": "Exam Type",
                "role": "list_tipoexamemedico",
                "route": "list_tipoexamemedico",
            },
        ],
    },

    # 🧬 HISTÓRICO CLÍNICO (grupo: factos correntes/longitudinais -
    # dados vitais, doenças e alergias correntes)
    {
        "menu": "Clinical History",
        "icon": "history_edu",
        "role": "list_dadovital",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_saude_historico_clinico",
                "route": "view_dashboard_saude_historico_clinico",
            },
            {
                "add_role": "add_dadovital",
                "add_route": "add_dadovital",
                "icon": "monitor_heart",
                "menu": "Vital Sign",
                "role": "list_dadovital",
                "route": "list_dadovital",
            },
            {
                "add_role": "add_doencacorrente",
                "add_route": "add_doencacorrente",
                "icon": "coronavirus",
                "menu": "Current Condition",
                "role": "list_doencacorrente",
                "route": "list_doencacorrente",
            },
            {
                "add_role": "add_alergiacorrente",
                "add_route": "add_alergiacorrente",
                "icon": "warning_amber",
                "menu": "Current Allergy",
                "role": "list_alergiacorrente",
                "route": "list_alergiacorrente",
            },
        ],
    },
]}]
