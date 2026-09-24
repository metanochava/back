
from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.serializers.pedidoexamemedico import PedidoExameMedicoSerializer
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.serializers.resultadoexamemedico import ResultadoExameMedicoSerializer
from saude.serializers.itempedidoexamemedico import ItemPedidoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF, all

from django.db.models import Prefetch
import barcode
import qrcode

from django.db import transaction
from django_resaas.saas.core.decorators.action import resaas_action
from saude.services import exam_request_service


@registerView('pedidoexamemedicos')
class PedidoExameMedicoAPIView(BaseAPIView):
    queryset = PedidoExameMedico.objects.all()   
    serializer_class = PedidoExameMedicoSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Doctor request or exam only - see
        saude/services/exam_request_service.py. The patient and the
        consultation are resolved inside the current Entity; the client
        never picks the tenant."""

        paciente, consulta, origin = exam_request_service.resolve_request_context(request, request.data)

        data = request.data.copy()
        data.pop("consulta", None)
        data.pop("paciente", None)
        data.pop("origin", None)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        pedidoexame = serializer.save(
            paciente=paciente,
            consulta=consulta,
            origin=origin,
            entity_id=request.entity_id,
            branch_id=request.branch_id,
            created_by=request.user,
            updated_by=request.user,
        )

        return all(request,
            data= self.get_serializer(pedidoexame).data,
            status=201
        )

    @resaas_action(detail=True, methods=["post"], label="Check in", icon="login")
    def check_in(self, request, *args, **kwargs):
        """Patient arrived for these exams (laboratory waiting starts).
        Idempotent: repeating it keeps the first time."""

        pedido = exam_request_service.check_in(self.get_object())
        return all(request, data=self.get_serializer(pedido).data)

   
    @action(
        detail=True,
        methods=['GET'],
    )
    def pdf(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)
        pedido = self.get_object()
        paciente = pedido.patient

        items = (
            pedido.items
            .select_related(
                "exame",
                "exame__classe_exame_medico",
                "exame__classe_exame_medico__tipo_exame_medico",
            )
            .order_by(
                "exame__classe_exame_medico__tipo_exame_medico__ordem",
                "exame__classe_exame_medico__ordem",
                "exame__nome",
            )
        )

        logo_b64 = None
        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(f.read())

        except FileNotFoundError:
            logo_b64 = None

        qr_b64 = make_qr_b64(f"{pedido.id}")
        barcode_b64 = make_barcode_b64(f"{pedido.id}")
        
        return PDF(
            "saude/pedidoexamemedico.html",
            request,
            entity=entity,
            pedido=pedido,
            items=items,
            logo_b64=logo_b64,
            qr_b64=make_qr_b64(str(pedido.id)),
            barcode_b64=make_barcode_b64(str(pedido.id)),
            paciente=paciente,
        )





    @action(
        detail=True,
        methods=["get"],
    )
    def items(self, request, *args, **kwargs):

        pedido = self.get_object()

        queryset = (
            pedido.items
            .select_related(
                "pedido",
                "exame",
                "exame__classe_exame_medico",
                "exame__classe_exame_medico__tipo_exame_medico",
            )
            .prefetch_related(
                Prefetch(
                    "resultados",
                    queryset=ResultadoExameMedico.objects.select_related(
                        "emitido_por",
                        "validado_por",
                    ).order_by(
                        "-numero_revisao",
                        "-created_at",
                    ),
                ),
            )
            .order_by(
                "exame__classe_exame_medico__tipo_exame_medico__ordem",
                "exame__classe_exame_medico__ordem",
                "exame__nome",
            )
        )

        serializer = ItemPedidoExameMedicoSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return all(
            request,
            data=serializer.data,
            status=200,
        )    


        
           
    @action(
        detail=True,
        methods=['GET'],
    )
    def resultados(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)
        pedido = self.get_object()
        paciente = pedido.patient

        resultados = ResultadoExameMedico.objects.filter(
            item_pedido__pedido=pedido
        ).select_related(
            "item_pedido",
            "item_pedido__exame",
            "emitido_por",
            "validado_por"
        )

        return all(
            request,
            data=ResultadoExameMedicoSerializer(resultados, many=True).data,
            status=200
        )
