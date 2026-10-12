def grant_purchases_action_permissions(sender, **kwargs):
    """The @resaas_action permissions of purchases (submit_purchaseorder, ...)
    are created by django_resaas's ActionSyncService but granted to no group:
    Root gets them here (same as sales/inventory signals.py)."""

    if kwargs.get("app_config").name != "purchases":
        return

    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    from django_resaas.saas.models.group import Group
    from purchases.models import PurchaseOrder
    from purchases.profiles import ACTION_PERMISSIONS

    content_type = ContentType.objects.get_for_model(PurchaseOrder)
    permissions = [
        Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults={"name": f"Can {codename.rsplit('_', 1)[0].replace('_', ' ')} purchase order"},
        )[0]
        for codename in ACTION_PERMISSIONS
    ]

    root_group, _ = Group.objects.get_or_create(name="Root")
    root_group.permissions.add(*permissions)


def create_purchases_groups(sender, **kwargs):
    if kwargs.get("app_config").name != "purchases":
        return

    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from purchases.profiles import PURCHASES_PROFILES

    group_creator(PURCHASES_PROFILES)
