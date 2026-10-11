"""Profiles (Group templates) of the purchases module - same mechanism as
sales/profiles.py and inventory/profiles.py (group_creator()).

The generic finance profiles (Finance Manager, Accountant, Auditor) and the
warehouse ones (Warehouse Manager, Receiving Clerk) are the SAME names the
other modules use: a profile is not duplicated per module, the active
modules and the granted permissions decide what it sees.
"""

ORDER_READ = ["view_purchaseorder", "list_purchaseorder", "view_purchaseorderline", "list_purchaseorderline"]
RECEIPT_READ = ["view_goodsreceipt", "list_goodsreceipt", "view_goodsreceiptline", "list_goodsreceiptline"]
SUPPLIER_READ = ["view_supplier", "list_supplier"]

PURCHASES_PROFILES = [
    {
        "name": "Purchasing Manager",
        "permissions": [
            *SUPPLIER_READ, "add_supplier", "change_supplier", "delete_supplier",
            *ORDER_READ, "add_purchaseorder", "change_purchaseorder", "delete_purchaseorder",
            "add_purchaseorderline", "change_purchaseorderline", "delete_purchaseorderline",
            "submit_purchaseorder", "return_to_draft_purchaseorder", "approve_purchaseorder",
            "cancel_purchaseorder", "receive_purchaseorder",
            *RECEIPT_READ,
        ],
    },
    {
        "name": "Buyer",
        "permissions": [
            *SUPPLIER_READ, "add_supplier", "change_supplier",
            *ORDER_READ, "add_purchaseorder", "change_purchaseorder", "delete_purchaseorder",
            "add_purchaseorderline", "change_purchaseorderline", "delete_purchaseorderline",
            "submit_purchaseorder",
            *RECEIPT_READ,
        ],
    },
    {
        "name": "Warehouse Manager",
        "permissions": [*SUPPLIER_READ, *ORDER_READ, "receive_purchaseorder", *RECEIPT_READ],
    },
    {
        "name": "Receiving Clerk",
        "permissions": [*ORDER_READ, "receive_purchaseorder", *RECEIPT_READ],
    },
    {"name": "Finance Manager", "permissions": [*SUPPLIER_READ, *ORDER_READ, "approve_purchaseorder", *RECEIPT_READ]},
    {"name": "Accountant", "permissions": [*SUPPLIER_READ, *ORDER_READ, *RECEIPT_READ]},
    {"name": "Auditor", "permissions": [*SUPPLIER_READ, *ORDER_READ, *RECEIPT_READ]},
]

ACTION_PERMISSIONS = [
    "submit_purchaseorder",
    "return_to_draft_purchaseorder",
    "approve_purchaseorder",
    "cancel_purchaseorder",
    "receive_purchaseorder",
]
