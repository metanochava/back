import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class EnsinoConfig(AppConfig):
    """Education (kindergarten, school, university): academic structure,
    classes, students, guardians and enrolments. Identity in django_resaas
    Person, teachers in hr.Employee, fees through catalog / sales."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ensino"
    verbose_name = "Education"

    def ready(self):
        from .signals import create_ensino_groups

        post_migrate.connect(create_ensino_groups, sender=self)

        import ensino.views

        for _, module_name, _ in pkgutil.iter_modules(ensino.views.__path__):
            importlib.import_module(f"ensino.views.{module_name}")
