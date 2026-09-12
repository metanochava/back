from django.test import TestCase

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.group import Group

from farmacia.profiles import FARMACIA_PROFILES
from testutils.tenant import bootstrap_tenant


class FarmaciaProfilesTests(TestCase):

    def test_farmacia_profiles_are_created_with_permissions(self):
        bootstrap_tenant("farmacia-profile", modules=("farmacia", "saude", "hr"))

        group_creator(FARMACIA_PROFILES)

        self.assertTrue(Group.objects.filter(name="Pharmacy Manager").exists())

        pharmacist = Group.objects.get(name="Pharmacist")
        codenames = set(pharmacist.permissions.values_list("codename", flat=True))
        self.assertIn("dispensar_filafarmacia", codenames)

    def test_pharmacist_group_is_shared_with_saude(self):
        """Group.name é único globalmente - farmacia e saude usam o
        MESMO Group 'Pharmacist' de propósito (CLAUDE.md: perfis
        partilhados quando a arquitectura já o suporta)."""
        bootstrap_tenant("farmacia-shared-profile", modules=("farmacia", "saude", "hr"))

        from saude.profiles import SAUDE_PROFILES
        group_creator(SAUDE_PROFILES)
        saude_pharmacist_id = Group.objects.get(name="Pharmacist").id

        group_creator(FARMACIA_PROFILES)
        farmacia_pharmacist_id = Group.objects.get(name="Pharmacist").id

        self.assertEqual(saude_pharmacist_id, farmacia_pharmacist_id)

        combined = Group.objects.get(name="Pharmacist").permissions.values_list("codename", flat=True)
        codenames = set(combined)
        self.assertIn("view_receitamedica", codenames)  # de saude
        self.assertIn("dispensar_filafarmacia", codenames)  # de farmacia
