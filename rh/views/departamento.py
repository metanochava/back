
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from rh.models.departamento import Departamento
from rh.serializers.departamento import DepartamentoSerializer


@registerView('departamentos')
class DepartamentoAPIView(BaseAPIView):
    queryset = Departamento.objects.all()   
    serializer_class = DepartamentoSerializer
    
