"""sales/apps.py chamava group_creator() com a lista clínica da saúde
copiada por engano - confirma que agora cria perfis reais de vendas."""
from django.test import TestCase

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.group import Group

from sales.profiles import SALES_PROFILES
from testutils.tenant import bootstrap_tenant


class SalesProfilesTests(TestCase):

    def test_sales_profiles_are_created(self):
        bootstrap_tenant("sales-profile-create", modules=("sales",))

        group_creator(SALES_PROFILES)

        self.assertTrue(Group.objects.filter(name="Sales Manager").exists())
        self.assertTrue(Group.objects.filter(name="Cashier").exists())

    def test_sales_manager_gets_real_sales_permissions_not_clinical(self):
        bootstrap_tenant("sales-profile-perms", modules=("sales",))

        group_creator(SALES_PROFILES)

        group = Group.objects.get(name="Sales Manager")
        codenames = set(group.permissions.values_list("codename", flat=True))

        self.assertIn("view_sale", codenames)
        self.assertIn("add_sale", codenames)
        # Nunca deve ganhar permissões clínicas - essa era a lista
        # errada, copiada de saude, que este perfil substitui.
        self.assertNotIn("view_paciente", codenames)
        self.assertNotIn("add_consulta", codenames)
