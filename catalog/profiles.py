"""Profiles (Group templates) of the catalog module - the same group_creator()
mechanism as the other modules. "Catalog Manager" keeps the catalogue; the
Entity's "Admin" can too. Other modules' profiles keep naming the catalog
permissions they need (codenames: view_product, list_product, ...)."""

_CRUD = lambda model: [f"{a}_{model}" for a in ("view", "list", "add", "change", "delete")]  # noqa: E731

CATALOG_PERMISSIONS = [
    *_CRUD("product"), *_CRUD("productcategory"), *_CRUD("productmedia"),
    *_CRUD("pricelist"), *_CRUD("pricelistitem"), "price_product",
]

CATALOG_PROFILES = [
    {"name": "Catalog Manager", "permissions": CATALOG_PERMISSIONS},
    {"name": "Admin", "permissions": CATALOG_PERMISSIONS},
]
