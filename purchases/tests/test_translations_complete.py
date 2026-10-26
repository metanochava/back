"""Same guard as sales/inventory: sidebar menus and every model choice label
of purchases are canonical English and translated into pt-pt
(purchases' own lang/<code>.py or the shared django_resaas one)."""
import re

import pytest
from django.apps import apps

from django_resaas.saas.lang import ptpt as saas_ptpt
from purchases.lang import ptpt
from purchases.profiles import PURCHASES_PROFILES
from purchases.sidebar import ALL as SIDEBAR
from sales.lang import ptpt as sales_ptpt
from inventory.lang import ptpt as inv_ptpt
from saude.lang import ptpt as saude_ptpt
from hr.lang import ptpt as hr_ptpt

NON_ENGLISH_CHARS = re.compile(r"[àâãçéêíóôõúÀ-ÿ]")

PT = {**hr_ptpt.key_value, **saude_ptpt.key_value, **inv_ptpt.key_value, **sales_ptpt.key_value, **saas_ptpt.key_value, **ptpt.key_value}


def _labels():
    for menu in SIDEBAR:
        yield menu["MENU"]
        for item in menu["SUBMENUS"]:
            yield item["menu"]
    for Model in apps.get_app_config("purchases").get_models():
        yield Model._meta.verbose_name
        yield Model._meta.verbose_name_plural
        for field in Model._meta.get_fields():
            for _, label in getattr(field, "choices", None) or ():
                yield label
    for profile in PURCHASES_PROFILES:
        yield profile["name"]


LABELS = sorted({str(label) for label in _labels()})


@pytest.mark.parametrize("label", LABELS)
def test_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label)


@pytest.mark.parametrize("label", LABELS)
def test_label_is_translated(label):
    for name, lang in (("pt-pt", PT),):
        assert label in lang, f"{label!r} has no {name} translation"
