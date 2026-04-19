
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from rh.models.funcionario_cargo import FuncionarioCargo
from rh.serializers.funcionario_cargo import FuncionarioCargoSerializer


@registerView('funcionariocargos')
class FuncionarioCargoAPIView(BaseAPIView):
    queryset = FuncionarioCargo.objects.all()   
    serializer_class = FuncionarioCargoSerializer
    
