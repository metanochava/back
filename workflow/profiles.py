"""Profiles of workflow (group_creator()). Approving a step is NOT given
here: each step names the permission its approvers need (e.g.
approve_purchaseorder), so who approves follows the profiles of the module
that owns the object."""

READ = ["view_workflowinstance", "list_workflowinstance", "inbox_workflowinstance", "decide_workflowinstance",
        "cancel_workflowinstance", "add_workflowinstance"]

WORKFLOW_PROFILES = [
    {
        "name": "Admin",
        "permissions": [
            "view_workflowdefinition", "list_workflowdefinition", "add_workflowdefinition",
            "change_workflowdefinition", "delete_workflowdefinition",
            "view_workflowstep", "list_workflowstep", "add_workflowstep", "change_workflowstep", "delete_workflowstep",
            *READ, "cancel_any_workflowinstance",
        ],
    },
    {"name": "Purchasing Manager", "permissions": [*READ]},
    {"name": "Finance Manager", "permissions": [*READ]},
    {"name": "Buyer", "permissions": [*READ]},
    {"name": "Auditor", "permissions": ["view_workflowinstance", "list_workflowinstance"]},
]

ACTION_PERMISSIONS = {
    "workflowinstance": [
        "decide_workflowinstance", "cancel_workflowinstance", "inbox_workflowinstance", "cancel_any_workflowinstance",
    ],
}
