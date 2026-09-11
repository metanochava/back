"""Perfis (Group templates) do módulo saude - nomes técnicos em inglês
(terminologia ocupacional internacional), com pacotes de permissões
por omissão.

Mapa de migração PT -> EN (SAUDE_RENAME_FROM) preserva Group.id e
todas as relações existentes (BranchUserGroup/EntityGroup/
permissions) - só o `name` muda, via group_creator()'s rename_from
(engine/core/utils/group_creator.py). Group não tem campo `code`
próprio (só `id` UUID + `name` único) - `id` já é o identificador
estável, não foi necessário adicionar coluna nova.

IMPORTANTE (perfil != permissão, CLAUDE.md): nenhum destes nomes é lido
em código de segurança em lado nenhum - servem só de conjunto de
permissões por omissão ao criar o grupo. Um administrador pode
renomear ou criar "Senior Clinical Supervisor" e continua a funcionar,
desde que tenha as permissões certas.
"""

# ============================================================
# CLÍNICA
# ============================================================

CLINICAL_PROFILES = [
    {
        "name": "Medical Receptionist",
        "permissions": [
            "view_paciente", "add_paciente", "list_paciente",
            "view_agenda", "add_agenda", "change_agenda", "list_agenda",
        ],
    },
    {
        "name": "General Practitioner",
        "permissions": [
            "view_paciente", "list_paciente",
            "view_consulta", "add_consulta", "change_consulta", "list_consulta",
            "view_agenda", "list_agenda",
            "view_diagnostico", "add_diagnostico",
            "view_receitamedica", "add_receitamedica",
            "view_atestadomedico", "add_atestadomedico",
            "view_pedidoexamemedico", "add_pedidoexamemedico",
        ],
    },
    {
        "name": "Specialist Physician",
        "permissions": [
            "view_paciente", "list_paciente",
            "view_consulta", "add_consulta", "change_consulta", "list_consulta",
            "view_agenda", "list_agenda",
            "view_diagnostico", "add_diagnostico",
            "view_receitamedica", "add_receitamedica",
            "view_pedidoexamemedico", "add_pedidoexamemedico",
            "view_relatoriomedico", "add_relatoriomedico",
        ],
    },
    {
        "name": "Surgeon",
        "permissions": [
            "view_paciente", "view_consulta", "view_agenda",
            "view_cirurgia", "add_cirurgia", "change_cirurgia", "list_cirurgia",
            "view_internamento", "view_procedimento", "add_procedimento",
        ],
    },
    {
        "name": "Registered Nurse",
        "permissions": [
            "view_paciente", "list_paciente", "view_agenda",
            "view_dadovital", "add_dadovital",
            "view_observacaoclinica", "add_observacaoclinica",
            "view_medicacaocorrente", "add_medicacaocorrente",
            "view_vacina", "add_vacina",
        ],
    },
    {
        "name": "Nurse Manager",
        "permissions": [
            "view_paciente", "list_paciente", "view_agenda",
            "view_dadovital", "add_dadovital", "change_dadovital",
            "view_observacaoclinica", "add_observacaoclinica", "change_observacaoclinica",
            "view_medicacaocorrente", "add_medicacaocorrente", "change_medicacaocorrente",
            "view_internamento", "list_internamento",
        ],
    },
    {
        "name": "Midwife",
        "permissions": [
            "view_paciente", "view_consulta", "add_consulta",
            "view_dadovital", "add_dadovital", "view_internamento",
        ],
    },
    {
        "name": "Physiotherapist",
        "permissions": [
            "view_paciente", "view_consulta", "add_consulta",
            "view_procedimento", "add_procedimento",
        ],
    },
    {
        "name": "Psychologist",
        "permissions": [
            "view_paciente", "view_consulta", "add_consulta",
            "view_observacaoclinica", "add_observacaoclinica",
        ],
    },
    {
        "name": "Dietitian and Nutritionist",
        "permissions": ["view_paciente", "view_consulta", "add_consulta", "view_dadovital"],
    },
]

# ============================================================
# FARMÁCIA (perfil clínico - ver farmacia/profiles.py para o
# módulo dedicado de dispensação)
# ============================================================

PHARMACY_PROFILES = [
    {
        "name": "Pharmacist",
        "permissions": [
            "view_receitamedica", "list_receitamedica",
            "view_itemreceita", "add_itemreceita",
            "view_medicamento", "list_medicamento",
            "view_medicacaocorrente", "view_alergiamedicamentosa",
        ],
    },
    {
        "name": "Pharmacy Technician",
        "permissions": [
            "view_receitamedica", "view_itemreceita",
            "view_medicamento", "list_medicamento",
        ],
    },
]

# ============================================================
# EXAMES / DIAGNÓSTICO
# ============================================================

