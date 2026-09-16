"""Same guard as saude/hr/notifications/farmacia/inventory's
test_translations_complete.py. sales' frontend
(/var/www/dev/front/src/pages/vendas) originally used Portuguese as the
tdc() canonical key throughout; all tdc() keys were rewritten to
English. This guards the backend side: sidebar.py's menu values and
dashboard.py's widget/filter labels reach tdc()/Translate.tdc() as
lookup keys and must be canonical English, translated into
pt-pt/fr-fr/es-es (via sales' own lang/<code>.py, or the shared saas
core one). Also covers every model field's `choices=` display labels,
auto-discovered via Django's app registry rather than a
hand-maintained list - a hand-maintained list is exactly what let
Sale.ESTADO_CHOICES/Payment.FORMA_CHOICES/Customer.TYPE_CHOICES/
CustomerContact.ROLE_CHOICES slip through the first translation pass,
since `choices=SOME_CONSTANT` doesn't match a naive `choices=\\[`
grep."""
import re

import pytest
from django.apps import apps

from sales.sidebar import ALL as SALES_SIDEBAR
from sales.dashboard import DASHBOARD as SALES_DASHBOARD
from sales.lang import ptpt as sales_ptpt
from sales.lang import frfr as sales_frfr
from sales.lang import eses as sales_eses
from django_resaas.saas.lang import ptpt as saas_ptpt
from django_resaas.saas.lang import frfr as saas_frfr
from django_resaas.saas.lang import eses as saas_eses

pytestmark = pytest.mark.django_db

NON_ENGLISH_CHARS = re.compile(r"[àâãçéêíóôõúÀ-ÿ]")

PT = {**saas_ptpt.key_value, **sales_ptpt.key_value}
FR = {**saas_frfr.key_value, **sales_frfr.key_value}
ES = {**saas_eses.key_value, **sales_eses.key_value}


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
    for Model in apps.get_app_config("sales").get_models():
        for field in Model._meta.get_fields():
            choices = getattr(field, "choices", None)
            if not choices:
                continue
            for _, label in choices:
                if isinstance(label, str):
                    yield label


ALL_LABELS = sorted(set(
    list(_sidebar_menu_labels(SALES_SIDEBAR))
    + list(_dashboard_text(SALES_DASHBOARD))
    + list(_choice_labels())
))


@pytest.mark.parametrize("label", ALL_LABELS)
def test_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label), (
        f"sales label {label!r} looks non-English - "
        "canonical strings must originate in English (CLAUDE.md #82)"
    )


@pytest.mark.parametrize("label", ALL_LABELS)
def test_label_is_translated(label):
    for lang_name, lang in (("pt-pt", PT), ("fr-fr", FR), ("es-es", ES)):
        assert label in lang, f"{label!r} has no {lang_name} translation"
