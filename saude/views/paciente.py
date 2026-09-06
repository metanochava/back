from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from django_resaas.engine.core.base.views import BaseAPIView, registerView
from django_resaas.engine.core.decorators import resaas_action
from django_resaas.engine.core.utils import (
    PDF,
    all,
    fail,
    make_barcode_b64,
    make_qr_b64,
    png_bytes_to_b64,
)
from django_resaas.engine.data.user.serializers.user import UserSerializer
from django_resaas.engine.models.entity import Entity
from django_resaas.engine.models.person import Person

from saude.models.consent_grant import ConsentGrant
from saude.models.paciente import Paciente
from saude.serializers.consent_grant import ConsentGrantSerializer
from saude.serializers.paciente import PacienteSerializer
from saude.serializers.patient_merge import PatientMergeSerializer
from saude.services.consent_service import ConsentService
from saude.services.patient_matching_service import PatientMatchingService
from saude.services.patient_merge_service import PatientMergeService
from saude.services.patient_timeline_service import PatientTimelineService


def _as_drf_validation_error(exc):
    return DRFValidationError(
        exc.messages if hasattr(exc, "messages") else str(exc)
    )


def generate_nid():
    year = timezone.now().strftime("%Y")
    last = Paciente.objects.filter(
        nid__startswith=f"PAC-{year}"
    ).order_by("-nid").first()

    number = int(last.nid.split("-")[-1]) + 1 if last else 1
    return f"PAC-{year}-{number:06d}"


