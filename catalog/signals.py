def create_catalog_groups(sender, **kwargs):
    """The catalog's profiles (catalog/profiles.py), additive by name like
    the other modules' (group_creator)."""

    if kwargs.get("app_config").name != "catalog":
        return

    from django_resaas.saas.models.entity_type import EntityType

    if not EntityType.objects.exists():
        return

    from django_resaas.saas.core.utils.group_creator import group_creator
    from catalog.profiles import CATALOG_PROFILES

    group_creator(CATALOG_PROFILES)
