from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


ACTION_PERMISSIONS = [
    "search_candidates_paciente",
    "timeline_paciente",
    "grant_consent_paciente",
    "revoke_consent_paciente",
    "start_emergencyaccess",
    "end_emergencyaccess",
    "review_emergencyaccess",
    "merge_patients_paciente",
    # laboratory flow (saude/services/exam_request_service.py)
    "check_in_pedidoexamemedico",
    "validate_resultadoexamemedico",
]


# Dashboards por grupo do sidebar (ver saude/sidebar.py e
# saude/views/dashboard.py) - não são @resaas_action (são
# TenantDashboardAPIView simples, plain APIView), por isso o
# ActionSyncService não os cria sozinho: temos de os criar aqui, tal
# como inventory/signals.py já faz para os seus próprios dashboards.
DASHBOARD_PERMISSIONS = [
    ("view_dashboard_saude_medicacao", "Can view Medicação dashboard"),
    ("view_dashboard_saude_documentos_medicos", "Can view Documentos Médicos dashboard"),
    ("view_dashboard_saude_exames", "Can view Exames dashboard"),
    ("view_dashboard_saude_historico_clinico", "Can view Histórico Clínico dashboard"),
    # Dashboard do motor genérico (django_resaas.saas.core.dashboards),
    # declarado em saude/dashboard.py - nome distinto de
    # 'view_saude_dashboard' (o dashboard antigo, DashBoarde.vue) e dos
    # 4 acima (dashboards por grupo do sidebar antigo), para não colidir
    # com nenhum dos dois.
    ("view_dashboard_saude_clinica", "Can view Clínica dashboard"),
    # Operational dashboards per work area (saude/dashboard.py's
    # DASHBOARDS) - granted to the matching profiles by saude/profiles.py
    ("view_dashboard_saude_reception", "Can view Reception dashboard"),
    ("view_dashboard_saude_nursing", "Can view Nursing dashboard"),
    ("view_dashboard_saude_doctor", "Can view Doctor dashboard"),
    ("view_dashboard_saude_laboratory", "Can view Laboratory dashboard"),
]


def grant_action_permissions_to_root(sender, **kwargs):
    """
    Permissões de @resaas_action (search_candidates) são criadas
    pelo próprio django_resaas (ActionSyncService via post_migrate),
    mas não são concedidas a nenhum group automaticamente -
    concedemos ao Root aqui, best-effort, mesmo padrão usado por
    farmacia (ver farmacia/signals.py) e inventory (ver
    inventory/signals.py).
    """

    if kwargs.get("app_config").name != "saude":
        return

    from django_resaas.saas.models.group import Group

    root_group, _ = Group.objects.get_or_create(name="Root")

    action_perms = Permission.objects.filter(codename__in=ACTION_PERMISSIONS)

    if action_perms.exists():
        root_group.permissions.add(*action_perms)


def create_and_grant_dashboard_permissions(sender, **kwargs):
    """
    Ao contrário das ACTION_PERMISSIONS acima, estas não existem
    ainda em lado nenhum - têm de ser criadas (não só concedidas).
    Usa o Paciente como content_type só para bookkeeping (o
    check_permission real filtra só por codename, nunca por
    content_type - ver django_resaas.saas.core.base.permissions).
    """

    if kwargs.get("app_config").name != "saude":
        return

    from django_resaas.saas.models.group import Group

    from saude.models.paciente import Paciente

    content_type = ContentType.objects.get_for_model(Paciente)
    root_group, _ = Group.objects.get_or_create(name="Root")

    created = []

    for codename, name in DASHBOARD_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults={"name": name},
        )
        created.append(perm)

    root_group.permissions.add(*created)