@registerView("pacientes")
class PacienteAPIView(BaseAPIView):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["nid"] = generate_nid()
        data["state"] = "Active"

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        paciente = serializer.save(
            entity_id=request.entity_id,
            branch_id=request.branch_id,
            created_by=request.user,
            updated_by=request.user,
        )

        return all(
            request,
            data=self.get_serializer(paciente).data,
            status=201,
        )

    @action(detail=True, methods=["get"])
    def pdf(self, request, *args, **kwargs):
        paciente = self.get_object()
        entity = paciente.entity

        logo_b64 = self.file_to_b64(
            getattr(entity, "logo", None)
        )

        user = getattr(paciente.person, "user", None)
        profile = None
        profile_b64 = None

        if user:
            profile = UserSerializer(
                user,
                context={
                    "request": request,
                    "include_fields": ["profile"],
                },
            ).data.get("profile")

            profile_b64 = self.file_to_b64(
                getattr(user, "profile", None)
            )

        return PDF(
            "saude/paciente.html",
            request,
            entity=entity,
            paciente=paciente,
            logo_b64=logo_b64,
            profile=profile,
            profile_b64=profile_b64,
            qr_b64=make_qr_b64(str(paciente.id)),
            barcode_b64=make_barcode_b64(
                str(paciente.nid or paciente.id)
            ),
            data_emissao=timezone.now().date(),
        )

    @staticmethod
    def file_to_b64(file):
        try:
            if file and file.path:
                with open(file.path, "rb") as content:
                    return png_bytes_to_b64(content.read())
        except Exception:
            pass

        return None

    def get_pdflist_context(self, request, queryset):
        context = super().get_pdflist_context(request, queryset)
        context.update({
            "titulo": "Lista de Pacientes",
            "pacientes": queryset,
        })
        return context

    @resaas_action(
        methods=["get"],
        detail=False,
        label="Search Candidates",
        icon="search",
        tooltip="Procurar Paciente já existente noutra Entity antes de registar um novo",
        position="t",
        order=1,
    )
    def search_candidates(self, request):
        """
        Fase 1 da iniciativa Patient longitudinal (ver
        docs/architecture/patient-longitudinal-health-pharmacy.md) -
        sugere Paciente/Person já existentes, cross-entity, sem
        nunca criar ou fundir automaticamente. Acção explícita e
        própria (não `list` genérico) para não expor varrimento
        livre de Person entre Entities - só quem tiver a permission
        `search_candidates_paciente` pode chamar.
        """
        params = request.query_params

        candidates = PatientMatchingService.find_candidates(
            nid=params.get("nid"),
            identifier=params.get("identifier"),
            email=params.get("email"),
            phone=params.get("phone"),
            name=params.get("name"),
            date_of_birth=params.get("date_of_birth") or None,
        )

        if candidates is None:
            return fail(
                request,
                "At least one search criterion is required "
                "(nid, identifier, email, phone, or name + date_of_birth).",
                status=400,
            )

        return all(request, candidates=candidates)

    @resaas_action(
        methods=["get"],
        detail=False,
        label="Timeline",
        icon="timeline",
        tooltip="Linha do tempo clínica, incluindo eventos autorizados de outras Entities",
        position="t",
        order=1,
    )
    def timeline(self, request):
        """
        Fase 4 (ver docs/architecture/patient-longitudinal-health-pharmacy.md)
        - por person_id (não paciente pk): a Entity actual pode não
        ter sequer um Paciente próprio para esta Person ainda (ex.:
        primeiro acesso via emergency access). Nunca usa o
        get_object()/get_queryset() tenant-scoped - a agregação
        cross-entity é feita explicitamente pelo service, sempre
        filtrada pelo scope autorizado.
        """
        person_id = request.query_params.get("person_id")

        if not person_id:
            return fail(request, "person_id is required.", status=400)

        person = Person.objects.filter(id=person_id).first()

        if not person:
            return fail(request, "Person not found.", status=404)

        requesting_entity = self.get_request_entity(request)

        events = PatientTimelineService.build_timeline(
            person=person,
            requesting_entity=requesting_entity,
        )

        return all(request, events=events)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Grant Consent",
        icon="share",
        tooltip="Autoriza outra Entity a ver um scope dos dados clínicos deste Paciente",
        position="t",
        order=2,
    )
    def grant_consent(self, request, pk=None):
        """
        Fase 2 (ver docs/architecture/patient-longitudinal-health-pharmacy.md)
        - grant_consent/revoke_consent operam sobre um Paciente da
        Entity ACTUAL (scope normal, get_object() já garante isso) -
        é a Entity dona do registo que decide partilhá-lo, nunca o
        contrário. Único ponto de escrita: ConsentService.
        """
        paciente = self.get_object()

        target_entity_id = request.data.get("target_entity_id")

        if not target_entity_id:
            return fail(request, "target_entity_id is required.", status=400)

        target_entity = Entity.objects.filter(id=target_entity_id).first()

        if not target_entity:
            return fail(request, "target_entity not found.", status=404)

        source_entity = self.get_request_entity(request)

        try:
            consent = ConsentService.grant(
                person=paciente.person,
                source_entity=source_entity,
                target_entity=target_entity,
                scope=request.data.get("scope") or [],
                reason=request.data.get("reason"),
                expires_at=request.data.get("expires_at") or None,
                granted_by=request.user,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(
            request,
            data=ConsentGrantSerializer(consent).data,
            status=201,
        )

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Revoke Consent",
        icon="block",
        tooltip="Revoga um consentimento previamente concedido para este Paciente",
        position="t",
        order=3,
    )
    def revoke_consent(self, request, pk=None):
        paciente = self.get_object()

        consent_grant_id = request.data.get("consent_grant_id")

        if not consent_grant_id:
            return fail(request, "consent_grant_id is required.", status=400)

        consent = ConsentGrant.objects.filter(
            id=consent_grant_id, person=paciente.person
        ).first()

        if not consent:
            return fail(
                request,
                "ConsentGrant not found for this Paciente.",
                status=404,
            )

        requesting_entity = self.get_request_entity(request)

        try:
            ConsentService.revoke(
                consent,
                revoked_by=request.user,
                requesting_entity=requesting_entity,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(request, data=ConsentGrantSerializer(consent).data)

    @resaas_action(
        methods=["post"],
        detail=False,
        label="Merge Patients",
        icon="merge_type",
        tooltip="Funde duas identidades de Paciente que afinal são a mesma pessoa",
        position="t",
        order=4,
    )
    def merge_patients(self, request):
        """
        Fase 5 (ver docs/architecture/patient-longitudinal-health-pharmacy.md)
        - última e mais arriscada por ser parcialmente irreversível.
        `survivor_paciente_id` tem de pertencer à Entity actual (é a
        Entity dona do registo sobrevivente que decide a fusão);
        `duplicate_paciente_id` pode pertencer a qualquer Entity
        (tipicamente encontrado via search_candidates). Único ponto
        de escrita: PatientMergeService.
        """
        survivor_paciente_id = request.data.get("survivor_paciente_id")
        duplicate_paciente_id = request.data.get("duplicate_paciente_id")

        if not survivor_paciente_id or not duplicate_paciente_id:
            return fail(
                request,
                "survivor_paciente_id and duplicate_paciente_id are required.",
                status=400,
            )

        survivor_paciente = Paciente.objects.filter(
            id=survivor_paciente_id,
            entity_id=request.entity_id,
        ).first()

        if not survivor_paciente:
            return fail(
                request,
                "survivor Paciente not found in your Entity.",
                status=404,
            )

        duplicate_paciente = Paciente.objects.filter(id=duplicate_paciente_id).first()

        if not duplicate_paciente:
            return fail(request, "duplicate Paciente not found.", status=404)

        try:
            merge_record = PatientMergeService.merge(
                survivor_person=survivor_paciente.person,
                duplicate_person=duplicate_paciente.person,
                performed_by=request.user,
                entity_id=request.entity_id,
                branch_id=request.branch_id,
                reason=request.data.get("reason"),
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(
            request,
            data=PatientMergeSerializer(merge_record).data,
            status=201,
        )

    # @resaas_action(
    #     methods=["post"],
    #     detail=True,
    #     label="Test Action",
    #     icon="event",
    #     tooltip="Test RESAAS action",
    #     position="r",
    #     order=10,
    #     visible=True,
    # )
    # def test_action(self, request, pk=None):
    #     return Response({"success": True})

    # @resaas_action(
    #     methods=["post"],
    #     detail=False,
    #     label="Action",
    #     icon="science",
    #     tooltip="Test action",
    #     position="t",
    #     order=10,
    #     visible=True,
    #     autorequest=True,
    # )
    # def pdf_post(self, request, pk=None):
    #     return Response({"Post": True})

    # @resaas_action(
    #     methods=["post"],
    #     detail=False,
    #     label="Mais",
    #     icon="event",
    #     tooltip="Test RESAAS action",
    #     position="t",
    #     order=10,
    #     visible=True,
    #     autorequest=True,
    # )
    # def pdf_up(self, request, pk=None):
    #     return Response({"Mais": True})

    # @resaas_action(
    #     methods=["get"],
    #     detail=True,
    #     label="Test Action",
    #     icon="science",
    #     tooltip="Test RESAAS action",
    #     position="l",
    #     order=10,
    # )
    # def pdf_get(self, request, pk=None):
    #     return Response({"success get": True})

    # @resaas_action(
    #     methods=["get"],
    #     detail=True,
    #     label="Menu",
    #     icon="science",
    #     tooltip="Test RESAAS action",
    #     position="M",
    #     order=10,
    # )
    # def pdf_getk(self, request, pk=None):
    #     return Response({"success get": True})