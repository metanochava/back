"""Sidebar menus, model names, choice labels and profile names of crm
are canonical English and translated into pt-pt/fr-fr/es-es."""
import re

import pytest
from django.apps import apps

from crm.profiles import CRM_PROFILES
from crm.sidebar import ALL as SIDEBAR

NON_ENGLISH_CHARS = re.compile(r"[àâãçéêíóôõúÀ-ÿ]")


def _merged(code):
    import importlib

    merged = {}
    for module in ("hr", "saude", "inventory", "sales", "purchases", "accounting", "django_resaas.saas", "crm"):
        try:
            merged.update(importlib.import_module(f"{module}.lang.{code}").key_value)
        except ModuleNotFoundError:
            pass
    return merged


LANGS = {"pt-pt": _merged("ptpt"), "fr-fr": _merged("frfr"), "es-es": _merged("eses")}


def _labels():
    for menu in SIDEBAR:
        yield menu["MENU"]
        for item in menu["SUBMENUS"]:
            yield item["menu"]
    for Model in apps.get_app_config("crm").get_models():
        yield Model._meta.verbose_name
        yield Model._meta.verbose_name_plural
        for field in Model._meta.get_fields():
            for _, label in getattr(field, "choices", None) or ():
                yield label
    for profile in CRM_PROFILES:
        yield profile["name"]


LABELS = sorted({str(label) for label in _labels()})


@pytest.mark.parametrize("label", LABELS)
def test_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label)


@pytest.mark.parametrize("label", LABELS)
def test_label_is_translated(label):
    for name, lang in LANGS.items():
        assert label in lang, f"{label!r} has no {name} translation"
