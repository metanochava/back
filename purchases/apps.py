import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class PurchasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "purchases"

    def ready(self):
        from .signals import create_purchases_groups, grant_purchases_action_permissions

        # the action permissions first, so the profiles find them
        post_migrate.connect(grant_purchases_action_permissions, sender=self)
        post_migrate.connect(create_purchases_groups, sender=self)

        import purchases.views

        for _, module_name, _ in pkgutil.iter_modules(purchases.views.__path__):
            importlib.import_module(f"purchases.views.{module_name}")
