# rh/api/views/funcionario.py

from django_resaas.core.base.views import BaseAPIView, registerView
from rh.models.funcionario import Funcionario
from rh.serializers.funcionario import FuncionarioSerializer

@registerView(module="rh")
class FuncionarioAPIView(BaseAPIView):
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer