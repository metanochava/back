def grant_hospitality_action_permissions(sender, **kwargs):
    """The @resaas_action permissions (board_diningtable, ...) are created
    here (so the profiles find them on the first migrate) and given to Root."""

    if kwargs.get("app_config").name != "hospitality":
        return

    from django.apps import apps
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    from django_resaas.saas.models.group import Group
    from hospitality.profiles import ACTION_PERMISSIONS

    permissions = []
    for model_name, codenames in ACTION_PERMISSIONS.items():
        content_type = ContentType.objects.get_for_model(apps.get_model("hospitality", model_name))
        for codename in codenames:
            permissions.append(Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": f"Can {codename.rsplit('_' + model_name, 1)[0].replace('_', ' ')} {model_name}"},
            )[0])

    root_group, _ = Group.objects.get_or_create(name="Root")
    root_group.permissions.add(*permissions)


def create_hospitality_groups(sender, **kwargs):
    if kwargs.get("app_config").name != "hospitality":
        return

    from django.contrib.auth.management import create_permissions
    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from hospitality.profiles import HOSPITALITY_PROFILES

    # the model permissions before the profiles name them
    create_permissions(kwargs["app_config"], verbosity=0, using=kwargs.get("using", "default"))
    group_creator(HOSPITALITY_PROFILES)
