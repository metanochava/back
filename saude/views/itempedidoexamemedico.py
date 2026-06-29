
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.serializers.itempedidoexamemedico import ItemPedidoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.models.entity import Entity
from django_resaas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF

import barcode
import qrcode


@registerView('itempedidoexamemedicos')
class ItemPedidoExameMedicoAPIView(BaseAPIView):
    queryset = ItemPedidoExameMedico.objects.all()   
    serializer_class = ItemPedidoExameMedicoSerializer
    