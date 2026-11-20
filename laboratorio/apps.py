import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class LaboratorioConfig(AppConfig):
    """Rooms and laboratories (ReSaaS Ensino, docs/progress/ensino-modular.md):
    workstations, equipment, networks, environments, practical sessions with
    seats and exercises, and authorised, audited remote access. Uses academica
    (classes, enrolments), pedagogica (assignments) and hr (teachers); the
    Lab Manager only through integrations/labmanager.py."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "laboratorio"
    verbose_name = "Laboratories"

    def ready(self):
        from .signals import create_laboratorio_groups, grant_laboratorio_action_permissions

        post_migrate.connect(grant_laboratorio_action_permissions, sender=self)
        post_migrate.connect(create_laboratorio_groups, sender=self)

        import laboratorio.views

        for _, module_name, _ in pkgutil.iter_modules(laboratorio.views.__path__):
            importlib.import_module(f"laboratorio.views.{module_name}")
