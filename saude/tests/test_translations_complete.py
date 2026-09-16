"""Same guard as hr/notifications' test_translations_complete.py.
saude's frontend (/var/www/dev/front/src/pages/saude) originally used
Portuguese as the tdc() canonical key throughout - the opposite of
CLAUDE.md's "English is the canonical source language" rule. All tdc()
keys were rewritten to English; this test guards the backend side of
that fix: sidebar.py's menu values, dashboard.py's widget/filter
labels and tooltips, and every model field's `choices=` display labels
(auto-discovered via Django's app registry, not a hand-maintained list
- a hand-maintained list is exactly what let saude/farmacia/inventory/
sales' named CHOICES constants like FilaFarmacia.ESTADO_CHOICES or
HorarioMedico.DIA_SEMANA_CHOICES slip through the first pass, since
`choices=SOME_CONSTANT` doesn't match a naive `choices=\\[` grep) - all
reach tdc()/Translate.tdc() as lookup keys and must be canonical
English, translated into pt-pt/fr-fr/es-es (via saude's own
lang/<code>.py, or the shared saas core one)."""
import re

import pytest
from django.apps import apps

from saude.sidebar import ALL as SAUDE_SIDEBAR
from saude.dashboard import DASHBOARD as SAUDE_DASHBOARD
from saude.lang import ptpt as saude_ptpt
from saude.lang import frfr as saude_frfr
from saude.lang import eses as saude_eses
from django_resaas.saas.lang import ptpt as saas_ptpt
from django_resaas.saas.lang import frfr as saas_frfr
from django_resaas.saas.lang import eses as saas_eses

pytestmark = pytest.mark.django_db

NON_ENGLISH_CHARS = re.compile(r"[àâãçéêíóôõúÀ-ÿ]")

PT = {**saas_ptpt.key_value, **saude_ptpt.key_value}
FR = {**saas_frfr.key_value, **saude_frfr.key_value}
ES = {**saas_eses.key_value, **saude_eses.key_value}


def _sidebar_menu_labels(entries):
    for entry in entries:
        if "menu" in entry:
            yield entry["menu"]
        if "submenu" in entry:
            yield from _sidebar_menu_labels(entry["submenu"])


def _dashboard_text(node):
    if isinstance(node, dict):
        for key in ("label", "tooltip"):
            if key in node and isinstance(node[key], str):
                yield node[key]
        for value in node.values():
            yield from _dashboard_text(value)
    elif isinstance(node, list):
        for item in node:
            yield from _dashboard_text(item)


def _choice_labels():
    for Model in apps.get_app_config("saude").get_models():
        for field in Model._meta.get_fields():
            choices = getattr(field, "choices", None)
            if not choices:
                continue
            for _, label in choices:
                if isinstance(label, str):
                    yield label


ALL_LABELS = sorted(set(
    list(_sidebar_menu_labels(SAUDE_SIDEBAR))
    + list(_dashboard_text(SAUDE_DASHBOARD))
    + list(_choice_labels())
))


@pytest.mark.parametrize("label", ALL_LABELS)
def test_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label), (
        f"saude label {label!r} looks non-English - "
        "canonical strings must originate in English (CLAUDE.md #82)"
    )


@pytest.mark.parametrize("label", ALL_LABELS)
def test_label_is_translated(label):
    for lang_name, lang in (("pt-pt", PT), ("fr-fr", FR), ("es-es", ES)):
        assert label in lang, f"{label!r} has no {lang_name} translation"
