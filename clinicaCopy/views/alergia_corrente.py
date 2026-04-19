
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from clinica.models.alergia_corrente import AlergiaCorrente
from clinica.serializers.alergia_corrente import AlergiaCorrenteSerializer


@registerView()
class AlergiaCorrenteAPIView(BaseAPIView):
    queryset = AlergiaCorrente.objects.all()   
    serializer_class = AlergiaCorrenteSerializer
    
