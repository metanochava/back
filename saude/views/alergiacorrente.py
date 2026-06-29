
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.alergiacorrente import AlergiaCorrente
from saude.serializers.alergiacorrente import AlergiaCorrenteSerializer


@registerView('alergiacorrentes')
class AlergiaCorrenteAPIView(BaseAPIView):
    queryset = AlergiaCorrente.objects.all()   
    serializer_class = AlergiaCorrenteSerializer
    
