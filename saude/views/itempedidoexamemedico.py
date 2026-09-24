
from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.serializers.itempedidoexamemedico import ItemPedidoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF

import barcode
import qrcode

from rest_framework.response import Response

from django_resaas.saas.core.decorators.action import resaas_action
from saude.services import exam_request_service, lab_result_service


@registerView('itempedidoexamemedicos')
class ItemPedidoExameMedicoAPIView(BaseAPIView):
    queryset = ItemPedidoExameMedico.objects.all()   
    serializer_class = ItemPedidoExameMedicoSerializer
    
    def perform_update(self, serializer):
        previous_state = serializer.instance.estado_exame

        super().perform_update(serializer)

        # collection time is stamped by the server when the item becomes
        # "colhido" (saude/services/exam_request_service.py)
        exam_request_service.stamp_collection(serializer.instance, previous_state)

    # ------------------------------------------------------------------
    # Laboratory workflow (saude/services/exam_request_service.py,
    # saude/services/lab_result_service.py). All PROTECTED: BaseAPIView
    # checks the permission of each action and get_object() keeps the
    # item inside the current Entity/Branch.
    # ------------------------------------------------------------------

    @resaas_action(detail=True, methods=["get"], label="Result form", icon="science",
                   permission="view_itempedidoexamemedico")
    def result_form(self, request, *args, **kwargs):
        """The exam's active parameters (+ applicable reference, current
        values) the dynamic result form is built from."""
        return Response(lab_result_service.form_schema(self.get_object()))

    @resaas_action(detail=True, methods=["post"], label="Record result", icon="edit_note")
    def record_result(self, request, *args, **kwargs):
        """{"values": {code: value}, "observacao"?, "laudo"?} - validated
        against the exam definition by the server."""
        item = self.get_object()
        lab_result_service.record_result(
            request, item, request.data.get("values"),
            observacao=request.data.get("observacao"), laudo=request.data.get("laudo"),
        )
        return Response(lab_result_service.form_schema(item))

    @resaas_action(detail=True, methods=["post"], label="Collect", icon="colorize")
    def collect(self, request, *args, **kwargs):
        item = exam_request_service.collect(request, self.get_object())
        return Response(self.get_serializer(item).data)

    @resaas_action(detail=True, methods=["post"], label="Reject sample", icon="block")
    def reject_sample(self, request, *args, **kwargs):
        item = exam_request_service.reject_sample(request, self.get_object(), request.data.get("reason"))
        return Response(self.get_serializer(item).data)
