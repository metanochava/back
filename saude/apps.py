import pkgutil
import importlib
from django.apps import AppConfig
from django.db.models.signals import post_migrate


# ==========================================================
# CREATE SAUDE GROUPS
# ==========================================================
def create_saude_groups(sender, **kwargs):
    """
    Cria grupos do módulo Saúde após migrate.

    🔥 FIX:
    - Só executa no app correto
    - Só executa quando EntityType existe
    - Evita erro entity_type_id NULL
    """

    # ------------------------------------------------------
    # 🔹 EXECUTA APENAS NO APP SAUDE
    # ------------------------------------------------------
    if kwargs.get("app_config").name != "saude":
        return

    # ------------------------------------------------------
    # 🔹 GARANTE CONTEXTO
    # ------------------------------------------------------
    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    # ------------------------------------------------------
    # 🔹 IMPORT LOCAL
    # ------------------------------------------------------
    from django_resaas.saas.core.utils.group_creator import group_creator
    from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM

    # ------------------------------------------------------
    # 🔹 CRIAÇÃO DE GRUPOS (perfis em inglês - terminologia
    # ocupacional internacional; nomes antigos em português
    # renomeados no lugar, nunca duplicados - ver
    # saude/profiles.py's SAUDE_RENAME_FROM e group_creator()'s
    # rename_from)
    # ------------------------------------------------------
    group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)


# ==========================================================
# APP CONFIG
# ==========================================================
class SaudeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'saude'

    def ready(self):
        """
        Inicialização do app Saúde.

        ✔ liga signal corretamente
        ✔ evita execução prematura
        """

        from saude.signals.permissions import (
            create_and_grant_dashboard_permissions,
            grant_action_permissions_to_root,
        )

        # 🔹 Dashboards - cria as permissões e concede ao Root. Ligado
        # ANTES de create_saude_groups: os perfis (saude/profiles.py)
        # recebem permissões de dashboard, que têm de existir já no
        # primeiro migrate (post_migrate corre os receivers pela ordem
        # em que foram ligados).
        post_migrate.connect(create_and_grant_dashboard_permissions, sender=self)

        # 🔥 SIGNAL CORRETO
        post_migrate.connect(create_saude_groups, sender=self)

        # 🔹 Fase 1 (Patient longitudinal): concede a permissão de
        # search_candidates ao Root - mesmo padrão de farmacia/signals.py
        post_migrate.connect(grant_action_permissions_to_root, sender=self)

        # 🔹 AUTO LOAD VIEWS
        import saude.views

        for _, module_name, _ in pkgutil.iter_modules(saude.views.__path__):
            importlib.import_module(f"saude.views.{module_name}")

        import saude.signals
        import saude.signals.receitamedica  # noqa: F401 — regista o @receiver (saude/signals/ não tem __init__.py que o importe)