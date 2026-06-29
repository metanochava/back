
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.tipoexamemedico import TipoExameMedico
from saude.serializers.tipoexamemedico import TipoExameMedicoSerializer


@registerView('tipoexamemedicos')
class TipoExameMedicoAPIView(BaseAPIView):
    queryset = TipoExameMedico.objects.all()   
    serializer_class = TipoExameMedicoSerializer
    
