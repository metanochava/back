
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.alergiacorrente import Alergiacorrente
from saude.serializers.alergiacorrente import AlergiacorrenteSerializer


@registerView('alergiacorrentes')
class AlergiacorrenteAPIView(BaseAPIView):
    queryset = Alergiacorrente.objects.all()   
    serializer_class = AlergiacorrenteSerializer
    
