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
        "icon": "event",
        "menu": "Consulta",
        "role": "list_consulta",
        "route": "list_consulta",
    },

    # 💊 RECEITA
    {
        "add_role": "add_receitamedica",
        "add_route": "add_receitamedica",
        "icon": "medication",
        "menu": "Receitamedica",
        "role": "list_receitamedica",
        "route": "list_receitamedica",
    },

    # 📄 DOCUMENTOS MÉDICOS
    {
        "add_role": "add_atestadomedico",
        "add_route": "add_atestadomedico",
        "icon": "assignment",
        "menu": "Atestadomedico",
        "role": "list_atestadomedico",
        "route": "list_atestadomedico",
    },
    {
        "add_role": "add_relatoriomedico",
        "add_route": "add_relatoriomedico",
        "icon": "description",
        "menu": "Relatoriomedico",
        "role": "list_relatoriomedico",
        "route": "list_relatoriomedico",
    },
    {
        "add_role": "add_guiatransferencia",
        "add_route": "add_guiatransferencia",
        "icon": "transfer_within_a_station",
        "menu": "Guiatransferencia",
        "role": "list_guiatransferencia",
        "route": "list_guiatransferencia",
    },

    # 🧪 EXAMES
    {
        "add_role": "add_pedidoexamemedico",
        "add_route": "add_pedidoexamemedico",
        "icon": "request_page",
        "menu": "Pedidoexamemedico",
        "role": "list_pedidoexamemedico",
        "route": "list_pedidoexamemedico",
    },
    {
        "add_role": "add_examemedico",
        "add_route": "add_examemedico",
        "icon": "biotech",
        "menu": "Examemedico",
        "role": "list_examemedico",
        "route": "list_examemedico",
    },
    {
        "add_role": "add_classeexamemedico",
        "add_route": "add_classeexamemedico",
        "icon": "category",
        "menu": "Classeexamemedico",
        "role": "list_classeexamemedico",
        "route": "list_classeexamemedico",
    },
    {
        "add_role": "add_tipoexamemedico",
        "add_route": "add_tipoexamemedico",
        "icon": "tune",
        "menu": "Tipoexamemedico",
        "role": "list_tipoexamemedico",
        "route": "list_tipoexamemedico",
    },

    # ❤️ DADOS VITAIS
    {
        "add_role": "add_dadovital",
        "add_route": "add_dadovital",
        "icon": "monitor_heart",
        "menu": "Dadovital",
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
        "menu": "Medicacaocorrente",
        "role": "list_medicacaocorrente",
        "route": "list_medicacaocorrente",
    },

    # 🧬 HISTÓRICO CLÍNICO
    {
        "add_role": "add_doencacorrente",
        "add_route": "add_doencacorrente",
        "icon": "coronavirus",
        "menu": "Doencacorrente",
        "role": "list_doencacorrente",
        "route": "list_doencacorrente",
    },
    {
        "add_role": "add_alergiacorrente",
        "add_route": "add_alergiacorrente",
        "icon": "warning_amber",
        "menu": "Alergiacorrente",
        "role": "list_alergiacorrente",
        "route": "list_alergiacorrente",
    },
]