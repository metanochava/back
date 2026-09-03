from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from django_resaas.engine.core.base.views import BaseAPIView, registerView
from django_resaas.engine.models.entity import Entity
from django_resaas.engine.core.utils import (
    make_qr_b64,
    make_barcode_b64,
    png_bytes_to_b64,
    PDF
)

from saude.models.consulta import Consulta
from saude.models.agenda import Agenda
from saude.serializers.consulta import ConsultaSerializer


@registerView("consultas")
class ConsultaAPIView(BaseAPIView):

    queryset = Consulta.objects.all()
    serializer_class = ConsultaSerializer


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
            consulta=consulta
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