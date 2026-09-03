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
    from django_resaas.engine.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    # ------------------------------------------------------
    # 🔹 IMPORT LOCAL
    # ------------------------------------------------------
    from django_resaas.engine.core.utils.group_creator import group_creator

    # ------------------------------------------------------
    # 🔹 CRIAÇÃO DE GRUPOS
    # ------------------------------------------------------
    group_creator([
        # 👨‍⚕️ Clínica
        "Médico Geral",
        "Médico Especialista",
        "Cirurgião",
        "Enfermeiro",
        "Enfermeiro Chefe",
        "Parteira",
        "Fisioterapeuta",
        "Psicólogo",
        "Nutricionista",
        "Farmacêutico",
        "Técnico de Farmácia",

        # 🧪 Exames
        "Técnico de Laboratório",
        "Técnico de Radiologia",
        "Técnico de Imagiologia",
        "Técnico de Ecografia",
        "Técnico de Tomografia",
        "Técnico de Ressonância",
        "Analista Clínico",

        # 🏢 Atendimento
        "Secretária Clínica",
        "Gestor de Pacientes",
        "Triagem",

        # 💰 Financeiro
        "Administrador",
        "Gestor Financeiro",
        "Contabilista",
        "Tesoureiro",
        "Faturamento",
        "Auditor",

        # 🏥 Gestão
        "Diretor Clínico",
        "Coordenador Médico",
    ])


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

        # 🔥 SIGNAL CORRETO
        post_migrate.connect(create_saude_groups, sender=self)

        # 🔹 AUTO LOAD VIEWS
        import saude.views

        for _, module_name, _ in pkgutil.iter_modules(saude.views.__path__):
            importlib.import_module(f"saude.views.{module_name}")

        import saude.signals