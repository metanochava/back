import pkgutil
import importlib
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_groups(sender, **kwargs):
    from django_resaas.core.utils.group_creator import group_creator

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


class RhConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rh'

    def ready(self):
        # 🔥 ligar signal (CORRETO)
        post_migrate.connect(create_groups, sender=self)

        # 🔥 carregar views (ok manter)
        import rh.views
        for _, module_name, _ in pkgutil.iter_modules(rh.views.__path__):
            importlib.import_module(f"rh.views.{module_name}")