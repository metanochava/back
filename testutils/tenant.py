"""
Fixture partilhada para testes de tenant multi-entity.

O pacote django_resaas tem o seu próprio fixture pytest `bootstrap_tenant`
(usado nos testes internos do próprio pacote), mas não o expõe como
plugin pytest para projetos consumidores — e este projeto usa
`manage.py test` (unittest/Django TestCase), não pytest. Por isso
replicamos aqui o essencial, usando só API pública do pacote.
"""

import itertools

from django.apps import apps as django_apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from django_resaas.models.entity import Entity
from django_resaas.models.entity_type import EntityType
from django_resaas.models.branch import Branch
from django_resaas.models.entity_user import EntityUser
from django_resaas.models.branch_user import BranchUser
from django_resaas.models.branch_user_group import BranchUserGroup
from django_resaas.models.group import Group
from django_resaas.models.app import App
from django_resaas.models.entity_app import EntityApp
from django_resaas.models.user import User
from django_resaas.core.tenant.context import ResaasContextService


_counter = itertools.count(1)


CRUD_CODENAMES = [
    ("view", "Can view"), ("add", "Can add"), ("change", "Can change"), ("delete", "Can delete"),
    ("list", "Can list"), ("pdf", "Can pdf"), ("pdf_list", "Can pdf list"),
    ("restore", "Can restore"), ("hard_delete", "Can hard delete"),
]


def _ensure_crud_permissions(group, app_labels):
    """
    django_resaas.core.signals.permissions.create_model_permissions (que
    normalmente cria e concede ao group 'Root' as permissões
    list_/view_/add_/change_/delete_/pdf_/pdf_list_/restore_/hard_delete_
    por model) tem `if not EntityType.objects.exists(): return` — ou
    seja, numa base de dados nova (sem nenhuma EntityType ainda), essa
    sincronização NUNCA corre no migrate inicial, porque a própria
    verificação depende de já existir a entity que só o teste vai
    criar a seguir. Na prática isto só "resolve-se sozinho" se o
    `migrate` for corrido de novo depois de já existir alguma
    EntityType (o que aconteceu por acaso neste projeto durante o
    desenvolvimento, mascarando o problema).

    Para não depender dessa corrida, garantimos aqui exatamente as
    mesmas permissões, para os app_labels pedidos.
    """

    perms = []

    for model in django_apps.get_models():
        if model._meta.app_label not in app_labels:
            continue

        content_type = ContentType.objects.get_for_model(model)

        for codename, label in CRUD_CODENAMES:
            perm, _ = Permission.objects.get_or_create(
                codename=f"{codename}_{model._meta.model_name}",
                content_type=content_type,
                defaults={"name": f"{label} {model._meta.verbose_name}"},
            )
            perms.append(perm)

    group.permissions.add(*perms)


def bootstrap_tenant(label, modules=(), extra_permissions=()):
    """
    Cria um tenant completo e isolado (EntityType/Entity/Branch/User)
    com um Group próprio ("Root", já com todas as permissões CRUD
    criadas pelo post_migrate signal do django_resaas), ativa os
    módulos pedidos, e devolve um APIClient já autenticado com o
    contexto RESAAS correto.

    extra_permissions: codenames adicionais a garantir no group,
    além de tudo o que "Root" já tiver (ex.: permissões de
    dashboard que não são criadas automaticamente por model).
    """

    n = next(_counter)

    entity_type = EntityType.objects.create(name=f"EntityType {label}-{n}")

    entity = Entity.objects.create(
        name=f"Entity {label}-{n}",
        entity_type=entity_type,
    )

    branch = Branch.objects.create(
        name=f"Branch {label}-{n}",
        entity=entity,
    )

    user = User.objects.create_user(
        username=f"user-{label}-{n}",
        email=f"user-{label}-{n}@example.com",
        password="test-pass-123",
    )

    EntityUser.objects.create(entity=entity, user=user)
    BranchUser.objects.create(branch=branch, user=user)

    group, _ = Group.objects.get_or_create(name="Root")

    _ensure_crud_permissions(group, set(modules) | {"django_resaas"})

    if extra_permissions:
        content_type = ContentType.objects.get_for_model(Entity)

        for codename in extra_permissions:
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": codename},
            )
            group.permissions.add(perm)

    BranchUserGroup.objects.create(branch=branch, user=user, group=group)

    for module_name in modules:
        app, _ = App.objects.get_or_create(name=module_name)
        EntityApp.objects.create(entity=entity, app=app, state="Active")

    issued = ResaasContextService.issue(
        user=user,
        entity_id=entity.id,
        branch_id=branch.id,
        group_id=group.id,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(
        HTTP_X_RESAAS_CONTEXT=issued["token"],
        HTTP_L="1",
    )

    return {
        "entity_type": entity_type,
        "entity": entity,
        "branch": branch,
        "user": user,
        "group": group,
        "client": client,
    }
