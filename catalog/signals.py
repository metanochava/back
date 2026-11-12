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


# the modules that sell, stock or buy catalogued items: when one of them is
# active for an Entity, so is the catalog (the rule of migration 0001, kept
# for the Entities activated later). settings.CATALOG_CONSUMER_MODULES
# overrides it. No module is imported - only the App names.
DEFAULT_CONSUMERS = ("inventory", "sales", "purchases", "farmacia")


def consumer_modules():
    from django.conf import settings

    return tuple(getattr(settings, "CATALOG_CONSUMER_MODULES", DEFAULT_CONSUMERS))


def activate_catalog_with_its_consumers(sender, instance, **kwargs):
    """EntityApp saved: a consumer module active for the Entity -> the
    catalog active for it too (created when missing, re-activated when it was
    turned off together)."""
    if instance.state != "Active" or getattr(instance.app, "name", None) not in consumer_modules():
        return

    from django_resaas.saas.models.app import App

    catalog, _ = App.objects.get_or_create(name="catalog", defaults={"state": "Active"})
    row, created = sender.objects.get_or_create(entity_id=instance.entity_id, app=catalog,
                                                defaults={"state": "Active"})
    if not created and row.state != "Active":
        row.state = "Active"
        row.save(update_fields=["state"])
