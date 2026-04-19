
import pkgutil
import importlib
from django.apps import AppConfig

class SaudeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'saude'
    def ready(self):
        import saude.views

        for _, module_name, _ in pkgutil.iter_modules(saude.views.__path__):
            importlib.import_module(f"saude.views.{module_name}")
