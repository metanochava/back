
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from rh.models.funcionario import Funcionario
from rh.serializers.funcionario import FuncionarioSerializer


@registerView('funcionarios')
class FuncionarioAPIView(BaseAPIView):
    queryset = Funcionario.objects.all()   
    serializer_class = FuncionarioSerializer
    
