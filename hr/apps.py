import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


# the module's own non-CRUD permissions (dashboards) - created by the
# framework's public helper, ensure_module_permissions (they used to be
# hardcoded in django_resaas's core)
HR_MODULE_PERMISSIONS = [
        {
            "codename": "view_hr_dashboard",
            "name": "Can view HR dashboard",
        },
        {
            "codename": "view_dashboard_hr_organizacao",
            "name": "Can view Organização dashboard",
        },
        {
            "codename": "view_dashboard_hr_tempo_presenca",
            "name": "Can view Tempo & Presença dashboard",
        },
        {
            "codename": "view_dashboard_hr_salario_folha",
            "name": "Can view Salário & Folha de Pagamento dashboard",
        },
        {
            "codename": "view_dashboard_hr_ausencias",
            "name": "Can view Ausências dashboard",
        },
        {
            "codename": "view_dashboard_hr_recrutamento",
            "name": "Can view Recrutamento dashboard",
        },
        {
            "codename": "view_dashboard_hr_onboarding",
            "name": "Can view Onboarding dashboard",
        },
        {
            "codename": "view_dashboard_hr_desempenho",
            "name": "Can view Desempenho dashboard",
        },
        {
            "codename": "view_dashboard_hr_formacao",
            "name": "Can view Formação dashboard",
        },
        {
            "codename": "view_dashboard_hr_ciclo_vida",
            "name": "Can view Ciclo de Vida do Colaborador dashboard",
        },
]


def create_hr_module_permissions(sender, **kwargs):
    if kwargs.get("app_config").label != "hr":
        return

    from django_resaas.saas.core.signals.permissions import ensure_module_permissions

    ensure_module_permissions("hr", HR_MODULE_PERMISSIONS)


def create_hr_groups(sender, **kwargs):
    """Cria os perfis (Group templates) do módulo hr - mesmo mecanismo
    de saude/apps.py's create_saude_groups() (ver hr/profiles.py).
    Guard idêntico ao de todos os outros apps.py: só corre depois de
    já existir pelo menos uma EntityType real."""

    if kwargs.get("app_config").label != "hr":
        return

    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from hr.profiles import HR_PROFILES

    group_creator(HR_PROFILES)


class HrConfig(AppConfig):

    default_auto_field = "django.db.models.BigAutoField"

    name = "hr"
    label = "hr"

    verbose_name = "HR"

    def ready(self):
        """Carrega todas as views do módulo para que os decorators
        @registerView/@resaas_action corram e populem VIEW_REGISTRY
        ANTES do post_migrate (consumido por
        saas/core/signals/action_sync.py's sync_resaas_actions,
        que só cria/actualiza as Permissions das @resaas_action
        quando VIEW_REGISTRY já não está vazio) - mesmo padrão já
        usado por saude/sales/inventory/farmacia's apps.py. Sem isto,
        hr nunca tinha as suas custom action permissions
        (hire_application, calculate_payroll, approve_leaverequest,
        ...) criadas antes do primeiro pedido HTTP real resolver
        hr/urls.py - o que mascarava o problema em produção mas
        quebrava qualquer teste que criasse permissões via ORM antes
        de qualquer request."""

        import hr.views

        for _, module_name, _ in pkgutil.iter_modules(hr.views.__path__):
            importlib.import_module(f"hr.views.{module_name}")

        # permissions first: the profiles grant some of them
        post_migrate.connect(create_hr_module_permissions, sender=self)
        post_migrate.connect(create_hr_groups, sender=self)
