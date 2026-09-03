import pkgutil
import importlib

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        """
        Auto-carrega todas as views do módulo para que o decorator
        @registerView corra e popule VIEW_REGISTRY (consumido por
        django_resaas.engine.core.utils.autoload_urls.build_saas_urls()).
        """

        from .signals import create_inventory_dashboard_permissions
        post_migrate.connect(create_inventory_dashboard_permissions, sender=self)

        import inventory.views

        for _, module_name, _ in pkgutil.iter_modules(inventory.views.__path__):
            importlib.import_module(f"inventory.views.{module_name}")
