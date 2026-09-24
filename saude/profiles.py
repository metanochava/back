
"""
Perfis (Group templates) essenciais do módulo saude.

PRINCÍPIO
---------
Group representa um PERFIL DE ACESSO e não necessariamente uma profissão.

Exemplos:
    Doctor              -> perfil de acesso
    Nurse               -> perfil de acesso
    Surgeon             -> profissão/especialidade, não precisa de Group próprio
    Cardiologist        -> especialidade, não precisa de Group próprio
    Physiotherapist     -> profissão, criar Group específico apenas se as
                           permissões realmente justificarem

A autorização nunca deve depender do nome do Group.

Os nomes servem apenas como templates de permissões por omissão.
A segurança continua baseada nas permissions efectivas.

Um administrador pode criar Groups adicionais conforme a necessidade
da organização.

IMPORTANTE:
- Reutilizar Groups existentes.
- Preservar Group.id.
- Seeds devem ser idempotentes.
- Não remover permissões personalizadas.
- Não usar Group.name como controlo de segurança.
"""


# ============================================================
# CLINICAL
# ============================================================

CLINICAL_PROFILES = [
    {
        "name": "Doctor",
        "permissions": [
            "view_paciente",
            "list_paciente",

            "view_consulta",
            "add_consulta",
            "change_consulta",
            "list_consulta",

            "view_agenda",
            "list_agenda",

            "view_diagnostico",
            "add_diagnostico",

            "view_receitamedica",
            "add_receitamedica",

            "view_atestadomedico",
            "add_atestadomedico",

            "view_pedidoexamemedico",
            "add_pedidoexamemedico",

            "view_dadovital",
            "add_dadovital",

            "view_resultadoexamemedico",
            "lab_evolution_paciente",

            "view_relatoriomedico",
            "add_relatoriomedico",

            "view_dashboard_saude_doctor",
        ],
    },

    {
        "name": "Nurse",
        "permissions": [
            "view_paciente",
            "list_paciente",

            "view_agenda",

            "view_dadovital",
            "add_dadovital",

            "view_observacaoclinica",
            "add_observacaoclinica",

            "view_medicacaocorrente",
            "add_medicacaocorrente",

            "view_vacina",
            "add_vacina",

            "view_dashboard_saude_nursing",
        ],
    },
]


# ============================================================
# RECEPTION / FRONT OFFICE
# ============================================================

FRONT_OFFICE_PROFILES = [
    {
        "name": "Medical Receptionist",
        "permissions": [
            "view_paciente",
            "add_paciente",
            "list_paciente",

            "view_agenda",
            "add_agenda",
            "change_agenda",
            "list_agenda",

            "view_dashboard_saude_reception",

            # Exam-only workflow
            "view_pedidoexamemedico",
            "add_pedidoexamemedico",
            "add_itempedidoexamemedico",
            "view_examemedico",
            "check_in_pedidoexamemedico",

            # Patient Portal
            "grant_portal_access_paciente",
        ],
    },
]


# ============================================================
# LABORATORY
# ============================================================

LABORATORY_PROFILES = [
    {
        "name": "Medical Laboratory Technician",
        "permissions": [
            "view_pedidoexamemedico",
            "list_pedidoexamemedico",

            "view_itempedidoexamemedico",
            "change_itempedidoexamemedico",

            "view_resultadoexamemedico",
            "add_resultadoexamemedico",

            "view_examemedico",
            "view_tipoexamemedico",

            "check_in_pedidoexamemedico",

            "collect_itempedidoexamemedico",
            "reject_sample_itempedidoexamemedico",
            "record_result_itempedidoexamemedico",

            "view_examparameter",

            "view_dashboard_saude_laboratory",
        ],
    },

    {
        "name": "Medical Laboratory Scientist",
        "permissions": [
            "view_pedidoexamemedico",
            "list_pedidoexamemedico",

            "view_itempedidoexamemedico",
            "change_itempedidoexamemedico",

            "view_resultadoexamemedico",
            "add_resultadoexamemedico",
            "change_resultadoexamemedico",

            "check_in_pedidoexamemedico",

            "collect_itempedidoexamemedico",
            "reject_sample_itempedidoexamemedico",
            "record_result_itempedidoexamemedico",

            "lab_evolution_paciente",

            # Exam / parameter configuration
            "view_examparameter",
            "add_examparameter",
            "change_examparameter",

            "view_examreferencerange",
            "add_examreferencerange",
            "change_examreferencerange",

            # Higher-level laboratory operations
            "validate_resultadoexamemedico",
            "release_resultadoexamemedico",
            "amend_resultadoexamemedico",

            "view_dashboard_saude_laboratory",
        ],
    },
]


# ============================================================
# PHARMACY
# ============================================================

PHARMACY_PROFILES = [
    {
        "name": "Pharmacist",
        "permissions": [
            "view_receitamedica",
            "list_receitamedica",

            "view_itemreceita",
            "add_itemreceita",

            "view_medicamento",
            "list_medicamento",

            "view_medicacaocorrente",
            "view_alergiamedicamentosa",

            # Add pharmacy dashboard permission here when/if
            # the real permission exists in the RESAAS permission sync.
        ],
    },
]


# ============================================================
# BILLING / CASHIER
# ============================================================

FINANCE_PROFILES = [
    {
        "name": "Cashier",
        "permissions": [
            # Keep clinical access intentionally minimal.
            "view_paciente",

            # IMPORTANT:
            # Add the REAL billing/payment/invoice permissions here
            # after verifying the existing financial module.
            #
            # Do not invent health-specific financial permissions if
            # they already exist in the finance/billing infrastructure.
        ],
    },
]


# ============================================================
# HEALTH MANAGEMENT
# ============================================================

MANAGEMENT_PROFILES = [
    {
        "name": "Healthcare Administrator",
        "permissions": [
            "view_paciente",
            "view_consulta",
            "view_agenda",
            "view_medico",
            "view_receitamedica",
            "view_internamento",

            "view_dashboard_saude_clinica",
        ],
    },
]


# ============================================================
# ALL DEFAULT HEALTH PROFILES
# ============================================================

SAUDE_PROFILES = (
    CLINICAL_PROFILES
    + FRONT_OFFICE_PROFILES
    + LABORATORY_PROFILES
    + PHARMACY_PROFILES
    + FINANCE_PROFILES
    + MANAGEMENT_PROFILES
)


# ============================================================
# MIGRATION / RENAME MAP
# ============================================================
#
# Existing installations may already contain the old Groups.
#
# group_creator(rename_from=...) must preserve:
#
#   Group.id
#   BranchUserGroup
#   EntityGroup
#   permissions
#
# Only the name changes.
#
# Do NOT delete the old Group and create another one.
# ============================================================

SAUDE_RENAME_FROM = {
    # --------------------------------------------------------
    # Clinical
    # --------------------------------------------------------

    "Doctor": "Médico Geral",
    "Nurse": "Enfermeiro",

    # --------------------------------------------------------
    # Reception
    # --------------------------------------------------------

    "Medical Receptionist": "Recepcionista",

    # --------------------------------------------------------
    # Laboratory
    # --------------------------------------------------------

    "Medical Laboratory Technician": "Técnico de Laboratório",
    "Medical Laboratory Scientist": "Analista Clínico",

    # --------------------------------------------------------
    # Pharmacy
    # --------------------------------------------------------

    "Pharmacist": "Farmacêutico",

    # --------------------------------------------------------
    # Finance
    # --------------------------------------------------------

    "Cashier": "Faturamento",

    # --------------------------------------------------------
    # Management
    # --------------------------------------------------------

    "Healthcare Administrator": "Administrador",
}

