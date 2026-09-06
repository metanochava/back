from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.engine.core.base.views import BaseAPIView, registerView
from django_resaas.engine.core.decorators import resaas_action
from django_resaas.engine.core.utils import all, fail
from django_resaas.engine.models.person import Person

from saude.models.emergency_access import EmergencyAccess
from saude.serializers.emergency_access import EmergencyAccessSerializer
from saude.services.emergency_access_service import EmergencyAccessService


def _as_drf_validation_error(exc):
    return DRFValidationError(
        exc.messages if hasattr(exc, "messages") else str(exc)
    )


@registerView("emergency_accesses")
class EmergencyAccessAPIView(BaseAPIView):
    """
    Break-glass access a dados de uma Person que pode pertencer a
    outra Entity (ver docs/architecture/
    patient-longitudinal-health-pharmacy.md, Fase 2). list/retrieve
    genéricos ficam automaticamente scoped à Entity/Branch actual
    (EmergencyAccess é BaseModel) - é o log da PRÓPRIA Entity, nunca
    o de outra. Escrita SEMPRE via EmergencyAccessService: create/
    update/destroy genéricos ficam bloqueados propositadamente.
    """

    queryset = EmergencyAccess.objects.all()
    serializer_class = EmergencyAccessSerializer

    def create(self, request, *args, **kwargs):
        return fail(
            request,
            "Use the 'start' action to open an emergency access.",
            status=405,
        )

    def update(self, request, *args, **kwargs):
        return fail(
            request,
            "EmergencyAccess records are immutable except via 'end'/'review'.",
            status=405,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return fail(
            request,
            "EmergencyAccess records cannot be deleted.",
            status=405,
        )

    @resaas_action(
        methods=["post"],
        detail=False,
        label="Start",
        icon="emergency",
        tooltip="Abre um acesso de emergência a dados de uma Person de outra Entity",
        position="t",
        order=10,
    )
    def start(self, request):
        person_id = request.data.get("person_id")

        if not person_id:
            return fail(request, "person_id is required.", status=400)

        person = Person.objects.filter(id=person_id).first()

        if not person:
            return fail(request, "Person not found.", status=404)

        try:
            access = EmergencyAccessService.start(
                person=person,
                reason=request.data.get("reason"),
                scope=request.data.get("scope") or [],
                entity_id=request.entity_id,
                branch_id=request.branch_id,
                accessed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(request, data=self.get_serializer(access).data, status=201)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="End",
        icon="event_busy",
        tooltip="Termina este acesso de emergência",
        position="t",
        order=20,
    )
    def end(self, request, pk=None):
        access = self.get_object()

        try:
            EmergencyAccessService.end(access, ended_by=request.user)
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(request, data=self.get_serializer(access).data)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Review",
        icon="fact_check",
        tooltip="Regista a revisão pós-acesso deste emergency access",
        position="t",
        order=30,
    )
    def review(self, request, pk=None):
        access = self.get_object()

        try:
            EmergencyAccessService.review(access, reviewed_by=request.user)
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(request, data=self.get_serializer(access).data)
