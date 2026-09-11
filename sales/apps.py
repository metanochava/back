import pkgutil
import importlib

from django.apps import AppConfig
from django.db.models.signals import post_migrate


# ==========================================================
# CREATE SALES GROUPS
# ==========================================================
def create_sales_groups(sender, **kwargs):
    """
    Cria os perfis (Group templates) do módulo Sales após migrate.

    Antes disto chamava group_creator() com a lista CLÍNICA da saúde,
    copiada por engano (comentários diziam literalmente "CREATE SAUDE
    GROUPS" dentro do app sales) - substituído por perfis reais de
    vendas, ver sales/profiles.py.
    """

    # ------------------------------------------------------
    # 🔹 EXECUTA APENAS NO APP SALES
    # ------------------------------------------------------
    if kwargs.get("app_config").name != "sales":
        return

    # ------------------------------------------------------
    # 🔹 GARANTE CONTEXTO
    # ------------------------------------------------------
    from django_resaas.engine.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    # ------------------------------------------------------
    # 🔹 IMPORT LOCAL
    # ------------------------------------------------------
    from django_resaas.engine.core.utils.group_creator import group_creator
    from sales.profiles import SALES_PROFILES

    # ------------------------------------------------------
    # 🔹 CRIAÇÃO DE GRUPOS
    # ------------------------------------------------------
    group_creator(SALES_PROFILES)



class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sales'

    def ready(self):

        # 🔥 SIGNAL CORRETO
        post_migrate.connect(create_sales_groups, sender=self)
        
        from .signals import create_sales_dashboard_permissions
        post_migrate.connect(create_sales_dashboard_permissions, sender=self)

        import sales.views

        for _, module_name, _ in pkgutil.iter_modules(sales.views.__path__):
            importlib.import_module(f"sales.views.{module_name}")
