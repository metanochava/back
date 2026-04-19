
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.receitamedica import Receitamedica
from saude.serializers.receitamedica import ReceitamedicaSerializer


@registerView('receitamedicas')
class ReceitamedicaAPIView(BaseAPIView):
    queryset = Receitamedica.objects.all()   
    serializer_class = ReceitamedicaSerializer
    
