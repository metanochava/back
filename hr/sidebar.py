ALL = [{
'MENU' :"Hr",
'ICON' :"groups",
'SUBMENUS' :[
    {
        "menu": "Dashboard",
        "icon": "dashboard",
        "role": "view_hr_dashboard",
        "route": "view_hr_dashboard",
    },
    {
        "menu": "Employee",
        "icon": "person",  # 🔥 segurança
        "role": "list_employee",
        "route": "list_employee",
        "add_role": "add_employee",
        "add_route": "add_employee",
        # "crud": {"module": "hr", "model": "Employee"},
    },

    # 🏢 ORGANIZAÇÃO (grupo: gerador de menu suporta "submenu" aninhado,
    # ver "Dev" em django_resaas/saas/sidebar.py)
    {
        "menu": "Organization",
        "icon": "corporate_fare",
        "role": "list_department",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_organizacao",
                "route": "view_dashboard_hr_organizacao",
            },
            {
                "menu": "Department",
                "icon": "corporate_fare",
                "role": "list_department",
                "route": "list_department",
                "add_role": "add_department",
                "add_route": "add_department",
                # "crud": {"module": "hr", "model": "Department"},
            },
            {
                "menu": "Job Position",
                "icon": "badge",
                "role": "list_jobposition",
                "route": "list_jobposition",
                "add_role": "add_jobposition",
                "add_route": "add_jobposition",
                # "crud": {"module": "hr", "model": "JobPosition"},
            },
            {
                "menu": "Job Grade",
                "icon": "military_tech",
                "role": "list_jobgrade",
                "route": "list_jobgrade",
                "add_role": "add_jobgrade",
                "add_route": "add_jobgrade",
                # "crud": {"module": "hr", "model": "JobGrade"},
            },
            {
                "menu": "Contract",
                "icon": "assignment",
                "role": "list_contract",
                "route": "list_contract",
                "add_role": "add_contract",
                "add_route": "add_contract",
                # "crud": {"module": "hr", "model": "Contract"},
            },
            {
                "menu": "Specialty",
                "icon": "star",
                "role": "list_specialty",
                "route": "list_specialty",
                "add_role": "add_specialty",
                "add_route": "add_specialty",
                # "crud": {"module": "hr", "model": "Specialty"},
            },
            {
                "menu": "Employee Specialty",
                "icon": "workspace_premium",
                "role": "list_employeespecialty",
                "route": "list_employeespecialty",
                "add_role": "add_employeespecialty",
                "add_route": "add_employeespecialty",
                # "crud": {"module": "hr", "model": "EmployeeSpecialty"},
            },
        ],
    },

    # 🕒 TEMPO & PRESENÇA (grupo)
    {
        "menu": "Time & Attendance",
        "icon": "schedule",
        "role": "list_shift",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_tempo_presenca",
                "route": "view_dashboard_hr_tempo_presenca",
            },
            {
                "menu": "Shift",
                "icon": "schedule",
                "role": "list_shift",
                "route": "list_shift",
                "add_role": "add_shift",
                "add_route": "add_shift",
                # "crud": {"module": "hr", "model": "Shift"},
            },
            {
                "menu": "Employee Shift",
                "icon": "event_available",
                "role": "list_employeeshift",
                "route": "list_employeeshift",
                "add_role": "add_employeeshift",
                "add_route": "add_employeeshift",
                # "crud": {"module": "hr", "model": "EmployeeShift"},
            },
            {
                "menu": "Shift Schedule",
                "icon": "calendar_month",
                "role": "list_shiftschedule",
                "route": "list_shiftschedule",
                "add_role": "add_shiftschedule",
                "add_route": "add_shiftschedule",
                # "crud": {"module": "hr", "model": "ShiftSchedule"},
            },
            {
                "menu": "Attendance",
                "icon": "how_to_reg",
                "role": "list_attendance",
                "route": "list_attendance",
                "add_role": "add_attendance",
                "add_route": "add_attendance",
                # "crud": {"module": "hr", "model": "Attendance"},
            },
            {
                "menu": "Holiday",
                "icon": "event_busy",
                "role": "list_holiday",
                "route": "list_holiday",
                "add_role": "add_holiday",
                "add_route": "add_holiday",
                # "crud": {"module": "hr", "model": "Holiday"},
            },
        ],
    },

    # 💰 SALÁRIO & FOLHA DE PAGAMENTO (grupo)
    {
        "menu": "Salary & Payroll",
        "icon": "payments",
        "role": "list_salarycomponent",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_salario_folha",
                "route": "view_dashboard_hr_salario_folha",
            },
            {
                "menu": "Salary Component",
                "icon": "payments",
                "role": "list_salarycomponent",
                "route": "list_salarycomponent",
                "add_role": "add_salarycomponent",
                "add_route": "add_salarycomponent",
                # "crud": {"module": "hr", "model": "SalaryComponent"},
            },
            {
                "menu": "Employee Salary",
                "icon": "attach_money",
                "role": "list_employeesalary",
                "route": "list_employeesalary",
                "add_role": "add_employeesalary",
                "add_route": "add_employeesalary",
                # "crud": {"module": "hr", "model": "EmployeeSalary"},
            },
            {
                "menu": "Employee Salary Component",
                "icon": "money",
                "role": "list_employeesalarycomponent",
                "route": "list_employeesalarycomponent",
                "add_role": "add_employeesalarycomponent",
                "add_route": "add_employeesalarycomponent",
                # "crud": {"module": "hr", "model": "EmployeeSalaryComponent"},
            },
            {
                "menu": "Payroll Period",
                "icon": "date_range",
                "role": "list_payrollperiod",
                "route": "list_payrollperiod",
                "add_role": "add_payrollperiod",
                "add_route": "add_payrollperiod",
                # "crud": {"module": "hr", "model": "PayrollPeriod"},
            },
            {
                "menu": "Payroll Run",
                "icon": "play_circle",
                "role": "list_payrollperiod",
                "route": "payroll_run",
                # No add_role/add_route: this is the controlled Generate -> Review
                # -> Confirm workflow (pedido secção 78), not a generic CRUD add
                # page - see pages/hr/payroll/PayrollRunPage.vue.
            },
            {
                "menu": "Payroll",
                "icon": "receipt_long",
                "role": "list_payroll",
                "route": "list_payroll",
                "add_role": "add_payroll",
                "add_route": "add_payroll",
                # "crud": {"module": "hr", "model": "Payroll"},
            },
            {
                "menu": "Payroll Item",
                "icon": "list_alt",
                "role": "list_payrollitem",
                "route": "list_payrollitem",
                "add_role": "add_payrollitem",
                "add_route": "add_payrollitem",
                # "crud": {"module": "hr", "model": "PayrollItem"},
            },
            {
                "menu": "Payslip",
                "icon": "receipt",
                "role": "list_payslip",
                "route": "list_payslip",
                "add_role": "add_payslip",
                "add_route": "add_payslip",
                # "crud": {"module": "hr", "model": "Payslip"},
            },
        ],
    },

    # 🏖️ AUSÊNCIAS (grupo)
    {
        "menu": "Absences",
        "icon": "beach_access",
        "role": "list_leavetype",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_ausencias",
                "route": "view_dashboard_hr_ausencias",
            },
            {
                "menu": "Leave Type",
                "icon": "beach_access",
                "role": "list_leavetype",
                "route": "list_leavetype",
                "add_role": "add_leavetype",
                "add_route": "add_leavetype",
                # "crud": {"module": "hr", "model": "LeaveType"},
            },
            {
                "menu": "Leave Calendar",
                "icon": "event_note",
                "role": "list_leaverequest",
                "route": "leave_calendar",
                # No add_role/add_route on purpose: LeaveRequest has no generic
                # add page - creation happens from EmployeeProfilePage's Leave
                # tab (status/approval are workflow-controlled, not free CRUD -
                # see hr/serializers/leave_request.py).
            },
            {
                "menu": "Leave Approvals",
                "icon": "fact_check",
                "role": "approve_leaverequest",
                "route": "leave_approvals",
            },
            {
                "menu": "Leave Balance",
                "icon": "account_balance_wallet",
                "role": "list_leavebalanceentry",
                "route": "list_leavebalanceentry",
                "add_role": "add_leavebalanceentry",
                "add_route": "add_leavebalanceentry",
                # "crud": {"module": "hr", "model": "LeaveBalanceEntry"},
            },
        ],
    },

    # 🧑‍💼 RECRUTAMENTO (grupo)
    {
        "menu": "Recruitment",
        "icon": "work",
        "role": "list_jobopening",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_recrutamento",
                "route": "view_dashboard_hr_recrutamento",
            },
            {
                "menu": "Job Opening",
                "icon": "work",
                "role": "list_jobopening",
                "route": "list_jobopening",
                "add_role": "add_jobopening",
                "add_route": "add_jobopening",
                # "crud": {"module": "hr", "model": "JobOpening"},
            },
            {
                "menu": "Candidate",
                "icon": "person_search",
                "role": "list_candidate",
                "route": "list_candidate",
                "add_role": "add_candidate",
                "add_route": "add_candidate",
                # "crud": {"module": "hr", "model": "Candidate"},
            },
            {
                "menu": "Recruitment Pipeline",
                "icon": "view_kanban",
                "role": "list_application",
                "route": "recruitment_pipeline",
                # No add_role/add_route: the pipeline board itself doesn't create
                # applications - see the "New application" action inside it
                # (creates via the normal Application add form/route below).
            },
            {
                "menu": "Application",
                "icon": "assignment_ind",
                "role": "list_application",
                "route": "list_application",
                "add_role": "add_application",
                "add_route": "add_application",
                # "crud": {"module": "hr", "model": "Application"},
            },
            {
                "menu": "Interview",
                "icon": "record_voice_over",
                "role": "list_interview",
                "route": "list_interview",
                "add_role": "add_interview",
                "add_route": "add_interview",
                # "crud": {"module": "hr", "model": "Interview"},
            },
        ],
    },

    # 📋 ONBOARDING (grupo)
    {
        "menu": "Onboarding",
        "icon": "checklist",
        "role": "list_onboardingtemplate",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_onboarding",
                "route": "view_dashboard_hr_onboarding",
            },
            {
                "menu": "Onboarding Templates",
                "icon": "checklist",
                "role": "list_onboardingtemplate",
                "route": "list_onboardingtemplate",
                "add_role": "add_onboardingtemplate",
                "add_route": "add_onboardingtemplate",
                # "crud": {"module": "hr", "model": "OnboardingTemplate"},
            },
            {
                "menu": "Onboarding Template Tasks",
                "icon": "playlist_add_check",
                "role": "list_onboardingtemplatetask",
                "route": "list_onboardingtemplatetask",
                "add_role": "add_onboardingtemplatetask",
                "add_route": "add_onboardingtemplatetask",
                # "crud": {"module": "hr", "model": "OnboardingTemplateTask"},
            },
            {
                "menu": "Employee Onboardings",
                "icon": "assignment_turned_in",
                "role": "list_employeeonboarding",
                "route": "list_employeeonboarding",
                # No add_role/add_route on purpose: EmployeeOnboarding has no
                # generic add page - creation only happens via
                # EmployeeAPIView.start_onboarding (see hr/views/employee.py),
                # normally from EmployeeProfilePage's Onboarding tab.
            },
        ],
    },

    # 📈 DESEMPENHO (grupo)
    {
        "menu": "Performance",
        "icon": "trending_up",
        "role": "list_performancecycle",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_desempenho",
                "route": "view_dashboard_hr_desempenho",
            },
            {
                "menu": "Performance Cycle",
                "icon": "date_range",
                "role": "list_performancecycle",
                "route": "list_performancecycle",
                "add_role": "add_performancecycle",
                "add_route": "add_performancecycle",
                # "crud": {"module": "hr", "model": "PerformanceCycle"},
            },
            {
                "menu": "Competency",
                "icon": "psychology",
                "role": "list_competency",
                "route": "list_competency",
                "add_role": "add_competency",
                "add_route": "add_competency",
                # "crud": {"module": "hr", "model": "Competency"},
            },
            {
                "menu": "Goals",
                "icon": "flag",
                "role": "list_employeegoal",
                "route": "list_employeegoal",
                "add_role": "add_employeegoal",
                "add_route": "add_employeegoal",
                # "crud": {"module": "hr", "model": "EmployeeGoal"},
            },
            {
                "menu": "Performance Reviews",
                "icon": "rate_review",
                "role": "list_performancereview",
                "route": "list_performancereview",
                "add_role": "add_performancereview",
                "add_route": "add_performancereview",
                # "crud": {"module": "hr", "model": "PerformanceReview"},
            },
        ],
    },

    # 🎓 FORMAÇÃO (grupo)
    {
        "menu": "Training",
        "icon": "school",
        "role": "list_course",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_formacao",
                "route": "view_dashboard_hr_formacao",
            },
            {
                "menu": "Courses",
                "icon": "menu_book",
                "role": "list_course",
                "route": "list_course",
                "add_role": "add_course",
                "add_route": "add_course",
                # "crud": {"module": "hr", "model": "Course"},
            },
            {
                "menu": "Training Sessions",
                "icon": "school",
                "role": "list_trainingsession",
                "route": "list_trainingsession",
                "add_role": "add_trainingsession",
                "add_route": "add_trainingsession",
                # "crud": {"module": "hr", "model": "TrainingSession"},
                # List page is custom (enrollments + capacity + enroll action -
                # pedido secção 76) rather than AutoCrud, same reasoning as Leave
                # Calendar/Recruitment Pipeline - see
                # pages/hr/training_session/TrainingSessionLPage.vue.
            },
        ],
    },

    # 🔄 CICLO DE VIDA DO COLABORADOR (grupo)
    {
        "menu": "Employee Lifecycle",
        "icon": "compare_arrows",
        "role": "list_promotion",
        "submenu": [
            {
                "icon": "space_dashboard",
                "menu": "Dashboard",
                "role": "view_dashboard_hr_ciclo_vida",
                "route": "view_dashboard_hr_ciclo_vida",
            },
            {
                "menu": "Promotions",
                "icon": "trending_up",
                "role": "list_promotion",
                "route": "list_promotion",
                # No add_role/add_route on purpose: Promotion has no generic add
                # page - creation only happens via
                # EmployeeAPIView.apply_promotion, from EmployeeProfilePage's
                # History tab.
            },
            {
                "menu": "Transfers",
                "icon": "compare_arrows",
                "role": "list_transfer",
                "route": "list_transfer",
                # No add_role/add_route on purpose: same reasoning as Promotions -
                # only via EmployeeAPIView.apply_transfer.
            },
            {
                "menu": "Disciplinary Cases",
                "icon": "gavel",
                "role": "list_disciplinarycase",
                "route": "list_disciplinarycase",
                "add_role": "add_disciplinarycase",
                "add_route": "add_disciplinarycase",
                # Sensitive data (pedido secção 41) - gated by its own dedicated
                # permission, distinct from list_employee/change_employee, so this
                # entry only ever appears to users explicitly granted it.
            },
            {
                "menu": "Resignations",
                "icon": "logout",
                "role": "list_resignation",
                "route": "list_resignation",
                "add_role": "add_resignation",
                "add_route": "add_resignation",
                # "crud": {"module": "hr", "model": "Resignation"},
            },
            {
                "menu": "Terminations",
                "icon": "person_off",
                "role": "list_termination",
                "route": "list_termination",
                # No add_role/add_route: only via
                # EmployeeAPIView.terminate_employee.
            },
            {
                "menu": "Offboarding",
                "icon": "assignment_late",
                "role": "list_employeeoffboarding",
                "route": "list_employeeoffboarding",
                # No add_role/add_route: only via
                # EmployeeAPIView.start_offboarding, normally from
                # EmployeeProfilePage's History tab.
            },
        ],
    },
]
}]