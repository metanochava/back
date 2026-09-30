"""Perfis (Group templates) do módulo hr - mesmo mecanismo já usado
por saas/profiles.py (CORE_PROFILES) e por saude/sales/inventory/
farmacia em `/var/www/dev/back` (group_creator(), saas/core/utils/
group_creator.py).

hr nunca teve nenhum mecanismo de perfis (apps.py não tinha sequer
`ready()`) - confirmado por inspecção directa. Os 7 perfis abaixo
mapeiam directamente para os 9 dashboards analíticos já existentes em
hr/views/dashboard.py (view_dashboard_hr_organizacao/
tempo_presenca/salario_folha/ausencias/recrutamento/onboarding/
desempenho/formacao/ciclo_vida - motor de dashboard antigo, anterior
ao motor genérico `<app>/dashboard.py`, ver docs/architecture/
dashboards.md "Limitações actuais" para a nota sobre esta app ainda
não ter migrado) e para os modelos reais de hr/models/ (nenhum campo,
permissão ou workflow foi inventado - todos os codenames abaixo foram
confirmados por introspecção de Permission.objects.filter(
content_type__app_label='hr')).

Sem "Performance Management Specialist" dedicado (nem no pedido
original) - performance/goals ficam em "Training and Development
Specialist" (desenvolvimento do colaborador é a mesma disciplina),
evitando explosão de perfis (CLAUDE.md #19)."""

_CRUD = lambda model: [f"{a}_{model}" for a in ("add", "view", "change", "list")]  # noqa: E731

HR_PROFILES = [
    {
        "name": "Human Resources Manager",
        "permissions": [
            "view_hr_dashboard",
            "view_dashboard_hr_organizacao", "view_dashboard_hr_tempo_presenca",
            "view_dashboard_hr_salario_folha", "view_dashboard_hr_ausencias",
            "view_dashboard_hr_recrutamento", "view_dashboard_hr_onboarding",
            "view_dashboard_hr_desempenho", "view_dashboard_hr_formacao",
            "view_dashboard_hr_ciclo_vida",

            *_CRUD("employee"), "apply_promotion_employee", "apply_transfer_employee",
            "start_onboarding_employee", "start_offboarding_employee", "terminate_employee_employee",
            *_CRUD("department"), *_CRUD("contract"),
            *_CRUD("leaverequest"), "approve_leaverequest", "reject_leaverequest",
            *_CRUD("payroll"), "calculate_payroll", "confirm_payroll", "review_payroll", "mark_paid_payroll",
            *_CRUD("performancecycle"), *_CRUD("performancereview"),
            *_CRUD("disciplinarycase"), "start_review_disciplinarycase", "resolve_disciplinarycase",
            *_CRUD("resignation"), "accept_resignation",
            *_CRUD("termination"), *_CRUD("transfer"), *_CRUD("promotion"),
        ],
    },
    {
        "name": "HR Officer",
        "permissions": [
            "view_hr_dashboard",
            "view_dashboard_hr_organizacao", "view_dashboard_hr_tempo_presenca",
            "view_dashboard_hr_ausencias", "view_dashboard_hr_onboarding",

            *_CRUD("employee"), "view_department",
            *_CRUD("contract"), *_CRUD("attendance"),
            *_CRUD("leaverequest"), "submit_leaverequest",
            "view_leavetype", "view_leavebalanceentry",
            *_CRUD("employeeonboarding"), "complete_employeeonboarding", "cancel_employeeonboarding",
            *_CRUD("employeeonboardingtask"), "complete_employeeonboardingtask",
            *_CRUD("employeeoffboarding"), "complete_employeeoffboarding", "cancel_employeeoffboarding",
            *_CRUD("employeeoffboardingtask"),
        ],
    },
    {
        "name": "Recruitment Specialist",
        "permissions": [
            "view_dashboard_hr_recrutamento",
            *_CRUD("candidate"),
            *_CRUD("application"), "hire_application", "move_application", "schedule_interview_application",
            *_CRUD("interview"),
            "view_jobopening", "add_jobopening", "change_jobopening",
            "view_jobposition", "view_jobgrade",
        ],
    },
    {
        "name": "Payroll Specialist",
        "permissions": [
            "view_dashboard_hr_salario_folha",
            *_CRUD("payroll"), "calculate_payroll", "confirm_payroll", "review_payroll",
            "mark_paid_payroll", "cancel_payroll", "reopen_payroll",
            *_CRUD("payrollperiod"), "generate_payrollperiod",
            *_CRUD("payrollitem"), *_CRUD("payslip"),
            "view_salarycomponent", *_CRUD("employeesalary"), *_CRUD("employeesalarycomponent"),
        ],
    },
    {
        "name": "Training and Development Specialist",
        "permissions": [
            "view_dashboard_hr_formacao", "view_dashboard_hr_desempenho",
            *_CRUD("trainingsession"), "enroll_trainingsession", "cancel_session_trainingsession",
            *_CRUD("course"),
            *_CRUD("employeetraining"), "mark_completed_employeetraining", "mark_failed_employeetraining",
            *_CRUD("certification"), "view_competency",
            *_CRUD("employeegoal"), "update_progress_employeegoal",
            *_CRUD("performancecycle"), "close_cycle_performancecycle",
            *_CRUD("performancereview"), "submit_review_performancereview",
            *_CRUD("reviewcompetencyrating"),
        ],
    },
    {
        "name": "Employee Relations Officer",
        "permissions": [
            "view_dashboard_hr_ciclo_vida", "view_dashboard_hr_ausencias",
            "view_leaverequest", "list_leaverequest", "approve_leaverequest", "reject_leaverequest",
            *_CRUD("disciplinarycase"), "start_review_disciplinarycase",
            "resolve_disciplinarycase", "dismiss_disciplinarycase",
            *_CRUD("disciplinaryaction"),
            "view_resignation", "list_resignation", "accept_resignation",
            "view_termination", "list_termination",
            "view_transfer", "list_transfer",
            "view_promotion", "list_promotion",
            "view_employee",
        ],
    },
    {
        "name": "HR Administrator",
        "permissions": [
            *_CRUD("department"), *_CRUD("jobposition"), *_CRUD("jobgrade"),
            *_CRUD("leavetype"), *_CRUD("holiday"),
            *_CRUD("shift"), *_CRUD("shiftschedule"), *_CRUD("employeeshift"),
            *_CRUD("salarycomponent"),
            *_CRUD("onboardingtemplate"), *_CRUD("onboardingtemplatetask"),
            *_CRUD("competency"), *_CRUD("specialty"), *_CRUD("employeespecialty"),
        ],
    },
]

# The platform's administration profiles are defined by django_resaas
# (saas/profiles.py) and only name the core's permissions. The HR module adds
# its own to them: group_creator() is additive by profile name.
HR_PROFILES += [
    {
        "name": "Organization Administrator",
        "permissions": [
            "view_employee", "add_employee", "change_employee", "list_employee",
            "view_department", "add_department", "change_department", "list_department",
        ],
    },
    {
        "name": "Branch Administrator",
        "permissions": [
            "view_employee", "change_employee", "list_employee",
            "view_department", "list_department",
        ],
    },
]
