ALL = [{
    'MENU': "Approvals",
    'ICON': "approval",

    'SUBMENUS': [
        {"icon": "inbox", "menu": "My approvals", "role": "inbox_workflowinstance", "route": "view_approval_inbox"},
        {"icon": "fact_check", "menu": "Approval requests", "role": "list_workflowinstance", "route": "list_workflowinstance"},
        {"icon": "account_tree", "menu": "Workflows", "role": "list_workflowdefinition", "route": "list_workflowdefinition"},
        {"icon": "format_list_numbered", "menu": "Workflow steps", "role": "list_workflowstep", "route": "list_workflowstep"},
    ],
}]
