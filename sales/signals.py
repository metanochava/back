from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


DASHBOARD_PERMISSIONS = [
    ("view_dashboard_sales", "Can view sales dashboard (branch scope)"),
    ("view_consolidated_dashboard_sales", "Can view consolidated sales dashboard (entity scope)"),
]


def create_sales_dashboard_permissions(sender, **kwargs):
    """
    Mesma razão que inventory/signals.py: endpoints de dashboard não
    são CRUD, por isso o post_migrate signal do django_resaas não os
    cria sozinho.
    """

    if kwargs.get("app_config").name != "sales":
        return

    from django_resaas.engine.models.group import Group
    from sales.models import Customer

    content_type = ContentType.objects.get_for_model(Customer)

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

    action_perms = Permission.objects.filter(
        codename__in=["confirmar_sale", "anular_sale", "pagar_sale", "disponibilidade_sale"]
    )
    if action_perms.exists():
        root_group.permissions.add(*action_perms)
