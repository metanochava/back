import importlib
import pkgutil

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CatalogConfig(AppConfig):
    """The commercial identity of what an Entity sells or buys: goods and
    services, categories, variants, media and price lists. Horizontal: no
    stock (inventory), no sales, no vertical module. Other modules use
    catalog.services and keep loose product ids."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Catalog"

    def ready(self):
        from django.db.models.signals import post_save

        from django_resaas.saas.models.entity_app import EntityApp

        from .signals import activate_catalog_with_its_consumers, create_catalog_groups

        post_migrate.connect(create_catalog_groups, sender=self)
        # selling, stocking or buying needs the catalogue: activating one of
        # those modules activates the catalog for the Entity too
        post_save.connect(activate_catalog_with_its_consumers, sender=EntityApp,
                          dispatch_uid="catalog_with_its_consumers")

        import catalog.views

        for _, module_name, _ in pkgutil.iter_modules(catalog.views.__path__):
            importlib.import_module(f"catalog.views.{module_name}")
