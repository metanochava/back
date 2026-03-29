# rh/api/views/contrato.py

from django_resaas.core.base.views import BaseAPIView, registerView
from rh.models.contrato import Contrato
from rh.serializers.contrato import ContratoSerializer

@registerView(module="rh")
class ContratoAPIView(BaseAPIView):
    queryset = Contrato.objects.all()
    serializer_class = ContratoSerializer