# the pedagogica module's menu (front/src/modules/pedagogica)
ALL = [{
    'MENU': "Pedagogy",
    'ICON': "cast_for_education",
    'SUBMENUS': [
        {"icon": "draw", "menu": "Digital board", "role": "list_lesson", "route": "list_lesson"},
        {"icon": "history_edu", "menu": "My lessons", "role": "view_own_lesson", "route": "view_own_lesson"},
        {"icon": "event_note", "menu": "Lesson plans", "role": "list_lessonplan", "route": "list_lessonplan"},
        {"icon": "folder_open", "menu": "Materials", "role": "list_material", "route": "list_material"},
        {"icon": "assignment", "menu": "Assignments", "role": "list_assignment", "route": "list_assignment"},
        {"icon": "event", "menu": "Pedagogical calendar", "role": "list_calendarevent", "route": "list_calendarevent"},
        {"icon": "insights", "menu": "Progress notes", "role": "list_progressnote", "route": "list_progressnote"},
        {"icon": "campaign", "menu": "Class messages", "role": "list_classmessage", "route": "list_classmessage"},
    ],
}]
