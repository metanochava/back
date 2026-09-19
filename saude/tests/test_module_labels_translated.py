"""Standing rule (CLAUDE.md section 84): every user-facing label of the saude
module exists in pt-pt, es-es and fr-fr - model/field labels (what the
schema hands the frontend, which translates them with tdc()), choice labels,
sidebar menus, @resaas_action labels/tooltips, and every tdc('...') literal in
the saude frontend pages. test_translations_complete.py covers choices /
sidebar / dashboard; this adds the field and action labels and the frontend
literals so a new untranslated string fails a test instead of shipping."""
import ast
import glob
import inspect
import importlib
import pkgutil
import re
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase

from django_resaas.saas.core.base.views import BaseAPIView


def _load(path):
    source = Path(path).read_text()
    return ast.literal_eval(source[source.index("{"):source.rindex("}") + 1]) if "{" in source else {}


def _dictionaries():
    result = {}
    for code in ("ptpt", "eses", "frfr"):
        merged = {}
        for path in glob.glob(f"/var/www/dev/venv/lib/python3.10/site-packages/django_resaas/*/lang/{code}.py"):
            merged.update(_load(path))
        for path in glob.glob(f"/var/www/dev/back/*/lang/{code}.py"):
            merged.update(_load(path))
        result[code] = merged
    return result


DICTIONARIES = _dictionaries()


def _untranslated(text):
    return [code for code, words in DICTIONARIES.items() if text not in words]


class SaudeLabelsAreTranslated(SimpleTestCase):

    def test_every_saude_model_and_field_label_is_translated(self):
        missing = {}
        for model in apps.get_app_config("saude").get_models():
            labels = {
                str(model._meta.verbose_name).title(): f"{model.__name__}.verbose_name",
                str(model._meta.verbose_name_plural).title(): f"{model.__name__}.verbose_name_plural",
            }
            for field in model._meta.get_fields():
                if getattr(field, "concrete", False) or getattr(field, "many_to_many", False):
                    if getattr(field, "verbose_name", None):
                        labels[str(field.verbose_name).title()] = f"{model.__name__}.{field.name}"
                    for choice in getattr(field, "choices", None) or []:
                        labels[str(choice[1])] = f"{model.__name__}.{field.name} choice"
            for text, where in labels.items():
                if _untranslated(text):
                    missing[text] = where

        self.assertEqual(missing, {}, "Untranslated saude labels (add them to saude/lang/*.py)")

    def test_person_contact_document_and_address_labels_are_translated(self):
        missing = {}
        for label, names in (("django_resaas", {"Person", "PersonContact", "Document", "DocumentType", "Address"}),):
            for model in apps.get_app_config(label).get_models():
                if model.__name__ not in names:
                    continue
                texts = {str(model._meta.verbose_name).title(), str(model._meta.verbose_name_plural).title()}
                for field in model._meta.get_fields():
                    if getattr(field, "concrete", False) and getattr(field, "verbose_name", None):
                        texts.add(str(field.verbose_name).title())
                        texts.update(str(choice[1]) for choice in getattr(field, "choices", None) or [])
                missing.update({text: model.__name__ for text in texts if _untranslated(text)})

        self.assertEqual(missing, {})

    def test_every_saude_action_label_and_tooltip_is_translated(self):
        import saude.views as saude_views
        import django_resaas.saas.data.person.views.person as person_views

        modules = [importlib.import_module(f"saude.views.{m.name}") for m in pkgutil.iter_modules(saude_views.__path__)]
        modules.append(person_views)

        missing = {}
        for module in modules:
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if not issubclass(cls, BaseAPIView) or cls.__module__ != module.__name__:
                    continue
                for attr in dir(cls):
                    meta = getattr(getattr(cls, attr, None), "_resaas_action", None)
                    for key in ("label", "tooltip"):
                        text = (meta or {}).get(key)
                        if text and _untranslated(text):
                            missing[text] = f"{cls.__name__}.{attr}"

        self.assertEqual(missing, {})

    def test_every_tdc_literal_in_the_saude_frontend_pages_is_translated(self):
        pages = Path("/var/www/dev/front/src/pages/saude")
        if not pages.exists():
            self.skipTest("frontend repo not next to the backend")

        pattern = re.compile(r"""tdc\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""")
        missing = {}
        for path in list(pages.rglob("*.vue")) + list(pages.rglob("*.js")):
            for match in pattern.finditer(path.read_text()):
                text = (match.group(1) or match.group(2) or "").replace("\\'", "'")
                if text.strip() and _untranslated(text):
                    missing[text] = str(path.relative_to(pages))

        self.assertEqual(missing, {}, "Untranslated tdc() strings in the saude frontend")

    def test_every_group_name_defined_by_the_modules_is_translated(self):
        """Group names are data but the frontend shows them everywhere
        (selectors, modals, tables) through tdc() - each name a module
        seeds must exist in the dictionaries."""
        from saude.profiles import SAUDE_PROFILES
        from farmacia.profiles import FARMACIA_PROFILES
        from inventory.profiles import INVENTORY_PROFILES
        from sales.profiles import SALES_PROFILES
        from django_resaas.hr.profiles import HR_PROFILES
        from django_resaas.saas.profiles import CORE_PROFILES

        names = {"Root", "Admin", "Guest"}
        for profiles in (CORE_PROFILES, SAUDE_PROFILES, FARMACIA_PROFILES, INVENTORY_PROFILES, SALES_PROFILES, HR_PROFILES):
            names.update(profile["name"] for profile in profiles)

        missing = sorted(name for name in names if _untranslated(name))

        self.assertEqual(missing, [], "Untranslated group names (add them to the module's lang/*.py)")

