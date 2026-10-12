def grant_crm_action_permissions(sender, **kwargs):
    """The @resaas_action permissions (qualify_lead, ...) are granted to
    no group by the framework: Root gets them here (same as accounting)."""

    if kwargs.get("app_config").name != "crm":
        return

    from django.apps import apps
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    from django_resaas.saas.models.group import Group
    from crm.profiles import ACTION_PERMISSIONS

    permissions = []
    for model_name, codenames in ACTION_PERMISSIONS.items():
        content_type = ContentType.objects.get_for_model(apps.get_model("crm", model_name))
        for codename in codenames:
            permissions.append(Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": f"Can {codename.rsplit('_' + model_name, 1)[0].replace('_', ' ')} {model_name}"},
            )[0])

    root_group, _ = Group.objects.get_or_create(name="Root")
    root_group.permissions.add(*permissions)


def create_crm_groups(sender, **kwargs):
    if kwargs.get("app_config").name != "crm":
        return

    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from crm.profiles import CRM_PROFILES

    group_creator(CRM_PROFILES)
