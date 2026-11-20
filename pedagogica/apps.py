import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class PedagogicaConfig(AppConfig):
    """Teaching and learning (ReSaaS Ensino, docs/progress/ensino-modular.md):
    lesson plans, the digital board, materials, assignments and submissions,
    the pedagogical calendar, progress notes and class messages. Uses
    academica (classes, subjects, enrolments, grades) through its models and
    public services; academica never imports pedagogica."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "pedagogica"
    verbose_name = "Pedagogy"

    def ready(self):
        from .signals import create_pedagogica_groups, grant_pedagogica_action_permissions

        post_migrate.connect(grant_pedagogica_action_permissions, sender=self)
        post_migrate.connect(create_pedagogica_groups, sender=self)

        import pedagogica.views

        for _, module_name, _ in pkgutil.iter_modules(pedagogica.views.__path__):
            importlib.import_module(f"pedagogica.views.{module_name}")
