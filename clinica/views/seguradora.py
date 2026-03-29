
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from clinica.models.seguradora import Seguradora
from clinica.serializers.seguradora import SeguradoraSerializer


@registerView()
class SeguradoraAPIView(BaseAPIView):
    queryset = Seguradora.objects.all()   
    serializer_class = SeguradoraSerializer
    
