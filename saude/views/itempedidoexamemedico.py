
from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.serializers.itempedidoexamemedico import ItemPedidoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF

import barcode
import qrcode

from saude.services import exam_request_service


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
