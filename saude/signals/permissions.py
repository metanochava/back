from django.contrib.auth.models import Permission


ACTION_PERMISSIONS = [
    "search_candidates_paciente",
    "timeline_paciente",
    "grant_consent_paciente",
    "revoke_consent_paciente",
    "start_emergencyaccess",
    "end_emergencyaccess",
    "review_emergencyaccess",
]


def grant_action_permissions_to_root(sender, **kwargs):
    """
    Permissões de @resaas_action (search_candidates) são criadas
    pelo próprio django_resaas (ActionSyncService via post_migrate),
    mas não são concedidas a nenhum group automaticamente -
    concedemos ao Root aqui, best-effort, mesmo padrão usado por
    farmacia (ver farmacia/signals.py) e inventory (ver
    inventory/signals.py).
    """

    if kwargs.get("app_config").name != "saude":
        return

    from django_resaas.engine.models.group import Group

    root_group, _ = Group.objects.get_or_create(name="Root")

    action_perms = Permission.objects.filter(codename__in=ACTION_PERMISSIONS)

    if action_perms.exists():
        root_group.permissions.add(*action_perms)
