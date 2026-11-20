def grant_laboratorio_action_permissions(sender, **kwargs):
    """The action permissions (start_labsession, view_own_labsession, ...) exist on
    the first migrate (the profiles name them) and Root holds them."""
    if kwargs.get("app_config").name != "laboratorio":
        return

    from django.apps import apps
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    from django_resaas.saas.models.group import Group
    from laboratorio.profiles import ACTION_PERMISSIONS

    permissions = []
    for model_name, codenames in ACTION_PERMISSIONS.items():
        content_type = ContentType.objects.get_for_model(apps.get_model("laboratorio", model_name))
        for codename in codenames:
            permissions.append(Permission.objects.get_or_create(
                codename=codename, content_type=content_type,
                defaults={"name": f"Can {codename.rsplit('_' + model_name, 1)[0].replace('_', ' ')} {model_name}"},
            )[0])
    root, _ = Group.objects.get_or_create(name="Root")
    root.permissions.add(*permissions)


def create_laboratorio_groups(sender, **kwargs):
    if kwargs.get("app_config").name != "laboratorio":
        return

    from django.contrib.auth.management import create_permissions
    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from laboratorio.profiles import LABORATORIO_PROFILES

    create_permissions(kwargs["app_config"], verbosity=0, using=kwargs.get("using", "default"))
    group_creator(LABORATORIO_PROFILES)
