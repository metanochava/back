"""Profiles (Group templates) of the accounting module (group_creator()).
The finance profile names are the same ones sales/purchases use."""

def _crud(model, delete=True):
    perms = [f"view_{model}", f"list_{model}", f"add_{model}", f"change_{model}"]
    return perms + ([f"delete_{model}"] if delete else [])


READ = [
    "view_account", "list_account", "view_journal", "list_journal",
    "view_fiscalperiod", "list_fiscalperiod", "view_journalentry", "list_journalentry",
    "view_journalentryline", "list_journalentryline", "view_postingrule", "list_postingrule",
    "trial_balance_account",
]

ACCOUNTING_PROFILES = [
    {
        "name": "Accountant",
        "permissions": [
            *READ,
            *_crud("account"), *_crud("journal"),
            *_crud("journalentry"), *_crud("journalentryline"),
            "post_entry_journalentry", "reverse_journalentry",
        ],
    },
    {
        "name": "Finance Manager",
        "permissions": [
            *READ,
            *_crud("fiscalperiod"), *_crud("postingrule"),
            "close_fiscalperiod", "reopen_fiscalperiod", "reverse_journalentry",
        ],
    },
    {"name": "Treasurer", "permissions": [*READ]},
    {"name": "Auditor", "permissions": [*READ]},
]

ACTION_PERMISSIONS = {
    "journalentry": ["post_entry_journalentry", "reverse_journalentry"],
    "fiscalperiod": ["close_fiscalperiod", "reopen_fiscalperiod"],
    "account": ["trial_balance_account"],
}
