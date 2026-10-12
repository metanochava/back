"""Profiles (Group templates) of crm (group_creator()). "Sales Manager" and
"Sales Representative" are the same profiles sales uses (additive)."""


def _crud(model):
    return [f"view_{model}", f"list_{model}", f"add_{model}", f"change_{model}", f"delete_{model}"]


READ = [
    "view_stage", "list_stage", "view_lead", "list_lead", "view_opportunity", "list_opportunity",
    "view_activity", "list_activity", "pipeline_opportunity",
]

LEAD_ACTIONS = ["mark_contacted_lead", "qualify_lead", "disqualify_lead", "reopen_lead", "convert_lead"]

CRM_PROFILES = [
    {
        "name": "Sales Manager",
        "permissions": [
            *READ, *_crud("stage"), *_crud("lead"), *_crud("opportunity"), *_crud("activity"),
            *LEAD_ACTIONS, "create_defaults_stage", "move_opportunity", "complete_activity",
        ],
    },
    {
        "name": "Sales Representative",
        "permissions": [
            *READ, "add_lead", "change_lead", "add_opportunity", "change_opportunity",
            "add_activity", "change_activity",
            *LEAD_ACTIONS, "move_opportunity", "complete_activity",
        ],
    },
    {
        "name": "Customer Service Representative",
        "permissions": ["view_lead", "list_lead", "add_lead", "change_lead", "mark_contacted_lead",
                        "view_activity", "list_activity", "add_activity", "complete_activity"],
    },
    {"name": "Auditor", "permissions": [*READ]},
]

ACTION_PERMISSIONS = {
    "lead": LEAD_ACTIONS,
    "stage": ["create_defaults_stage"],
    "opportunity": ["move_opportunity", "pipeline_opportunity"],
    "activity": ["complete_activity"],
}
