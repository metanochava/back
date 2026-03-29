# rh/api/views/departamento.py

from django_resaas.core.base.views import BaseAPIView, registerView
from rh.models.departamento import Departamento
from rh.serializers.departamento import DepartamentoSerializer

@registerView(module="rh")
class DepartamentoAPIView(BaseAPIView):
    queryset = Departamento.objects.all()
    serializer_class = DepartamentoSerializer