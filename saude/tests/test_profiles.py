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

    OFFICIAL = {
        "Doctor", "Nurse", "Receptionist",
        "Clinical Lab Technician", "Laboratory Technician",
        "Radiology Technician", "Radiologist",
        "Pharmacist", "Cashier", "Health Administrator", "Patient",
    }

    def test_the_official_profiles_exist_once(self):
        # Garante que as Permission (view_paciente, etc.) já existem -
        # create_model_permissions só corre com uma EntityType já
        # criada, o que bootstrap_tenant() já garante.
        bootstrap_tenant("profile-create")

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        names = [p["name"] for p in SAUDE_PROFILES]
        self.assertEqual(set(names), self.OFFICIAL)
        self.assertEqual(len(names), len(set(names)))
        for name in self.OFFICIAL:
            self.assertEqual(Group.objects.filter(name=name).count(), 1, name)

    def test_every_default_permission_exists(self):
        """group_creator() never creates a permission: a codename that
        doesn't exist would be silently useless - the report lists it."""
        bootstrap_tenant("profile-perms-exist", modules=("saude", "hr"))  # list_/pdf_ permissions of saude

        report = group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        self.maxDiff = None
        self.assertEqual(report["permissions_missing"], {})

    def test_doctor_gets_default_permissions(self):
        bootstrap_tenant("profile-perms")

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        group = Group.objects.get(name="Doctor")
        codenames = set(group.permissions.values_list("codename", flat=True))

        self.assertIn("view_paciente", codenames)
        self.assertIn("add_consulta", codenames)

    def test_receptionist_can_load_the_booking_dialog_lookups(self):
        """The booking dialog lists specialties (hr), doctors, rooms and doctor
        schedules: without these the receptionist got 403 on hr/specialties."""
        bootstrap_tenant("profile-reception", modules=("saude", "hr"))

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        codenames = set(Group.objects.get(name="Receptionist").permissions.values_list("codename", flat=True))
        for model in ("specialty", "medico", "consultorio", "horariomedico"):
            self.assertTrue({f"list_{model}", f"view_{model}"} <= codenames, model)

    def test_lab_scientist_and_administrator_manage_the_exam_catalogue(self):
        """Creating an exam type answered 403 for every saude profile."""
        bootstrap_tenant("profile-exam-catalogue", modules=("saude", "hr"))

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        for name in ("Laboratory Technician", "Health Administrator"):
            codenames = set(Group.objects.get(name=name).permissions.values_list("codename", flat=True))
            for model in ("tipoexamemedico", "classeexamemedico"):
                self.assertTrue({f"list_{model}", f"add_{model}", f"change_{model}"} <= codenames, (name, model))
                self.assertNotIn(f"delete_{model}", codenames)

    def test_doctor_and_receptionist_can_open_the_exam_catalogue(self):
        """saude/catalogoexames/ (the exam request's catalogue) answers with
        list_tipoexamemedico; the doctor also needs the specialty lookups."""
        bootstrap_tenant("profile-doctor-lookups", modules=("saude", "hr"))

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        for name in ("Doctor", "Receptionist"):
            codenames = set(Group.objects.get(name=name).permissions.values_list("codename", flat=True))
            self.assertIn("list_tipoexamemedico", codenames, name)
            self.assertTrue({"list_specialty", "view_specialty", "list_medico", "view_medico"} <= codenames, name)

    def test_radiology_profiles_work_the_exam_flow(self):
        bootstrap_tenant("profile-radiology")
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        technician = set(Group.objects.get(name="Radiology Technician").permissions.values_list("codename", flat=True))
        radiologist = set(Group.objects.get(name="Radiologist").permissions.values_list("codename", flat=True))

        self.assertIn("record_result_itempedidoexamemedico", technician)
        self.assertNotIn("validate_resultadoexamemedico", technician)
        self.assertTrue({"validate_resultadoexamemedico", "release_resultadoexamemedico",
                         "amend_resultadoexamemedico"} <= radiologist)
        # the exam catalogue stays with the lab scientist and the administrator
        self.assertNotIn("add_examemedico", radiologist)

    def test_patient_has_only_portal_capabilities(self):
        """No clinical model permission: those would open clinical
        resources in general, not only the patient's own."""
        bootstrap_tenant("profile-patient")

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        codenames = set(Group.objects.get(name="Patient").permissions.values_list("codename", flat=True))
        self.assertEqual(codenames, {
            "view_patient_portal", "view_own_appointments", "view_own_exams", "view_own_results",
            "view_own_trends", "view_own_prescriptions", "view_own_vitals",
        })
        self.assertNotIn("grant_portal_access_paciente", codenames)

    def test_custom_permissions_are_preserved(self):
        bootstrap_tenant("profile-custom-perm", modules=("saude", "hr"))  # list_/pdf_ permissions of saude
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        nurse = Group.objects.get(name="Nurse")
        custom = Permission.objects.get(codename="pdf_consulta")  # not a Nurse default
        nurse.permissions.add(custom)

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        self.assertTrue(nurse.permissions.filter(pk=custom.pk).exists())

    def test_the_english_name_of_an_older_release_is_renamed_too(self):
        """An installation already on "General Practitioner" (English
        name before the 9 official profiles) keeps its Group.id."""
        old_group = Group.objects.create(name="General Practitioner")
        bootstrap_tenant("profile-rename-en")

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        old_group.refresh_from_db()
        self.assertEqual(old_group.name, "Doctor")
        self.assertEqual(Group.objects.filter(name="Doctor").count(), 1)

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

        self.assertEqual(old_group.name, "Doctor")
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


