ALL = [{
    'MENU': "Accounting",
    'ICON': "account_balance",

    'SUBMENUS': [
        {"icon": "menu_book", "menu": "Journal entries", "role": "list_journalentry", "route": "list_journalentry"},
        {"icon": "balance", "menu": "Trial balance", "role": "trial_balance_account", "route": "view_trial_balance"},
        {"icon": "account_tree", "menu": "Chart of accounts", "role": "list_account", "route": "list_account"},
        {"icon": "book", "menu": "Journals", "role": "list_journal", "route": "list_journal"},
        {"icon": "event", "menu": "Fiscal periods", "role": "list_fiscalperiod", "route": "list_fiscalperiod"},
        {"icon": "rule", "menu": "Posting rules", "role": "list_postingrule", "route": "list_postingrule"},
    ],
}]