DIAGNOSTIC_PROFILES = [
    {
        "name": "Medical Laboratory Technician",
        "permissions": [
            "view_pedidoexamemedico", "list_pedidoexamemedico",
            "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
            "view_examemedico", "view_tipoexamemedico",
        ],
    },
    {
        "name": "Medical Laboratory Scientist",
        "permissions": [
            "view_pedidoexamemedico", "list_pedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico", "change_resultadoexamemedico",
            "view_paramentroresultadoexamemedico", "add_paramentroresultadoexamemedico",
        ],
    },
    {
        "name": "Radiologic Technologist",
        "permissions": [
            "view_pedidoexamemedico", "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
        ],
    },
    {
        "name": "Medical Imaging Technologist",
        "permissions": [
            "view_pedidoexamemedico", "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
        ],
    },
    {
        "name": "Diagnostic Medical Sonographer",
        "permissions": [
            "view_pedidoexamemedico", "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
        ],
    },
    {
        "name": "CT Technologist",
        "permissions": [
            "view_pedidoexamemedico", "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
        ],
    },
    {
        "name": "MRI Technologist",
        "permissions": [
            "view_pedidoexamemedico", "view_itempedidoexamemedico", "change_itempedidoexamemedico",
            "view_resultadoexamemedico", "add_resultadoexamemedico",
        ],
    },
]

# ============================================================
# ATENDIMENTO
# ============================================================

FRONT_OFFICE_PROFILES = [
    {
        "name": "Medical Secretary",
        "permissions": [
            "view_paciente", "add_paciente",
            "view_agenda", "add_agenda", "change_agenda",
            "view_consulta", "list_consulta",
        ],
    },
    {
        "name": "Patient Services Coordinator",
        "permissions": [
            "view_paciente", "add_paciente", "change_paciente", "list_paciente",
            "view_agenda", "list_agenda",
        ],
    },
    {
        "name": "Triage Coordinator",
        "permissions": ["view_paciente", "view_dadovital", "add_dadovital", "view_agenda"],
    },
]

# ============================================================
# FINANCEIRO
#
# Deliberadamente sem permissões de modelos clínicos (Consulta,
# Diagnostico, etc.) - CLAUDE.md #51 (Health billing boundary): quem
# trata de dinheiro em saude vê o mínimo clínico necessário para
# contexto (paciente), nunca o registo clínico em si.
# ============================================================

FINANCE_PROFILES = [
    {"name": "Finance Manager", "permissions": ["view_paciente", "view_dashboard_saude_clinica"]},
    {"name": "Accountant", "permissions": ["view_paciente", "view_dashboard_saude_clinica"]},
    {"name": "Treasurer", "permissions": ["view_paciente"]},
    {"name": "Billing Specialist", "permissions": ["view_paciente", "view_consulta"]},
    {"name": "Auditor", "permissions": [
        "view_paciente", "view_consulta", "view_agenda", "view_receitamedica",
        "view_pedidoexamemedico", "view_resultadoexamemedico", "view_internamento",
        "view_dashboard_saude_clinica",
    ]},
]

# ============================================================
# GESTÃO CLÍNICA
# ============================================================

MANAGEMENT_PROFILES = [
    {
        "name": "Healthcare Administrator",
        "permissions": [
            "view_paciente", "view_consulta", "view_agenda", "view_medico",
            "view_receitamedica", "view_internamento", "view_dashboard_saude_clinica",
        ],
    },
    {
        "name": "Medical Director",
        "permissions": [
            "view_paciente", "view_consulta", "view_agenda", "view_medico",
            "view_diagnostico", "view_internamento", "view_cirurgia",
            "view_dashboard_saude_clinica",
        ],
    },
    {
        "name": "Clinical Coordinator",
        "permissions": [
            "view_paciente", "view_consulta", "view_agenda", "view_medico",
            "view_dashboard_saude_clinica",
        ],
    },
]

SAUDE_PROFILES = (
    CLINICAL_PROFILES
    + PHARMACY_PROFILES
    + DIAGNOSTIC_PROFILES
    + FRONT_OFFICE_PROFILES
    + FINANCE_PROFILES
    + MANAGEMENT_PROFILES
)

# Nome antigo (PT, já em produção via group_creator()) -> nome novo
# (EN) - ver group_creator()'s rename_from: só é usado se o grupo
# antigo já existir; instalações novas criam directamente em inglês.
SAUDE_RENAME_FROM = {
    "Medical Receptionist": "Recepcionista",
    "General Practitioner": "Médico Geral",
    "Specialist Physician": "Médico Especialista",
    "Surgeon": "Cirurgião",
    "Registered Nurse": "Enfermeiro",
    "Nurse Manager": "Enfermeiro Chefe",
    "Midwife": "Parteira",
    "Physiotherapist": "Fisioterapeuta",
    "Psychologist": "Psicólogo",
    "Dietitian and Nutritionist": "Nutricionista",
    "Pharmacist": "Farmacêutico",
    "Pharmacy Technician": "Técnico de Farmácia",
    "Medical Laboratory Technician": "Técnico de Laboratório",
    "Radiologic Technologist": "Técnico de Radiologia",
    "Medical Imaging Technologist": "Técnico de Imagiologia",
    "Diagnostic Medical Sonographer": "Técnico de Ecografia",
    "CT Technologist": "Técnico de Tomografia",
    "MRI Technologist": "Técnico de Ressonância",
    "Medical Laboratory Scientist": "Analista Clínico",
    "Medical Secretary": "Secretária Clínica",
    "Patient Services Coordinator": "Gestor de Pacientes",
    "Triage Coordinator": "Triagem",
    "Healthcare Administrator": "Administrador",
    "Finance Manager": "Gestor Financeiro",
    "Accountant": "Contabilista",
    "Treasurer": "Tesoureiro",
    "Billing Specialist": "Faturamento",
    "Auditor": "Auditor",
    "Medical Director": "Diretor Clínico",
    "Clinical Coordinator": "Coordenador Médico",
}