class SaudeProfilesOnTheSaudeTypeTests(TestCase):
    """create_saude_groups() also links the health profiles to the Saude
    EntityType and, when that link is new, to the existing Saude Entities
    (saude/apps.py, link_saude_profiles_to_type)."""

    def setUp(self):
        from django_resaas.saas.models.entity import Entity
        from django_resaas.saas.models.entity_type import EntityType

        self.saude_type, _ = EntityType.objects.get_or_create(name="Saude", defaults={"state": "Active"})
        self.clinic = Entity.objects.create(name="Clinic profiles", entity_type=self.saude_type)

    def _link(self):
        from saude.apps import link_saude_profiles_to_type

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        link_saude_profiles_to_type(SAUDE_PROFILES)

    def test_every_profile_is_linked_to_the_type_and_its_entities(self):
        from django_resaas.saas.models.entity_group import EntityGroup
        from django_resaas.saas.models.entity_type_group import EntityTypeGroup

        self._link()

        for name in ("Doctor", "Radiology Technician", "Radiologist"):
            group = Group.objects.get(name=name)
            self.assertTrue(EntityTypeGroup.objects.filter(entity_type=self.saude_type, group=group).exists(), name)
            self.assertTrue(EntityGroup.objects.filter(entity=self.clinic, group=group).exists(), name)

    def test_a_profile_an_entity_removed_is_not_put_back(self):
        from django_resaas.saas.models.entity_group import EntityGroup

        self._link()
        radiologist = Group.objects.get(name="Radiologist")
        EntityGroup.objects.filter(entity=self.clinic, group=radiologist).delete()

        self._link()

        self.assertFalse(EntityGroup.objects.filter(entity=self.clinic, group=radiologist).exists())


class ShortEnglishProfileNamesTests(TestCase):
    """2026-10-30: the long English names were shortened (the Portuguese ones
    translated). An installation still on the old names gets them renamed in
    place - same Group id, users and permissions."""

    def test_old_long_names_are_renamed_in_place(self):
        old = {
            "Medical Receptionist": "Receptionist",
            "Medical Laboratory Scientist": "Laboratory Technician",
            "Medical Laboratory Technician": "Clinical Lab Technician",
            "Healthcare Administrator": "Health Administrator",
        }
        ids = {name: Group.objects.create(name=name).id for name in old}

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        for old_name, new_name in old.items():
            self.assertFalse(Group.objects.filter(name=old_name).exists(), old_name)
            self.assertEqual(Group.objects.get(name=new_name).id, ids[old_name], new_name)


class TechniciansSeeThePatientListTests(TestCase):
    """The technicians open the patient list like the receptionist (list and
    view), without the receptionist's registration/editing permissions."""

    def test_every_technician_lists_patients_but_does_not_register_them(self):
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        for name in ("Clinical Lab Technician", "Laboratory Technician", "Radiology Technician"):
            codenames = set(Group.objects.get(name=name).permissions.values_list("codename", flat=True))
            self.assertTrue({"list_paciente", "view_paciente"} <= codenames, name)
            self.assertFalse({"add_paciente", "change_paciente", "register_paciente"} & codenames, name)
