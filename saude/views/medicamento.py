
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.medicamento import Medicamento
from saude.serializers.medicamento import MedicamentoSerializer


@registerView('medicamentos')
class MedicamentoAPIView(BaseAPIView):
    queryset = Medicamento.objects.all()   
    serializer_class = MedicamentoSerializer
    
