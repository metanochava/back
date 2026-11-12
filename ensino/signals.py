def create_ensino_groups(sender, **kwargs):
    if kwargs.get("app_config").name != "ensino":
        return

    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from ensino.profiles import ENSINO_PROFILES

    group_creator(ENSINO_PROFILES)
