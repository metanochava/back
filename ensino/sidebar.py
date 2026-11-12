# the ensino module's menu (the routes are front/src/pages/ensino)
ALL = [{
'MENU' : "Education",
'ICON' : "school",

'SUBMENUS' : [
    {"icon": "badge", "menu": "Students", "role": "list_student", "route": "list_student",
     "add_role": "add_student", "add_route": "add_student"},
    {"icon": "how_to_reg", "menu": "Enrolments", "role": "list_enrolment", "route": "list_enrolment"},
    {"icon": "groups", "menu": "Classes", "role": "list_classgroup", "route": "list_classgroup",
     "add_role": "add_classgroup", "add_route": "add_classgroup"},
    {"icon": "assignment", "menu": "Assessments", "role": "list_assessment", "route": "list_assessment"},
    {"icon": "grading", "menu": "Grades", "role": "list_grade", "route": "list_grade"},
    {"icon": "fact_check", "menu": "Attendance", "role": "list_studentattendance", "route": "list_studentattendance"},
    {"icon": "co_present", "menu": "Teaching assignments", "role": "list_teachingassignment", "route": "list_teachingassignment"},
    {
        "icon": "payments",
        "menu": "Tuition",
        "role": "list_tuitioncharge",
        "submenu": [
            {"icon": "rule", "menu": "Tuition rules", "role": "list_tuitionrule", "route": "list_tuitionrule"},
            {"icon": "receipt_long", "menu": "Tuition charges", "role": "list_tuitioncharge", "route": "list_tuitioncharge"},
        ],
    },
    {
        "icon": "account_tree",
        "menu": "Academic structure",
        "role": "list_programme",
        "submenu": [
            {"icon": "event", "menu": "Academic years", "role": "list_academicyear", "route": "list_academicyear"},
            {"icon": "date_range", "menu": "Academic periods", "role": "list_academicperiod", "route": "list_academicperiod"},
            {"icon": "stairs", "menu": "Education levels", "role": "list_educationlevel", "route": "list_educationlevel"},
            {"icon": "menu_book", "menu": "Programmes", "role": "list_programme", "route": "list_programme"},
            {"icon": "format_list_numbered", "menu": "Grade levels", "role": "list_gradelevel", "route": "list_gradelevel"},
            {"icon": "subject", "menu": "Subjects", "role": "list_subject", "route": "list_subject"},
            {"icon": "checklist", "menu": "Curriculum", "role": "list_curriculumitem", "route": "list_curriculumitem"},
            {"icon": "grade", "menu": "Grading scales", "role": "list_gradingscale", "route": "list_gradingscale"},
        ],
    },
]
}]
