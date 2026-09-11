
import pkgutil
import importlib
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_farmacia_groups(sender, **kwargs):
    """Cria os perfis (Group templates) do módulo farmacia - mesmo
    mecanismo de saude/apps.py's create_saude_groups(), ver
    farmacia/profiles.py."""

    if kwargs.get("app_config").name != "farmacia":
        return

    from django_resaas.engine.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.engine.core.utils.group_creator import group_creator
    from farmacia.profiles import FARMACIA_PROFILES

    group_creator(FARMACIA_PROFILES)


class FarmaciaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'farmacia'

    def ready(self):
        from .signals import (
            create_and_grant_dashboard_permissions,
            grant_action_permissions_to_root,
        )
        post_migrate.connect(grant_action_permissions_to_root, sender=self)
        post_migrate.connect(create_and_grant_dashboard_permissions, sender=self)
        post_migrate.connect(create_farmacia_groups, sender=self)

        import farmacia.views

        for _, module_name, _ in pkgutil.iter_modules(farmacia.views.__path__):
            importlib.import_module(f"farmacia.views.{module_name}")

        # farmacia ouve 'saude.prescription.created' para alimentar a
        # fila automaticamente — nunca importa saude aqui, só reage
        # ao nome do evento (ver farmacia/listeners.py).
        from django_resaas.engine.core.events import EventDispatcher
        from farmacia.listeners import on_prescription_created

        EventDispatcher.register("saude.prescription.created", on_prescription_created)
