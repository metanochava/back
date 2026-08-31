import pkgutil
import importlib

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sales'

    def ready(self):
        from .signals import create_sales_dashboard_permissions
        post_migrate.connect(create_sales_dashboard_permissions, sender=self)

        import sales.views

        for _, module_name, _ in pkgutil.iter_modules(sales.views.__path__):
            importlib.import_module(f"sales.views.{module_name}")
