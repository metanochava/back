"""The catalog's menu and its models' choices are canonical English with a
pt-pt translation (catalog/lang, inventory/lang where the catalogue's keys
were written, or the shared core) - same guard as the other modules."""
from django.apps import apps

from catalog.lang import ptpt as catalog_ptpt
from catalog.sidebar import ALL as CATALOG_SIDEBAR
from django_resaas.saas.lang import ptpt as saas_ptpt
from inventory.lang import ptpt as inventory_ptpt

PT = {**saas_ptpt.key_value, **inventory_ptpt.key_value, **catalog_ptpt.key_value}


def test_menu_is_translated():
    labels = [menu["MENU"] for menu in CATALOG_SIDEBAR]
    labels += [sub["menu"] for menu in CATALOG_SIDEBAR for sub in menu["SUBMENUS"]]
    assert [label for label in labels if label not in PT] == []


def test_choices_are_translated():
    missing = []
    for model in apps.get_app_config("catalog").get_models():
        for field in model._meta.fields:
            for _, label in (field.choices or []):
                if str(label) not in PT:
                    missing.append(f"{model.__name__}.{field.name}: {label}")
    assert missing == []
