"""Guards against the two real bugs found while creating hr's Portuguese/
French/Spanish translations (CLAUDE.md's LANGUAGE, INTERNATIONALIZATION
AND TRANSLATIONS section): canonical user-facing strings must originate
in English (sidebar.py's "menu" values and dashboard.py's widget
"label" values both reach tdc()/Translate.tdc() as lookup keys - both
had hardcoded Portuguese before this fix), and every such canonical
string must have a pt-pt/fr-fr/es-es translation (via hr's own
lang/<code>.py, or the shared saas core one)."""
import re

import pytest
from django.apps import apps

from hr.sidebar import ALL as HR_SIDEBAR
from hr.dashboard import DASHBOARD as HR_DASHBOARD
from hr.lang import ptpt as hr_ptpt
from hr.lang import frfr as hr_frfr
from hr.lang import eses as hr_eses
from django_resaas.saas.lang import ptpt as saas_ptpt
from django_resaas.saas.lang import frfr as saas_frfr
from django_resaas.saas.lang import eses as saas_eses

pytestmark = pytest.mark.django_db

# Accented characters that only appear in the pt/fr/es translations
# themselves, never in a canonical English key - the exact signal that
# caught "Colaboradores"/"Ausências pendentes"/"Organização"/etc. being
# used as canonical strings instead of their English source.
NON_ENGLISH_CHARS = re.compile(r"[àâãçéêíóôõúÀ-ÿ]")


def _sidebar_menu_labels(entries):
    for entry in entries:
        if "menu" in entry:
            yield entry["menu"]
        if "submenu" in entry:
            yield from _sidebar_menu_labels(entry["submenu"])


def _dashboard_labels(dashboard):
    yield dashboard["label"]
    for widget in dashboard["widgets"]:
        yield widget["label"]


PT = {**saas_ptpt.key_value, **hr_ptpt.key_value}
FR = {**saas_frfr.key_value, **hr_frfr.key_value}
ES = {**saas_eses.key_value, **hr_eses.key_value}


def _choice_labels():
    # Auto-discovered via Django's app registry, not a hand-maintained
    # list - a hand-maintained list is exactly what let
    # SalaryComponent.TYPE_CHOICES/CALCULATION_CHOICES slip through the
    # first translation pass (they're plain module-level tuples, not
    # models.TextChoices, so a `TextChoices` grep never found them).
    for Model in apps.get_app_config("hr").get_models():
        for field in Model._meta.get_fields():
            choices = getattr(field, "choices", None)
            if not choices:
                continue
            for _, label in choices:
                if isinstance(label, str):
                    yield label


@pytest.mark.parametrize("label", list(_sidebar_menu_labels(HR_SIDEBAR)))
def test_sidebar_menu_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label), (
        f"hr/sidebar.py menu label {label!r} looks non-English - "
        "canonical strings must originate in English (CLAUDE.md #82)"
    )


@pytest.mark.parametrize("label", list(_sidebar_menu_labels(HR_SIDEBAR)))
def test_sidebar_menu_label_is_translated(label):
    for lang_name, lang in (("pt-pt", PT), ("fr-fr", FR), ("es-es", ES)):
        assert label in lang, f"{label!r} has no {lang_name} translation"


@pytest.mark.parametrize("label", list(_dashboard_labels(HR_DASHBOARD)))
def test_dashboard_widget_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label), (
        f"hr/dashboard.py label {label!r} looks non-English - "
        "canonical strings must originate in English (CLAUDE.md #82)"
    )


@pytest.mark.parametrize("label", list(_dashboard_labels(HR_DASHBOARD)))
def test_dashboard_widget_label_is_translated(label):
    for lang_name, lang in (("pt-pt", PT), ("fr-fr", FR), ("es-es", ES)):
        assert label in lang, f"{label!r} has no {lang_name} translation"


@pytest.mark.parametrize("label", sorted(set(_choice_labels())))
def test_model_choice_label_is_canonical_english(label):
    assert not NON_ENGLISH_CHARS.search(label), (
        f"hr model choice label {label!r} looks non-English - "
        "canonical strings must originate in English (CLAUDE.md #82)"
    )


@pytest.mark.parametrize("label", sorted(set(_choice_labels())))
def test_model_choice_label_is_translated(label):
    for lang_name, lang in (("pt-pt", PT), ("fr-fr", FR), ("es-es", ES)):
        assert label in lang, f"{label!r} has no {lang_name} translation"
