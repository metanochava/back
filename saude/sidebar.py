MENU = "Saude"
ICON = "local_hospital"  # 🔥 identity médica

SUBMENUS = [
    {
        "icon": "space_dashboard",
        "menu": "Dashboard",
        "role": "view_saude_dashboard",
        "rota": "view_saude_dashboard",
    },

    # 👤 PACIENTE
    {
        "add_role": "add_paciente",
        "add_rota": "add_paciente",
        "icon": "person",
        "menu": "Paciente",
        "role": "list_paciente",
        "rota": "list_paciente",
    },

    # 📅 CONSULTA
    {
        "add_role": "add_consulta",
        "add_rota": "add_consulta",
        "icon": "event",
        "menu": "Consulta",
        "role": "list_consulta",
        "rota": "list_consulta",
    },

    # 💊 RECEITA
    {
        "add_role": "add_receitamedica",
        "add_rota": "add_receitamedica",
        "icon": "medication",
        "menu": "Receitamedica",
        "role": "list_receitamedica",
        "rota": "list_receitamedica",
    },

    # 📄 DOCUMENTOS MÉDICOS
    {
        "add_role": "add_atestadomedico",
        "add_rota": "add_atestadomedico",
        "icon": "assignment",
        "menu": "Atestadomedico",
        "role": "list_atestadomedico",
        "rota": "list_atestadomedico",
    },
    {
        "add_role": "add_relatoriomedico",
        "add_rota": "add_relatoriomedico",
        "icon": "description",
        "menu": "Relatoriomedico",
        "role": "list_relatoriomedico",
        "rota": "list_relatoriomedico",
    },
    {
        "add_role": "add_guiatransferencia",
        "add_rota": "add_guiatransferencia",
        "icon": "transfer_within_a_station",
        "menu": "Guiatransferencia",
        "role": "list_guiatransferencia",
        "rota": "list_guiatransferencia",
    },

    # 🧪 EXAMES
    {
        "add_role": "add_pedidoexamemedico",
        "add_rota": "add_pedidoexamemedico",
        "icon": "request_page",
        "menu": "Pedidoexamemedico",
        "role": "list_pedidoexamemedico",
        "rota": "list_pedidoexamemedico",
    },
    {
        "add_role": "add_examemedico",
        "add_rota": "add_examemedico",
        "icon": "biotech",
        "menu": "Examemedico",
        "role": "list_examemedico",
        "rota": "list_examemedico",
    },
    {
        "add_role": "add_classeexamemedico",
        "add_rota": "add_classeexamemedico",
        "icon": "category",
        "menu": "Classeexamemedico",
        "role": "list_classeexamemedico",
        "rota": "list_classeexamemedico",
    },
    {
        "add_role": "add_tipoexamemedico",
        "add_rota": "add_tipoexamemedico",
        "icon": "tune",
        "menu": "Tipoexamemedico",
        "role": "list_tipoexamemedico",
        "rota": "list_tipoexamemedico",
    },

    # ❤️ DADOS VITAIS
    {
        "add_role": "add_dadovital",
        "add_rota": "add_dadovital",
        "icon": "monitor_heart",
        "menu": "Dadovital",
        "role": "list_dadovital",
        "rota": "list_dadovital",
    },

    # 💊 MEDICAÇÃO
    {
        "add_role": "add_medicamento",
        "add_rota": "add_medicamento",
        "icon": "vaccines",
        "menu": "Medicamento",
        "role": "list_medicamento",
        "rota": "list_medicamento",
    },
    {
        "add_role": "add_medicacaocorrente",
        "add_rota": "add_medicacaocorrente",
        "icon": "medication_liquid",
        "menu": "Medicacaocorrente",
        "role": "list_medicacaocorrente",
        "rota": "list_medicacaocorrente",
    },

    # 🧬 HISTÓRICO CLÍNICO
    {
        "add_role": "add_doencacorrente",
        "add_rota": "add_doencacorrente",
        "icon": "coronavirus",
        "menu": "Doencacorrente",
        "role": "list_doencacorrente",
        "rota": "list_doencacorrente",
    },
    {
        "add_role": "add_alergiacorrente",
        "add_rota": "add_alergiacorrente",
        "icon": "warning_amber",
        "menu": "Alergiacorrente",
        "role": "list_alergiacorrente",
        "rota": "list_alergiacorrente",
    },
]