# Phone tabs this module suggests (django_resaas core/services/mobile_tab_service.py):
# shown only to profiles holding the permission; lower order first.
TABS = [
    {"label": "My school life", "icon": "backpack", "route": "view_own_enrolment", "permission": "view_own_enrolment", "order": 10},
    {"label": "Attendance", "icon": "fact_check", "route": "list_studentattendance", "permission": "list_studentattendance", "order": 20},
    {"label": "Grades", "icon": "grading", "route": "list_grade", "permission": "list_grade", "order": 30},
    {"label": "Timetable", "icon": "calendar_view_week", "route": "list_timetableslot", "permission": "list_timetableslot", "order": 40},
    {"label": "Students", "icon": "badge", "route": "list_student", "permission": "list_student", "order": 50},
]
