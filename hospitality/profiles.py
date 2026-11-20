"""Profiles (Group templates) of the hospitality module (group_creator()).

Waiter is new: serves the tables - opens their tabs and orders on them at the
point of sale (sales' checkout_sale), handles what customers ask. The other
names are the ones the modules share (Cashier, Admin): a profile is not
duplicated per module."""

_CRUD = lambda model: [f"{a}_{model}" for a in ("view", "list", "add", "change", "delete")]  # noqa: E731

READ = ["view_diningarea", "list_diningarea", "view_diningtable", "list_diningtable"]
SERVE = [*READ, "board_diningtable", "start_tab_diningtable", "view_tablerequest", "list_tablerequest",
         "handle_tablerequest", "view_tableorder", "list_tableorder", "accept_tableorder", "reject_tableorder",
         "kitchen_prepticket", "advance_prepticket"]
# a cook / a bartender: their station's screen
PREPARE = ["view_prepstation", "list_prepstation", "view_prepticket", "list_prepticket", "kitchen_prepticket",
           "advance_prepticket"]
MANAGE = [*_CRUD("diningarea"), *_CRUD("diningtable"), *_CRUD("prepstation"), "rotate_qr_diningtable",
          "qr_cards_diningtable", "pdf_diningtable", "pdf_list_diningtable", "view_prepticket", "list_prepticket"]

# what serving at the point of sale needs from sales and catalog
POINT_OF_SALE = ["checkout_sale", "list_customer", "list_product", "list_productcategory"]

ACTION_PERMISSIONS = {
    "diningtable": ["board_diningtable", "start_tab_diningtable", "rotate_qr_diningtable", "qr_cards_diningtable"],
    "tablerequest": ["handle_tablerequest"],
    "tableorder": ["accept_tableorder", "reject_tableorder"],
    "prepticket": ["kitchen_prepticket", "advance_prepticket"],
}

HOSPITALITY_PROFILES = [
    {
        "name": "Waiter",
        # the point of sale: order on the tables' tabs (sales) and see the menu
        "permissions": [*SERVE, *POINT_OF_SALE],
    },
    {"name": "Cashier", "permissions": SERVE},
    {"name": "Cook", "permissions": PREPARE},
    {"name": "Bartender", "permissions": [*PREPARE, *SERVE, *POINT_OF_SALE]},
    {"name": "Hospitality Manager", "permissions": sorted(set(SERVE + MANAGE + POINT_OF_SALE))},
    {"name": "Admin", "permissions": sorted(set(SERVE + MANAGE))},
]
