import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class WorkflowConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workflow"

    def ready(self):
        from .signals import create_workflow_groups, grant_workflow_action_permissions

        post_migrate.connect(grant_workflow_action_permissions, sender=self)
        post_migrate.connect(create_workflow_groups, sender=self)

        import workflow.views

        for _, module_name, _ in pkgutil.iter_modules(workflow.views.__path__):
            importlib.import_module(f"workflow.views.{module_name}")

        # definitions with start_event start by themselves (workflow.services.on_event)
        from django_resaas.saas.core.events import EventDispatcher
        from workflow.services import on_event

        EventDispatcher.register("*", on_event)
