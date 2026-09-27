from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from saude.services.document_edit_policy import DocumentEditWindowMixin
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import (
    make_qr_b64,
    make_barcode_b64,
    png_bytes_to_b64,
    PDF
)

from saude.models.consulta import Consulta
from saude.models.agenda import Agenda
from saude.serializers.consulta import ConsultaSerializer
from saude.services.exam_request_service import require_professional, resolve_patient
from saude.services import consultation_service, prescription_service
from django_resaas.saas.core.decorators.action import resaas_action


@registerView("consultas")
# edited only by its author, within 24 h (document_edit_policy)
class ConsultaAPIView(DocumentEditWindowMixin, BaseAPIView):

    queryset = Consulta.objects.all()
    serializer_class = ConsultaSerializer

    # POST consultas/ (add_consulta): the professional is the caller's
    # Employee in this Branch (never the client's value) and the patient must
    # be of this Entity.
    def perform_create(self, serializer):
        patient = serializer.validated_data.get("paciente")
        resolve_patient(self.request, patient.id if patient else None)
        serializer.validated_data["employee"] = require_professional(self.request)
        super().perform_create(serializer)
        # the consultation of today's appointment with this doctor
        prescription_service.link_to_todays_appointment(serializer.instance)

    # What the consultation form shows: the professional signing it and the
    # patient (tenant scoped). Read only; needs add_consulta.
    @resaas_action(detail=False, methods=["get"], label="Consultation form", icon="medical_services",
                   permission="add_consulta", visible=False)
    def intake(self, request, *args, **kwargs):
        return Response(consultation_service.intake_context(request, request.query_params.get("paciente")))


    @action(detail=True, methods=["GET"])
    def receitas(self, request, pk=None):
        pass

    @action(detail=True, methods=["GET"])
    def exames(self, request, pk=None):
        pass

    @action(detail=True, methods=["GET"])
    def transferencias(self, request, pk=None):
        pass

    @action(detail=True, methods=["GET"])
    def relatorios(self, request, pk=None):
        pass




    # ==========================================
    # PDF
    # ==========================================

    @action(
        detail=True,
        methods=["GET"],
    )
    def pdf(self, request, *args, **kwargs):

        consulta = self.get_object()

        entity = Entity.objects.get(
            id=consulta.entity.id
        )

        logo_b64 = None

        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(
                        f.read()
                    )

        except FileNotFoundError:
            pass

        qr_b64 = make_qr_b64(str(consulta.id))
        barcode_b64 = make_barcode_b64(str(consulta.id))

        return PDF(
            "saude/consultamedica.html",
            request,
            entity=entity,
            logo_b64=logo_b64,
            qr_b64=qr_b64,
            barcode_b64=barcode_b64,
            consulta=consulta,
            # same content and order as the consultation form (ConsultaSEPage)
            **consultation_service.pdf_context(request, consulta),
        )

    # ==========================================
    # HISTÓRICO DO PACIENTE
    # ==========================================

    @action(
        detail=True,
        methods=["GET"],
    )
    def historico(self, request, *args, **kwargs):

        consulta = self.get_object()

        rows = Consulta.objects.filter(
            paciente=consulta.paciente
        ).exclude(
            id=consulta.id
        )

        serializer = self.get_serializer(
            rows,
            many=True
        )

        return Response(serializer.data)

    # ==========================================
    # CONSULTAS POR PACIENTE
    # ==========================================

    @action(
        detail=False,
        methods=["GET"],
        url_path="paciente/(?P<paciente_id>[^/.]+)"
    )
    def paciente(self, request, paciente_id=None):

        rows = Consulta.objects.filter(
            paciente_id=paciente_id
        )

        serializer = self.get_serializer(
            rows,
            many=True
        )

        return Response(serializer.data)

    # ==========================================
    # CRIAR CONSULTA A PARTIR DE AGENDAMENTO
    # ==========================================

    @action(
        detail=False,
        methods=["POST"]
    )
    def iniciar(self, request):

        agenda_id = request.data.get("agenda")

        agenda = get_object_or_404(
            Agenda,
            id=agenda_id
        )

        consulta = Consulta.objects.create(
            paciente=agenda.paciente,
            employee=agenda.employee,
            entity=agenda.entity,
            branch=agenda.branch,
            created_by=request.user,
            updated_by=request.user,
        )

        agenda.consulta = consulta
        agenda.estado = 3  # concluída
        agenda.save()

        return Response(
            self.get_serializer(
                consulta
            ).data
        )