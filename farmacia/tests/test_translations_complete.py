"""Same guard as saude/hr/notifications' test_translations_complete.py.
farmacia's frontend originally used Portuguese as the tdc() canonical
key throughout; all tdc() keys were rewritten to English. This guards
the backend side: sidebar.py's menu values and dashboard.py's widget/
filter labels reach tdc()/Translate.tdc() as lookup keys and must be
canonical English, translated into pt-pt/fr-fr/es-es (via farmacia's
own lang/<code>.py, or the shared saas core one)."""
import re

import pytest

from farmacia.sidebar import ALL as FARMACIA_SIDEBAR
from farmacia.dashboard import DASHBOARD as FARMACIA_DASHBOARD
from farmacia.lang import ptpt as farmacia_ptpt
from farmacia.lang import frfr as farmacia_frfr
from farmacia.lang import eses as farmacia_eses
from django_resaas.saas.lang import ptpt as saas_ptpt
from django_resaas.saas.lang import frfr as saas_frfr
from django_resaas.saas.lang import eses as saas_eses

pytestmark = pytest.mark.django_db

NON_ENGLISH_CHARS = re.compile(r"[àâãçéêíóôõúÀ-ÿ]")

PT = {**saas_ptpt.key_value, **farmacia_ptpt.key_value}
FR = {**saas_frfr.key_value, **farmacia_frfr.key_value}
ES = {**saas_eses.key_value, **farmacia_eses.key_value}


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


ALL_LABELS = sorted(set(
    list(_sidebar_menu_labels(FARMACIA_SIDEBAR))
    + list(_dashboard_text(FARMACIA_DASHBOARD))
))


@pytest.mark.parametrize("label", ALL_LABELS)
def test_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label), (
        f"farmacia label {label!r} looks non-English - "
        "canonical strings must originate in English (CLAUDE.md #82)"
    )


@pytest.mark.parametrize("label", ALL_LABELS)
def test_label_is_translated(label):
    for lang_name, lang in (("pt-pt", PT), ("fr-fr", FR), ("es-es", ES)):
        assert label in lang, f"{label!r} has no {lang_name} translation"
