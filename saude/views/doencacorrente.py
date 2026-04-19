
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.doencacorrente import Doencacorrente
from saude.serializers.doencacorrente import DoencacorrenteSerializer


@registerView('doencacorrentes')
class DoencacorrenteAPIView(BaseAPIView):
    queryset = Doencacorrente.objects.all()   
    serializer_class = DoencacorrenteSerializer
    
