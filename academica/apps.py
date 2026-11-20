import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AcademicaConfig(AppConfig):
    """Education (kindergarten, school, university): academic structure,
    classes, students, guardians and enrolments. Identity in django_resaas
    Person, teachers in hr.Employee, fees through catalog / sales."""

    default_auto_field = "django.db.models.BigAutoField"
    # the former "ensino" app (2026-11-14, docs/progress/ensino-modular.md):
    # its tables keep the ensino_* names (Meta.db_table)
    name = "academica"
    verbose_name = "Academic"

    def ready(self):
        from .signals import create_academica_groups

        post_migrate.connect(create_academica_groups, sender=self)

        import academica.views

        for _, module_name, _ in pkgutil.iter_modules(academica.views.__path__):
            importlib.import_module(f"academica.views.{module_name}")
