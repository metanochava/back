import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounting"

    def ready(self):
        from .signals import create_accounting_groups, grant_accounting_action_permissions

        post_migrate.connect(grant_accounting_action_permissions, sender=self)
        post_migrate.connect(create_accounting_groups, sender=self)

        import accounting.views

        for _, module_name, _ in pkgutil.iter_modules(accounting.views.__path__):
            importlib.import_module(f"accounting.views.{module_name}")

        from django_resaas.saas.core.events import EventDispatcher
        from accounting.listeners import on_event_with_amount, on_sale_cancelled
        from accounting.models import PostingRule

        for event, _label in PostingRule.EVENT_CHOICES:
            EventDispatcher.register(event, on_event_with_amount)
        EventDispatcher.register("sales.sale.cancelled", on_sale_cancelled)
