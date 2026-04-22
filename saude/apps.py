import pkgutil
import importlib
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_saude_groups(sender, **kwargs):
    from django_resaas.core.utils.group_creator import group_creator

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


class SaudeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'saude'

    def ready(self):
        # ✅ CORRETO
        post_migrate.connect(create_saude_groups, sender=self)

        # 🔥 carregar views (ok)
        import saude.views
        for _, module_name, _ in pkgutil.iter_modules(saude.views.__path__):
            importlib.import_module(f"saude.views.{module_name}")