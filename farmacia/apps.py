
import pkgutil
import importlib
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FarmaciaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'farmacia'

    def ready(self):
        from .signals import grant_action_permissions_to_root
        post_migrate.connect(grant_action_permissions_to_root, sender=self)

        import farmacia.views

        for _, module_name, _ in pkgutil.iter_modules(farmacia.views.__path__):
            importlib.import_module(f"farmacia.views.{module_name}")

        # farmacia ouve 'saude.prescription.created' para alimentar a
        # fila automaticamente — nunca importa saude aqui, só reage
        # ao nome do evento (ver farmacia/listeners.py).
        from django_resaas.engine.core.events import EventDispatcher
        from farmacia.listeners import on_prescription_created

        EventDispatcher.register("saude.prescription.created", on_prescription_created)
