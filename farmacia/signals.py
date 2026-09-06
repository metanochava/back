from django.contrib.auth.models import Permission


ACTION_PERMISSIONS = [
    "revisar_filafarmacia",
    "dispensar_filafarmacia",
    "concluir_filafarmacia",
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
