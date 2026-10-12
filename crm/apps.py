import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"

    def ready(self):
        from .signals import create_crm_groups, grant_crm_action_permissions

        post_migrate.connect(grant_crm_action_permissions, sender=self)
        post_migrate.connect(create_crm_groups, sender=self)

        import crm.views

        for _, module_name, _ in pkgutil.iter_modules(crm.views.__path__):
            importlib.import_module(f"crm.views.{module_name}")
