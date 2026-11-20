"""Profiles of the pedagogica module (group_creator, additive by name). The
names are academica's (Teacher, Academic Director, Student, Guardian, Admin):
a profile is not duplicated per module."""

_CRUD = lambda model: [f"{a}_{model}" for a in ("view", "list", "add", "change", "delete")]  # noqa: E731
_READ = lambda model: [f"{a}_{model}" for a in ("view", "list")]  # noqa: E731

MODELS = ("lessonplan", "lesson", "lessonattachment", "material", "assignment", "calendarevent", "progressnote",
          "classmessage")

ACTION_PERMISSIONS = {
    "lesson": ["publish_lesson", "unpublish_lesson", "view_own_lesson"],
    "material": ["view_own_material"],
    "assignment": ["publish_assignment", "close_assignment", "view_own_assignment", "submit_assignment"],
    "submission": ["grade_submission"],
    "calendarevent": ["view_own_calendarevent"],
    "progressnote": ["view_own_progressnote"],
    "classmessage": ["view_own_classmessage"],
}

TEACHER = [*[p for model in MODELS for p in _CRUD(model)], *_READ("submission"), "grade_submission",
           "publish_lesson", "unpublish_lesson", "publish_assignment", "close_assignment"]
DIRECTOR = [*[p for model in MODELS for p in _READ(model)], *_READ("submission"), *_CRUD("calendarevent")]
FAMILY = ["view_own_lesson", "view_own_material", "view_own_assignment", "view_own_calendarevent",
          "view_own_progressnote", "view_own_classmessage"]

PEDAGOGICA_PROFILES = [
    {"name": "Teacher", "permissions": TEACHER},
    {"name": "Academic Director", "permissions": DIRECTOR},
    {"name": "Student", "permissions": [*FAMILY, "submit_assignment"]},
    {"name": "Guardian", "permissions": FAMILY},
    {"name": "Admin", "permissions": sorted(set(TEACHER + DIRECTOR))},
]
