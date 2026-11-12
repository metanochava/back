from saude.services import reprint
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.utils import PDF, all

from saude.models.clinicalsummary import ClinicalSummary
from saude.serializers.clinicalsummary import ClinicalSummarySerializer
from saude.services import clinical_summary_service, consultation_service
from saude.services.document_edit_policy import DocumentEditWindowMixin
from saude.services.pdf_properties import pdf_properties
from saude.views.patient_filter import PatientFilterMixin


@registerView("clinicalsummaries")
# edited only by its author, within 24 h (document_edit_policy)
class ClinicalSummaryAPIView(PatientFilterMixin, DocumentEditWindowMixin, BaseAPIView):
    queryset = ClinicalSummary.objects.select_related(
        "consulta__paciente__person", "consulta__employee__person", "entity", "branch", "created_by",
    )
    serializer_class = ClinicalSummarySerializer

    def create(self, request, *args, **kwargs):
        # the summary belongs to a consultation of TODAY of this patient
        # (consultation_service.resolve_for_document): never one created
        # here, never a patient of another Entity
        _patient, _professional, consulta = consultation_service.resolve_for_document(
            request, request.data.get("paciente"), request.data.get("consulta")
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        summary = serializer.save(
            consulta=consulta,
            entity=consulta.entity,
            branch=consulta.branch,
            created_by=request.user,
            updated_by=request.user,
        )
        return all(request, data=self.get_serializer(summary).data, status=status.HTTP_201_CREATED)

    # the sections suggested from the patient's record (read only: the doctor
    # reviews them before issuing)
    @resaas_action(detail=False, methods=["GET"], label="Fill from the record", icon="auto_fix_high",
                   permission="add_clinicalsummary", visible=False)
    def draft(self, request):
        return Response(clinical_summary_service.draft(
            request, request.GET.get("paciente"), request.GET.get("consulta") or None,
        ))

    @action(detail=True, methods=["GET"])
    def pdf(self, request, *args, **kwargs):
        summary = self.get_object()
        return PDF("saude/clinicalsummary.html", request, print_date=reprint.print_date(request),
                   **clinical_summary_service.pdf_context(request, summary),
                   **pdf_properties("Clinical Summary", summary))
