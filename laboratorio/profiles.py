"""Profiles of the laboratorio module (group_creator, additive by name). The
names are academica's (Teacher, Academic Director, Student, Guardian, Admin)
plus "Lab Technician": a profile is not duplicated per module."""

_CRUD = lambda model: [f"{a}_{model}" for a in ("view", "list", "add", "change", "delete")]  # noqa: E731
_READ = lambda model: [f"{a}_{model}" for a in ("view", "list")]  # noqa: E731

PLACES = ("room", "network", "workstation", "equipment", "environment")
SESSIONS = ("labsession", "seatassignment", "sessionexercise")

ACTION_PERMISSIONS = {
    "labsession": ["start_labsession", "end_labsession", "cancel_labsession", "view_own_labsession"],
    "remoteaccesssession": ["start_remoteaccesssession", "end_remoteaccesssession"],
    "virtuallab": ["network_mode_virtuallab", "create_machines_virtuallab", "power_virtuallab", "sync_virtuallab"],
    "virtualmachine": ["power_virtualmachine", "renew_password_virtualmachine", "backup_virtualmachine",
                       "view_own_virtualmachine", "renew_own_password_virtualmachine"],
}

# the virtual labs (formerly the Lab Manager): the technician runs them, the
# teacher powers and renews passwords of their class's machines
VIRTUAL_TECHNICIAN = [*_CRUD("virtuallab"), *_CRUD("virtualmachine"), "network_mode_virtuallab",
                      "create_machines_virtuallab", "power_virtuallab", "sync_virtuallab", "power_virtualmachine",
                      "renew_password_virtualmachine", "backup_virtualmachine"]
VIRTUAL_TEACHER = [*_READ("virtuallab"), *_READ("virtualmachine"), "power_virtuallab", "power_virtualmachine",
                   "renew_password_virtualmachine"]

TECHNICIAN = [*[p for model in PLACES for p in _CRUD(model)], *[p for model in SESSIONS for p in _READ(model)],
              *_READ("remoteaccesssession"), *VIRTUAL_TECHNICIAN]
TEACHER = [*[p for model in PLACES for p in _READ(model)], *[p for model in SESSIONS for p in _CRUD(model)],
           "start_labsession", "end_labsession", "cancel_labsession",
           *_READ("remoteaccesssession"), "start_remoteaccesssession", "end_remoteaccesssession", *VIRTUAL_TEACHER]
DIRECTOR = [*[p for model in (*PLACES, *SESSIONS, "remoteaccesssession", "virtuallab", "virtualmachine")
              for p in _READ(model)],
            "end_remoteaccesssession"]
FAMILY = ["view_own_labsession", "view_own_virtualmachine"]

LABORATORIO_PROFILES = [
    {"name": "Lab Technician", "permissions": TECHNICIAN},
    {"name": "Teacher", "permissions": TEACHER},
    {"name": "Academic Director", "permissions": DIRECTOR},
    {"name": "Student", "permissions": [*FAMILY, "renew_own_password_virtualmachine"]},
    {"name": "Guardian", "permissions": FAMILY},
    {"name": "Admin", "permissions": sorted(set(TECHNICIAN + TEACHER + DIRECTOR))},
]
