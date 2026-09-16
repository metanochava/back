"""Perfis (Group templates) de saude - mecanismo de referência usado
por todos os outros módulos (sales/inventory/farmacia) - ver
saude/apps.py's create_saude_groups() + saude/profiles.py +
engine/core/utils/group_creator.py.
"""
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.group import Group

from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM
from testutils.tenant import bootstrap_tenant


class SaudeProfilesTests(TestCase):

    def test_english_profiles_are_created(self):
        # Garante que as Permission (view_paciente, etc.) já existem -
        # create_model_permissions só corre com uma EntityType já
        # criada, o que bootstrap_tenant() já garante (mesma nota em
        # testutils/tenant.py's _ensure_crud_permissions()).
        bootstrap_tenant("profile-create")

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        self.assertTrue(Group.objects.filter(name="General Practitioner").exists())
        self.assertTrue(Group.objects.filter(name="Registered Nurse").exists())
        self.assertTrue(Group.objects.filter(name="Medical Director").exists())

    def test_general_practitioner_gets_default_permissions(self):
        bootstrap_tenant("profile-perms")

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        group = Group.objects.get(name="General Practitioner")
        codenames = set(group.permissions.values_list("codename", flat=True))

        self.assertIn("view_paciente", codenames)
        self.assertIn("add_consulta", codenames)

    def test_creating_profiles_twice_is_idempotent(self):
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        count_after_first = Group.objects.filter(
            name__in=[p["name"] for p in SAUDE_PROFILES]
        ).count()

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        count_after_second = Group.objects.filter(
            name__in=[p["name"] for p in SAUDE_PROFILES]
        ).count()

        self.assertEqual(count_after_first, count_after_second)
        self.assertEqual(count_after_first, len(SAUDE_PROFILES))

    def test_renaming_an_existing_group_preserves_id_and_relationships(self):
        """Simula uma instalação já em produção: um Group português já
        existe, já tem uma permissão e um utilizador associado -
        group_creator(rename_from=...) tem de renomear no lugar, nunca
        criar um Group novo a par do antigo."""
        old_group = Group.objects.create(name="Médico Geral")

        content_type = ContentType.objects.get_for_model(Group)
        legacy_perm, _ = Permission.objects.get_or_create(
            codename="legacy_custom_permission",
            content_type=content_type,
            defaults={"name": "Legacy custom permission"},
        )
        old_group.permissions.add(legacy_perm)

        tenant = bootstrap_tenant("profile-rename")
        BranchUserGroup.objects.create(
            user=tenant["user"], branch=tenant["branch"], group=old_group,
        )

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        old_group.refresh_from_db()

        self.assertEqual(old_group.name, "General Practitioner")
        self.assertFalse(Group.objects.filter(name="Médico Geral").exists())

        # A permissão antiga (nunca fazia parte do pacote por omissão)
        # continua lá - group_creator() é aditivo, nunca remove.
        self.assertTrue(old_group.permissions.filter(codename="legacy_custom_permission").exists())
        # As permissões novas por omissão também foram acrescentadas.
        self.assertTrue(old_group.permissions.filter(codename="view_paciente").exists())

        # A relação BranchUserGroup continua válida, apontando para o
        # MESMO Group (mesma PK) - nunca foi recriada.
        # bootstrap_tenant() também cria a sua própria BranchUserGroup
        # para o group "Root" - filtra pelo group renomeado
        # especificamente.
        relation = BranchUserGroup.objects.get(user=tenant["user"], group_id=old_group.id)
        self.assertEqual(relation.group_id, old_group.id)

    def test_profile_name_is_not_a_security_rule(self):
        """Um perfil totalmente novo, nunca listado em
        SAUDE_PROFILES, funciona desde que tenha as permissões certas
        - a segurança nunca depende do nome do Group."""
        bootstrap_tenant("profile-custom")

        custom_group = Group.objects.create(name="Senior Clinical Supervisor")
        perm = Permission.objects.filter(codename="view_paciente").first()
        self.assertIsNotNone(perm, "view_paciente deveria já existir via create_model_permissions")
        custom_group.permissions.add(perm)

        self.assertTrue(custom_group.permissions.filter(codename="view_paciente").exists())
