
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.atestadomedico import Atestadomedico
from saude.serializers.atestadomedico import AtestadomedicoSerializer


@registerView('atestadomedicos')
class AtestadomedicoAPIView(BaseAPIView):
    queryset = Atestadomedico.objects.all()   
    serializer_class = AtestadomedicoSerializer
    
