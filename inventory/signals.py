from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


DASHBOARD_PERMISSIONS = [
    ("view_dashboard_inventory", "Can view inventory dashboard (branch scope)"),
    ("view_consolidated_dashboard_inventory", "Can view consolidated inventory dashboard (entity scope)"),
]


def create_inventory_dashboard_permissions(sender, **kwargs):
    """
    Os endpoints de dashboard do inventory não são CRUD (não passam por
    BaseAPIView/ModelViewSet), por isso o post_migrate signal do
    django_resaas (que só cria view/add/change/delete/list/pdf/
    pdf_list/restore/hard_delete por model) não os cria. Fazemos o
    mesmo aqui, à parte, seguindo o padrão de MODULE_PERMISSIONS do
    próprio pacote (django_resaas.engine.core.signals.permissions).
    """

    if kwargs.get("app_config").name != "inventory":
        return

    # import local: evita import de app ainda não totalmente carregada
    from django_resaas.engine.models.group import Group
    from inventory.models import Warehouse

    content_type = ContentType.objects.get_for_model(Warehouse)

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

    # Permissões de @resaas_action (ex.: 'finalizar_inventorycount')
    # são criadas pelo próprio django_resaas (ActionSyncService via
    # post_migrate), mas não são concedidas a nenhum group
    # automaticamente — concedemos ao Root aqui, best-effort (se
    # ainda não tiverem sido sincronizadas nesta execução, ficam
    # concedidas na próxima).
    action_perms = Permission.objects.filter(
        codename__in=["finalizar_inventorycount"]
    )
    if action_perms.exists():
        root_group.permissions.add(*action_perms)
