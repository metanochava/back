
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.dadovital import Dadovital
from saude.serializers.dadovital import DadovitalSerializer


@registerView('dadovitals')
class DadovitalAPIView(BaseAPIView):
    queryset = Dadovital.objects.all()   
    serializer_class = DadovitalSerializer
    
