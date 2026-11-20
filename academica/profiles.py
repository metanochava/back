"""Profiles of the academica module (the former ensino) (group_creator, additive by name).

- School Secretary: students, guardians and enrolments (reads the structure
  and classes to enrol).
- Academic Director: the academic structure and the classes (reads students
  and enrolments).
- Teacher: assessments, grades and attendance of the classes.
- Student / Guardian: the portal only (enrolments/mine, grades/mine,
  studentattendances/mine, tuitioncharges/mine) - their own records, or their
  students', resolved from the signed-in user's Person; never the list of
  every student.
- Admin (the Entity's): everything of the module.
"""

_CRUD = lambda model: [f"{a}_{model}" for a in ("view", "list", "add", "change", "delete")]  # noqa: E731
_READ = lambda model: [f"{a}_{model}" for a in ("view", "list")]  # noqa: E731

STRUCTURE = ("gradingscale", "educationlevel", "programme", "gradelevel", "subject", "curriculumitem",
             "academicyear", "academicperiod", "classgroup")
ENROLMENT_ACTIONS = ["activate_enrolment", "suspend_enrolment", "transfer_enrolment", "complete_enrolment",
                     "cancel_enrolment", "change_class_enrolment"]

SECRETARY = [
    *_CRUD("student"), *_CRUD("guardian"), "view_enrolment", "list_enrolment", "add_enrolment", *ENROLMENT_ACTIONS,
    "list_enrolmentstatuschange", "view_enrolmentstatuschange",
    *[p for model in STRUCTURE for p in _READ(model)],
    # registering the student's Person, documents and contacts
    "add_person", "view_person", "add_document", "add_personcontact",
]
DIRECTOR = [*[p for model in STRUCTURE for p in _CRUD(model)], *_READ("student"), *_READ("guardian"),
            *_READ("enrolment")]

# second delivery: teaching, assessments, grades, attendance, tuition. The
# report card, a grade's history and the class attendance use view_enrolment,
# view_grade and add_studentattendance (their actions name them).
TEACHER = [*_CRUD("assessment"), "view_grade", "list_grade", "add_grade", "change_grade",
           *_CRUD("studentattendance"), *_READ("teachingassignment"), *_READ("classgroup"),
           *_READ("enrolment"), *_READ("student"), *_READ("subject"), *_READ("academicperiod")]
SECRETARY += [*_READ("tuitioncharge"), "charge_month_enrolment", *_READ("studentattendance"),
              *_READ("grade")]
DIRECTOR += [*_CRUD("teachingassignment"), *_CRUD("tuitionrule"), *_READ("tuitioncharge"), *_READ("assessment"),
             *_READ("grade"), *_READ("studentattendance")]

# third delivery (2026-11-14): timetables, documents, transfers, year-end.
# The PDFs use view_enrolment / view_student / view_classgroup; the student's
# timetable in the portal uses view_own_enrolment.
DIRECTOR += [*_CRUD("timetableslot"), "close_year_academicyear", *_READ("priorschooling")]
SECRETARY += [*_READ("timetableslot"), *_CRUD("priorschooling")]
TEACHER += [*_READ("timetableslot")]

# the portal: own records only (academica.services.portal_service)
PORTAL = ["view_own_enrolment", "view_own_grade", "view_own_studentattendance", "view_own_tuitioncharge"]

ENSINO_PROFILES = [
    {"name": "School Secretary", "permissions": SECRETARY},
    {"name": "Academic Director", "permissions": DIRECTOR},
    {"name": "Teacher", "permissions": TEACHER},
    {"name": "Student", "permissions": PORTAL},
    {"name": "Guardian", "permissions": PORTAL},
    {"name": "Admin", "permissions": sorted(set(SECRETARY + DIRECTOR + TEACHER))},
]
