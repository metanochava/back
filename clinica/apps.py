
import pkgutil
import importlib
from django.apps import AppConfig

class ClinicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clinica'
    def ready(self):
        import clinica.views

        for _, module_name, _ in pkgutil.iter_modules(clinica.views.__path__):
            importlib.import_module(f"clinica.views.{module_name}")
