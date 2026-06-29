
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.doencacorrente import DoencaCorrente
from saude.serializers.doencacorrente import DoencaCorrenteSerializer


@registerView('doencacorrentes')
class DoencaCorrenteAPIView(BaseAPIView):
    queryset = DoencaCorrente.objects.all()   
    serializer_class = DoencaCorrenteSerializer
    
