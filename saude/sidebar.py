MENU = "Saude"
ICON = "local_hospital"  # 🔥 identity médica

SUBMENUS = [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_saude_dashboard",
        "route": "view_saude_dashboard",
    },

    # 👤 PACIENTE
    {
        "add_role": "add_paciente",
        "add_route": "add_paciente",
        "icon": "person",
        "menu": "Paciente",
        "role": "list_paciente",
        "route": "list_paciente",
    },

    # 📅 CONSULTA
    {
        "add_role": "add_consulta",
        "add_route": "add_consulta",
        "icon": "health_and_safety",
        "menu": "Consulta",
        "role": "list_consulta",
        "route": "list_consulta",
    },

    # 🕒 HORÁRIO DO MÉDICO
    {
        "add_role": "add_horariomedico",
        "add_route": "add_horariomedico",
        "icon": "schedule",
        "menu": "HorarioMedico",
        "role": "list_horariomedico",
        "route": "list_horariomedico",
    },

    # 💊 RECEITA
    {
        "add_role": "add_receitamedica",
        "add_route": "add_receitamedica",
        "icon": "medication",
        "menu": "ReceitaMedica",
        "role": "list_receitamedica",
        "route": "list_receitamedica",
    },

    # 📄 DOCUMENTOS MÉDICOS
    {
        "add_role": "add_atestadomedico",
        "add_route": "add_atestadomedico",
        "icon": "assignment",
        "menu": "AtestadoMedico",
        "role": "list_atestadomedico",
        "route": "list_atestadomedico",
    },
    {
        "add_role": "add_relatoriomedico",
        "add_route": "add_relatoriomedico",
        "icon": "description",
        "menu": "RelatorioMedico",
        "role": "list_relatoriomedico",
        "route": "list_relatoriomedico",
    },
    {
        "add_role": "add_guiatransferencia",
        "add_route": "add_guiatransferencia",
        "icon": "transfer_within_a_station",
        "menu": "GuiaTransferencia",
        "role": "list_guiatransferencia",
        "route": "list_guiatransferencia",
    },

    # 🧪 EXAMES
    {
        "add_role": "add_pedidoexamemedico",
        "add_route": "add_pedidoexamemedico",
        "icon": "request_page",
        "menu": "PedidoExameMedico",
        "role": "list_pedidoexamemedico",
        "route": "list_pedidoexamemedico",
    },
    {
        "add_role": "add_examemedico",
        "add_route": "add_examemedico",
        "icon": "biotech",
        "menu": "ExameMedico",
        "role": "list_examemedico",
        "route": "list_examemedico",
    },
    {
        "add_role": "add_classeexamemedico",
        "add_route": "add_classeexamemedico",
        "icon": "category",
        "menu": "ClasseExameMedico",
        "role": "list_classeexamemedico",
        "route": "list_classeexamemedico",
    },
    {
        "add_role": "add_tipoexamemedico",
        "add_route": "add_tipoexamemedico",
        "icon": "tune",
        "menu": "TipoExameMedico",
        "role": "list_tipoexamemedico",
        "route": "list_tipoexamemedico",
    },

    # ❤️ DADOS VITAIS
    {
        "add_role": "add_dadovital",
        "add_route": "add_dadovital",
        "icon": "monitor_heart",
        "menu": "DadoVital",
        "role": "list_dadovital",
        "route": "list_dadovital",
    },

    # 💊 MEDICAÇÃO
    {
        "add_role": "add_medicamento",
        "add_route": "add_medicamento",
        "icon": "vaccines",
        "menu": "Medicamento",
        "role": "list_medicamento",
        "route": "list_medicamento",
    },
    {
        "add_role": "add_medicacaocorrente",
        "add_route": "add_medicacaocorrente",
        "icon": "medication_liquid",
        "menu": "MedicacaoMorrente",
        "role": "list_medicacaocorrente",
        "route": "list_medicacaocorrente",
    },

    # 🧬 HISTÓRICO CLÍNICO
    {
        "add_role": "add_doencacorrente",
        "add_route": "add_doencacorrente",
        "icon": "coronavirus",
        "menu": "DoencaCorrente",
        "role": "list_doencacorrente",
        "route": "list_doencacorrente",
    },
    {
        "add_role": "add_alergiacorrente",
        "add_route": "add_alergiacorrente",
        "icon": "warning_amber",
        "menu": "AlergiaCorrente",
        "role": "list_alergiacorrente",
        "route": "list_alergiacorrente",
    },
]