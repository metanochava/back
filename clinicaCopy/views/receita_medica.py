
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from clinica.models.receita_medica import ReceitaMedica
from clinica.serializers.receita_medica import ReceitaMedicaSerializer


@registerView()
class ReceitaMedicaAPIView(BaseAPIView):
    queryset = ReceitaMedica.objects.all()   
    serializer_class = ReceitaMedicaSerializer
    
