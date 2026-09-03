
from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView
from saude.models.medicacaocorrente import MedicacaoCorrente
from saude.serializers.medicacaocorrente import MedicacaoCorrenteSerializer


@registerView('medicacaocorrentes')
class MedicacaoMorrenteAPIView(BaseAPIView):
    queryset = MedicacaoCorrente.objects.all()   
    serializer_class = MedicacaoCorrenteSerializer
    
