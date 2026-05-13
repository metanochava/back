
import pkgutil
import importlib
from django.apps import AppConfig

class HrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hr'
    def ready(self):
        import hr.views

        for _, module_name, _ in pkgutil.iter_modules(hr.views.__path__):
            importlib.import_module(f"hr.views.{module_name}")
