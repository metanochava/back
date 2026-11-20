import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class HospitalityConfig(AppConfig):
    """Bars and restaurants: tables, their QR codes and what customers ask
    from them. Uses sales (the tables' open tabs) and catalog (the menu)
    through their public services."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hospitality"

    def ready(self):
        from .signals import create_hospitality_groups, grant_hospitality_action_permissions

        # the action permissions first, so the profiles find them
        post_migrate.connect(grant_hospitality_action_permissions, sender=self)
        post_migrate.connect(create_hospitality_groups, sender=self)

        # an item ordered on a tab reaches the station that prepares it
        from django_resaas.saas.core.events import EventDispatcher
        from hospitality.services import on_tab_ordered

        EventDispatcher.register("sales.tab.ordered", on_tab_ordered, propagate=True)

        import hospitality.views

        for _, module_name, _ in pkgutil.iter_modules(hospitality.views.__path__):
            importlib.import_module(f"hospitality.views.{module_name}")
