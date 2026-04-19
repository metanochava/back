
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.guiatransferencia import Guiatransferencia
from saude.serializers.guiatransferencia import GuiatransferenciaSerializer


@registerView('guiatransferencias')
class GuiatransferenciaAPIView(BaseAPIView):
    queryset = Guiatransferencia.objects.all()   
    serializer_class = GuiatransferenciaSerializer
    
