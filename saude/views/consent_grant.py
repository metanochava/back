from django.db.models import Q

from django_resaas.engine.core.base.views import BaseAPIView, registerView
from django_resaas.engine.core.utils import fail

from saude.models.consent_grant import ConsentGrant
from saude.serializers.consent_grant import ConsentGrantSerializer


@registerView("consent_grants")
class ConsentGrantAPIView(BaseAPIView):
    """
    Read-only: ConsentGrant não é BaseModel (existe entre DUAS
    Entities, ver saude/models/consent_grant.py) por isso o
    get_queryset genérico de BaseAPIView não o filtra sozinho -
    aqui restringimos explicitamente a grants em que a Entity actual
    é parte (concedeu OU recebeu). Escrita SEMPRE via
    ConsentService.grant()/.revoke() - PacienteAPIView.grant_consent/
    revoke_consent - nunca por aqui.
    """

    queryset = ConsentGrant.objects.all()
    serializer_class = ConsentGrantSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        entity_id = self.request.entity_id

        return qs.filter(
            Q(source_entity_id=entity_id) | Q(target_entity_id=entity_id)
        )

    def create(self, request, *args, **kwargs):
        return fail(
            request,
            "Use Paciente's 'grant_consent' action to create a consent grant.",
            status=405,
        )

    def update(self, request, *args, **kwargs):
        return fail(
            request,
            "ConsentGrant records are immutable except via 'revoke_consent'.",
            status=405,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return fail(
            request,
            "ConsentGrant records cannot be deleted.",
            status=405,
        )
