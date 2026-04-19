
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.medicacaocorrente import Medicacaocorrente
from saude.serializers.medicacaocorrente import MedicacaocorrenteSerializer


@registerView('medicacaocorrentes')
class MedicacaocorrenteAPIView(BaseAPIView):
    queryset = Medicacaocorrente.objects.all()   
    serializer_class = MedicacaocorrenteSerializer
    
