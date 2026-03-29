
import pkgutil
import importlib
from django.apps import AppConfig

class RhConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rh'
    def ready(self):
        import rh.views

        for _, module_name, _ in pkgutil.iter_modules(rh.views.__path__):
            importlib.import_module(f"rh.views.{module_name}")
