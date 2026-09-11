from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


ACTION_PERMISSIONS = [
    "revisar_filafarmacia",
    "dispensar_filafarmacia",
    "concluir_filafarmacia",
]

# 'view_farmacia_dashboard' já era referenciado em farmacia/sidebar.py
# desde antes deste motor existir, mas a Permission nunca tinha sido
# criada em lado nenhum - o item de menu ficava efectivamente
# invisível para todos (nem sequer Root a tinha, porque
# create_model_permissions só cria view/add/change/... por model, não
# permissões de dashboard). Corrigido aqui, mesmo padrão de
# DASHBOARD_PERMISSIONS já usado por inventory/sales/saude.
DASHBOARD_PERMISSIONS = [
    ("view_farmacia_dashboard", "Can view Farmácia dashboard"),
]


def grant_action_permissions_to_root(sender, **kwargs):
    """
    Permissões de @resaas_action (revisar/dispensar/concluir) são
    criadas pelo próprio django_resaas (ActionSyncService via
    post_migrate), mas não são concedidas a nenhum group
    automaticamente — concedemos ao Root aqui, best-effort, mesmo
    padrão usado por inventory (ver inventory/signals.py).
    """

    if kwargs.get("app_config").name != "farmacia":
        return

    from django_resaas.engine.models.group import Group

    root_group, _ = Group.objects.get_or_create(name="Root")

    action_perms = Permission.objects.filter(codename__in=ACTION_PERMISSIONS)

    if action_perms.exists():
        root_group.permissions.add(*action_perms)


def create_and_grant_dashboard_permissions(sender, **kwargs):
    """Cria (idempotente) e concede a Root as permissões de dashboard
    de farmacia - ver a nota em DASHBOARD_PERMISSIONS acima."""

    if kwargs.get("app_config").name != "farmacia":
        return

    from django_resaas.engine.models.group import Group
    from farmacia.models import FilaFarmacia

    content_type = ContentType.objects.get_for_model(FilaFarmacia)

    created = []
    for codename, name in DASHBOARD_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults={"name": name},
        )
        created.append(perm)

    root_group, _ = Group.objects.get_or_create(name="Root")
    root_group.permissions.add(*created)
