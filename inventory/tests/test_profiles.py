from django.test import TestCase

from django_resaas.engine.core.utils.group_creator import group_creator
from django_resaas.engine.models.group import Group

from inventory.profiles import INVENTORY_PROFILES
from testutils.tenant import bootstrap_tenant


class InventoryProfilesTests(TestCase):

    def test_inventory_profiles_are_created_with_permissions(self):
        bootstrap_tenant("inventory-profile", modules=("inventory",))

        group_creator(INVENTORY_PROFILES)

        self.assertTrue(Group.objects.filter(name="Inventory Manager").exists())
        self.assertTrue(Group.objects.filter(name="Storekeeper").exists())

        manager = Group.objects.get(name="Inventory Manager")
        codenames = set(manager.permissions.values_list("codename", flat=True))
        self.assertIn("view_product", codenames)
        self.assertIn("add_stockmovement", codenames)
