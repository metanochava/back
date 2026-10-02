"""Perfis (Group templates) do módulo hr - ver hr/profiles.py +
hr/apps.py's create_hr_groups(). Mesmo mecanismo group_creator() já
testado para saas/profiles.py's CORE_PROFILES (saas/tests/
test_core_profiles.py) e para saude/sales/inventory/farmacia's
profiles (dev/back).

Usa a fixture `bootstrap_tenant` (conftest.py da própria biblioteca)
antes de qualquer group_creator() que use codenames 'list_'/
'view_dashboard_hr_*' - essas Permissions só são criadas por
saas/core/signals/permissions.py depois de já existir uma
EntityType real (ver o docstring da própria fixture); sem isto,
ficam silenciosamente por conceder (Permission.objects.filter(
codename__in=...) nunca falha, só devolve menos linhas)."""
import pytest

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.group import Group
from hr.profiles import HR_PROFILES

pytestmark = pytest.mark.django_db


ALL_PROFILE_NAMES = (
    "Human Resources Manager", "HR Officer", "Recruitment Specialist",
    "Payroll Specialist", "Training and Development Specialist",
    "Employee Relations Officer", "HR Administrator",
)


def test_hr_profiles_are_created_with_permissions(bootstrap_tenant):
    bootstrap_tenant("hr-profile-1")
    group_creator(HR_PROFILES)

    for name in ALL_PROFILE_NAMES:
        assert Group.objects.filter(name=name).exists(), name


def test_hr_manager_gets_broad_cross_domain_permissions(bootstrap_tenant):
    bootstrap_tenant("hr-profile-2")
    group_creator(HR_PROFILES)

    group = Group.objects.get(name="Human Resources Manager")
    codenames = set(group.permissions.values_list("codename", flat=True))

    assert "approve_leaverequest" in codenames
    assert "calculate_payroll" in codenames
    assert "view_dashboard_hr_organizacao" in codenames
    assert "view_dashboard_hr_ciclo_vida" in codenames


def test_recruitment_specialist_is_scoped_to_hiring_workflow(bootstrap_tenant):
    bootstrap_tenant("hr-profile-3")
    group_creator(HR_PROFILES)

    group = Group.objects.get(name="Recruitment Specialist")
    codenames = set(group.permissions.values_list("codename", flat=True))

    assert "hire_application" in codenames
    assert "schedule_interview_application" in codenames
    # Não gere folha de pagamento nem processos disciplinares.
    assert "calculate_payroll" not in codenames
    assert "start_review_disciplinarycase" not in codenames


def test_payroll_specialist_is_scoped_to_payroll(bootstrap_tenant):
    bootstrap_tenant("hr-profile-4")
    group_creator(HR_PROFILES)

    group = Group.objects.get(name="Payroll Specialist")
    codenames = set(group.permissions.values_list("codename", flat=True))

    assert "calculate_payroll" in codenames
    assert "mark_paid_payroll" in codenames
    # Não recruta nem gere disciplina.
    assert "hire_application" not in codenames
    assert "resolve_disciplinarycase" not in codenames


def test_employee_relations_officer_handles_workplace_conduct(bootstrap_tenant):
    bootstrap_tenant("hr-profile-5")
    group_creator(HR_PROFILES)

    group = Group.objects.get(name="Employee Relations Officer")
    codenames = set(group.permissions.values_list("codename", flat=True))

    assert "approve_leaverequest" in codenames
    assert "resolve_disciplinarycase" in codenames
    assert "accept_resignation" in codenames
    # Não calcula folha de pagamento.
    assert "calculate_payroll" not in codenames


def test_hr_administrator_is_configuration_only(bootstrap_tenant):
    bootstrap_tenant("hr-profile-6")
    group_creator(HR_PROFILES)

    group = Group.objects.get(name="HR Administrator")
    codenames = set(group.permissions.values_list("codename", flat=True))

    assert "add_jobposition" in codenames
    assert "add_leavetype" in codenames
    # Não vê dados operacionais de funcionários nem dashboards -
    # é só configuração/master-data.
    assert "view_employee" not in codenames
    assert not any(c.startswith("view_dashboard_hr_") for c in codenames)


def test_hr_profiles_are_idempotent(bootstrap_tenant):
    bootstrap_tenant("hr-profile-7")
    group_creator(HR_PROFILES)
    group_creator(HR_PROFILES)

    assert Group.objects.filter(name="Human Resources Manager").count() == 1


def test_hr_profiles_use_only_real_permission_codenames(bootstrap_tenant):
    """Todos os codenames usados em HR_PROFILES têm de existir mesmo
    na base de dados (nunca inventados) - falha alto e explicitamente
    se algum não existir, em vez de group_creator() simplesmente
    ignorar em silêncio (Permission.objects.filter(codename__in=...))."""
    from django.contrib.auth.models import Permission

    bootstrap_tenant("hr-profile-8")

    real_codenames = set(
        Permission.objects.filter(content_type__app_label="hr").values_list("codename", flat=True)
    )

    used_codenames = {
        codename
        for profile in HR_PROFILES
        for codename in profile["permissions"]
    }

    missing = used_codenames - real_codenames
    assert not missing, f"Codenames inexistentes em HR_PROFILES: {sorted(missing)}"


def test_hr_adds_its_permissions_to_the_platform_administration_profiles(bootstrap_tenant):
    """The core's administration profiles only name core permissions; the hr
    module adds employees/departments to them (group_creator is additive by
    profile name) - this used to be hardcoded in django_resaas."""
    from django_resaas.saas.profiles import CORE_PROFILES

    bootstrap_tenant("hr-admin-profiles")
    group_creator(CORE_PROFILES)
    group_creator(HR_PROFILES)

    organization = set(Group.objects.get(name="Organization Administrator").permissions.values_list("codename", flat=True))
    branch = set(Group.objects.get(name="Branch Administrator").permissions.values_list("codename", flat=True))

    assert {"add_employee", "add_department", "add_branch"} <= organization
    assert {"view_employee", "list_department", "add_branchuser"} <= branch
    assert "add_employee" not in branch


def test_hr_creates_its_own_dashboard_permissions(bootstrap_tenant):
    """Module permissions come from hr/apps.py (ensure_module_permissions),
    not from django_resaas's core."""
    from django.contrib.auth.models import Permission

    bootstrap_tenant("hr-module-perms")

    assert Permission.objects.filter(codename="view_hr_dashboard", content_type__app_label="hr").exists()
