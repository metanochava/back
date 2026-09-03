
from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView
from saude.models.medicamento import Medicamento
from saude.serializers.medicamento import MedicamentoSerializer


@registerView('medicamentos')
class MedicamentoAPIView(BaseAPIView):
    queryset = Medicamento.objects.all()   
    serializer_class = MedicamentoSerializer

    # def perform_create(self, serializer):
    #     serializer.save()
    
