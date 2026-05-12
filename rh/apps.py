import pkgutil
import importlib
from django.apps import AppConfig
from django.db.models.signals import post_migrate


# ==========================================================
# CREATE GROUPS (POST MIGRATE)
# ==========================================================
def create_groups(sender, **kwargs):
    """
    Cria grupos automaticamente após migrate.

    🔥 FIX:
    - Só executa no app RH
    - Só executa quando EntityType já existe
    - Evita erro: entity_type_id NULL
    """

    # ------------------------------------------------------
    # 🔹 EXECUTA APENAS NO APP RH
    # ------------------------------------------------------
    if kwargs.get("app_config").name != "rh":
        return

    # ------------------------------------------------------
    # 🔹 GARANTE CONTEXTO
    # ------------------------------------------------------
    from django_resaas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    # ------------------------------------------------------
    # 🔹 IMPORT LOCAL (evita import cedo demais)
    # ------------------------------------------------------
    from django_resaas.core.utils.group_creator import group_creator

    # ------------------------------------------------------
    # 🔹 CRIAÇÃO DE GRUPOS
    # ------------------------------------------------------
    group_creator([
        # 🏢 Atendimento
        "Recepcionista",
        "Atendimento ao Cliente",
        "Call Center",

        # 💰 Financeiro
        "Administrador",
        "Gestor Financeiro",
        "Contabilista",
        "Tesoureiro",
        "Faturamento",
        "Auditor",

        # 🏥 Gestão
        "Diretor Geral",
        "Gestor de Unidade",
        "Supervisor",
        "Gestor de RH",

        # 🧹 Suporte
        "Segurança",
        "Limpeza",
        "Manutenção",
        "Motorista",
        "Auxiliar",

        # 💻 TI
        "Administrador de Sistema",
        "Técnico de TI",
        "Suporte Técnico",
        "DevOps",
        "Analista de Sistemas",
    ])


# ==========================================================
# APP CONFIG
# ==========================================================
class RhConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rh'

    def ready(self):
        """
        Inicialização do app RH.

        ✔ Liga signal post_migrate (forma correta)
        ✔ Carrega automaticamente as views
        """

        # --------------------------------------------------
        # 🔥 LIGAR SIGNAL (FORMA CORRETA)
        # --------------------------------------------------
        post_migrate.connect(create_groups, sender=self)

        # --------------------------------------------------
        # 🔹 AUTO LOAD VIEWS
        # --------------------------------------------------
        import rh.views

        for _, module_name, _ in pkgutil.iter_modules(rh.views.__path__):
            importlib.import_module(f"rh.views.{module_name}")