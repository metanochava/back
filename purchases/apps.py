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

        # approval of an order can be driven by a workflow (optional module)
        from django.apps import apps

        if apps.is_installed("workflow"):
            from purchases import services
            from workflow.registry import register_action

            register_action(
                "purchases.approve_order",
                label="Approve the purchase order",
                model="purchases.PurchaseOrder",
                on_approved=lambda order, user: services.approve_order(order=order, user=user),
                on_rejected=lambda order, user: services.return_to_draft(order=order, user=user),
            )
