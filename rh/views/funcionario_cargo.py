# rh/api/views/funcionario_cargo.py

from django_resaas.core.base.views import BaseAPIView, registerView
from rh.models.funcionario_cargo import FuncionarioCargo
from rh.serializers.funcionario_cargo import FuncionarioCargoSerializer

@registerView(module="rh")
class FuncionarioCargoAPIView(BaseAPIView):
    queryset = FuncionarioCargo.objects.all()
    serializer_class = FuncionarioCargoSerializer